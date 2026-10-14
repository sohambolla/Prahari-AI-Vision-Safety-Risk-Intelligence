"""Config-driven incident routing. Physical outputs are dry-run by default."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import urllib.request


class ActionRouter:
    def __init__(self, config=None):
        self.config = config or {}
        self.site_config = self.config.get("site", {})
        self.admin_config = self.config.get("admin", {})
        self._executor = ThreadPoolExecutor(max_workers=3, thread_name_prefix="prahari-alert")

    def _site_route(self, event):
        routes = self.site_config.get("zone_routes", {})
        camera_id = str(event.get("camera_id") or "")
        zone_id = str(event.get("zone_id") or "default")
        return routes.get(f"{camera_id}:{zone_id}") or routes.get(camera_id) or {}

    @staticmethod
    def _post_json(url, payload, timeout=0.35, headers=None):
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.status)

    def _send_telegram(self, event):
        token = os.environ.get("PRAHARI_TELEGRAM_BOT_TOKEN")
        chat_id = os.environ.get("PRAHARI_TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            return
        api_root = f"https://api.telegram.org/bot{token}"
        caption = f"{event.get('severity', 'warning').upper()}: {event.get('title')}\n{event.get('camera_id')} · {event.get('zone_id') or 'unassigned zone'}\n{event.get('detail', '')}"
        try:
            snapshot = Path(str(event.get("snapshot_path") or ""))
            if snapshot.is_file():
                boundary = "----PrahariSafetyIncident"
                parts = []
                for name, value in (("chat_id", chat_id), ("caption", caption[:1024])):
                    parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n{value}\r\n".encode())
                parts.append(
                    f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{snapshot.name}\"\r\nContent-Type: image/jpeg\r\n\r\n".encode()
                    + snapshot.read_bytes() + b"\r\n"
                )
                parts.append(f"--{boundary}--\r\n".encode())
                request = urllib.request.Request(
                    f"{api_root}/sendPhoto", data=b"".join(parts),
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST",
                )
                with urllib.request.urlopen(request, timeout=2.0):
                    pass
            else:
                self._post_json(f"{api_root}/sendMessage", {"chat_id": chat_id, "text": caption}, timeout=2.0)
        except Exception as exc:
            print(f"[WARN] Telegram incident delivery failed: {exc}")

    def dispatch(self, event):
        """Return immediate local status and queue optional remote adapters."""
        route = self._site_route(event)
        dry_run = (bool(self.site_config.get("dry_run", True))
                   or not bool(self.site_config.get("enabled", False))
                   or not bool(route.get("enabled", False)))
        if dry_run:
            simulated_outputs = route.get("simulated_outputs") or (
                ["zone_hooter", "red_beacon", "pa_announcement"]
                if str(event.get("severity", "")).lower() == "critical" else ["zone_beacon"]
            )
            site_result = {
                "mode": "dry-run", "dispatched": False,
                "zone_id": event.get("zone_id"),
                "simulated_outputs": simulated_outputs,
            }
        elif route.get("webhook_url"):
            payload = {key: value for key, value in event.items() if not key.startswith("_")}
            self._executor.submit(self._post_json, route["webhook_url"], payload, 0.35)
            site_result = {"mode": "webhook", "queued": True, "zone_id": event.get("zone_id")}
        else:
            site_result = {"mode": "unconfigured", "dispatched": False, "zone_id": event.get("zone_id")}

        telegram_queued = False
        if self.admin_config.get("telegram_enabled") and os.environ.get("PRAHARI_TELEGRAM_BOT_TOKEN") and os.environ.get("PRAHARI_TELEGRAM_CHAT_ID"):
            self._executor.submit(self._send_telegram, dict(event))
            telegram_queued = True

        call_url = os.environ.get("PRAHARI_CALL_WEBHOOK_URL")
        call_queued = False
        if call_url and self.admin_config.get("auto_call_enabled") and event.get("severity") == "critical":
            payload = {"event": {key: value for key, value in event.items() if not key.startswith("_")}, "provider": os.environ.get("PRAHARI_CALL_PROVIDER", "configured-webhook")}
            self._executor.submit(self._post_json, call_url, payload, 1.5)
            call_queued = True

        return {
            "site": site_result,
            "admin": {
                "websocket": bool(self.admin_config.get("websocket_enabled", True)),
                "telegram_queued": telegram_queued,
                "call_queued": call_queued,
            },
        }
