"""Machine registry, QR calibration, authorization checks, and shift alerts."""

from __future__ import annotations

from datetime import datetime
import json
import math
from pathlib import Path
import threading
import time
import uuid


class MachineRegistry:
    def __init__(self, path="configs/machines.json", max_shift_px=50, cooldown_seconds=60,
                 touch_person_iou=0.05, touch_confirm_frames=4, touch_max_gap_seconds=1.5,
                 touch_cooldown_seconds=30):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_shift_px = float(max_shift_px)
        self.cooldown_seconds = float(cooldown_seconds)
        self.touch_person_iou = float(touch_person_iou)
        self.touch_confirm_frames = int(touch_confirm_frames)
        self.touch_max_gap_seconds = float(touch_max_gap_seconds)
        self.touch_cooldown_seconds = float(touch_cooldown_seconds)
        self._lock = threading.RLock()
        self._shift_active = set()
        self._last_shift_alert = {}
        self._touch_counts = {}
        self._last_touch_alert = {}
        self._identity_presence = {}
        self._data = self._load()

    def _load(self):
        if not self.path.exists():
            return {"machines": {}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value.get("machines"), dict):
                value["machines"] = {}
            return value
        except (OSError, json.JSONDecodeError):
            return {"machines": {}}

    def _save(self):
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def list_machines(self):
        with self._lock:
            return [{"machine_id": machine_id, **dict(value)} for machine_id, value in self._data["machines"].items()]

    def get(self, machine_id):
        with self._lock:
            item = self._data["machines"].get(str(machine_id))
            return dict(item) if item else None

    def upsert(self, machine_id, camera_id, detection_labels=None, authorized_person_ids=None, qr_value=None):
        machine_id = str(machine_id).strip()
        camera_id = str(camera_id).strip()
        if not machine_id or not camera_id:
            raise ValueError("machine_id and camera_id are required")
        with self._lock:
            current = self._data["machines"].get(machine_id, {})
            current.update({
                "camera_id": camera_id,
                "detection_labels": [str(label).strip() for label in (detection_labels or []) if str(label).strip()],
                "authorized_person_ids": sorted({str(person).strip() for person in (authorized_person_ids or []) if str(person).strip()}),
                "qr_value": str(qr_value or current.get("qr_value") or f"PRAHARI:MACHINE:{machine_id}"),
                "maintenance_mode": bool(current.get("maintenance_mode", False)),
                "home_position": current.get("home_position"),
            })
            self._data["machines"][machine_id] = current
            self._save()
            return {"machine_id": machine_id, **dict(current)}

    def calibrate(self, machine_id, camera_id, x_percent, y_percent):
        machine_id = str(machine_id)
        x_percent, y_percent = float(x_percent), float(y_percent)
        if not (0 <= x_percent <= 100 and 0 <= y_percent <= 100):
            raise ValueError("calibration coordinates must be between 0 and 100 percent")
        with self._lock:
            machine = self._data["machines"].get(machine_id)
            if machine is None:
                raise KeyError(machine_id)
            if str(machine.get("camera_id")) != str(camera_id):
                raise ValueError("camera_id does not match the machine registry")
            machine["home_position"] = {"x_percent": x_percent, "y_percent": y_percent, "calibrated_at": time.time()}
            machine["maintenance_mode"] = False
            self._save()
            return {"machine_id": machine_id, **dict(machine)}

    def set_maintenance(self, machine_id, enabled):
        with self._lock:
            machine = self._data["machines"].get(str(machine_id))
            if machine is None:
                raise KeyError(machine_id)
            machine["maintenance_mode"] = bool(enabled)
            self._save()
            return {"machine_id": str(machine_id), **dict(machine)}

    def register_identity_presence(self, camera_id, track_id, person_id, source="rfid", ttl_seconds=30):
        if not camera_id or not track_id or not person_id:
            raise ValueError("camera_id, track_id and person_id are required")
        ttl = min(300.0, max(1.0, float(ttl_seconds)))
        key = (str(camera_id), str(track_id))
        with self._lock:
            self._identity_presence[key] = {"person_id": str(person_id), "source": str(source), "expires_at": time.time() + ttl}

    def identity_for(self, camera_id, detection):
        direct = detection.get("person_id")
        if direct:
            return str(direct)
        track_id = detection.get("track_id") or detection.get("tracker_id")
        with self._lock:
            presence = self._identity_presence.get((str(camera_id), str(track_id)))
            if presence and presence["expires_at"] > time.time():
                return presence["person_id"]
            if presence:
                self._identity_presence.pop((str(camera_id), str(track_id)), None)
        return None

    def check_interlock(self, machine_id, person_id, ppe):
        machine = self.get(machine_id)
        if machine is None:
            return {"machine_id": str(machine_id), "start_allowed": False, "reasons": ["Machine is not registered."], "mode": "dry-run", "relay_action": "none"}
        reasons = []
        if machine.get("maintenance_mode"):
            reasons.append("Machine is in maintenance mode.")
        if not person_id:
            reasons.append("Operator identity is not verified.")
        elif str(person_id) not in set(machine.get("authorized_person_ids", [])):
            reasons.append("Operator is not authorized for this machine.")
        for item in ("helmet", "vest", "gloves"):
            if not bool((ppe or {}).get(item, False)):
                reasons.append(f"Required PPE not verified: {item}.")
        allowed = not reasons
        return {
            "machine_id": str(machine_id), "person_id": str(person_id) if person_id else None,
            "start_allowed": allowed, "reasons": reasons,
            "mode": "dry-run", "relay_action": "would_allow_start" if allowed else "would_block_start",
            "physical_actuation": False,
        }

    @staticmethod
    def _parse_machine_id(payload, configured):
        value = str(payload or "").strip()
        prefixes = ("prahari:machine:", "machine:", "machine_id=")
        lower = value.casefold()
        for prefix in prefixes:
            if lower.startswith(prefix):
                value = value[len(prefix):].strip()
                break
        return value if value in configured else None

    def scan_qr_markers(self, frame, camera_id, timestamp=None):
        configured = {item["machine_id"]: item for item in self.list_machines()
                      if item.get("camera_id") == str(camera_id) and item.get("home_position")}
        if not configured or frame is None:
            return []
        try:
            import cv2
            import numpy as np
            detector = cv2.QRCodeDetector()
            decoded = []
            try:
                success, values, points, _ = detector.detectAndDecodeMulti(frame)
                if success and points is not None:
                    decoded = list(zip(values, points))
            except (AttributeError, cv2.error):
                pass
            if not decoded:
                value, points, _ = detector.detectAndDecode(frame)
                if value and points is not None:
                    decoded = [(value, points[0])]
            now = float(timestamp if timestamp is not None else time.time())
            height, width = frame.shape[:2]
            events = []
            for value, corners in decoded:
                machine_id = self._parse_machine_id(value, configured)
                if not machine_id:
                    continue
                points = np.asarray(corners, dtype=float).reshape(-1, 2)
                marker_x = float(points[:, 0].mean())
                marker_y = float(points[:, 1].mean())
                machine = configured[machine_id]
                home = machine["home_position"]
                dx = (marker_x / max(1, width) * 100.0 - float(home["x_percent"])) * width / 100.0
                dy = (marker_y / max(1, height) * 100.0 - float(home["y_percent"])) * height / 100.0
                distance = math.hypot(dx, dy)
                key = (str(camera_id), machine_id)
                threshold = float(machine.get("max_shift_px", self.max_shift_px))
                if distance <= threshold or machine.get("maintenance_mode"):
                    self._shift_active.discard(key)
                    continue
                if key in self._shift_active or now - self._last_shift_alert.get(key, -float("inf")) < self.cooldown_seconds:
                    continue
                self._shift_active.add(key)
                self._last_shift_alert[key] = now
                events.append({
                    "event_id": str(uuid.uuid4()), "event_type": "machine_shift", "severity": "warning",
                    "title": "Machine shifted from calibrated position",
                    "detail": f"{machine_id} is {distance:.0f}px from its calibrated home position.",
                    "camera_id": str(camera_id), "zone_id": None, "track_id": None,
                    "person_id": None, "machine_id": machine_id, "confidence": 1.0,
                    "timestamp": now, "bbox": None,
                    "evidence": {"shift_px": round(distance, 1), "threshold_px": threshold, "marker": value},
                    "status": "new",
                })
            return events
        except Exception as exc:
            print(f"[WARN] Machine QR scan unavailable: {exc}")
            return []

    def evaluate_touches(self, camera_id, detections, timestamp=None):
        now = float(timestamp if timestamp is not None else time.time())
        machines = [item for item in self.list_machines() if item.get("camera_id") == str(camera_id)]
        if not machines:
            return []
        events = []

        def get_box(detection):
            if isinstance(detection.get("bbox"), (list, tuple)) and len(detection["bbox"]) == 4:
                return tuple(float(value) for value in detection["bbox"])
            if all(key in detection for key in ("x", "y", "w", "h")):
                return (float(detection["x"]), float(detection["y"]),
                        float(detection["x"]) + float(detection["w"]),
                        float(detection["y"]) + float(detection["h"]))
            return None

        people = [d for d in (detections or []) if "person" in str(d.get("class", "")).casefold()
                  and d.get("tracking_confirmed") is not False and get_box(d)]
        observed_touch_keys = set()
        for machine in machines:
            labels = [str(label).casefold() for label in machine.get("detection_labels", [])]
            machine_detections = [d for d in (detections or []) if
                                  (str(d.get("machine_id") or "") == machine["machine_id"] or
                                   str(d.get("class", "")).casefold() in labels) and get_box(d)]
            authorized = set(machine.get("authorized_person_ids", []))
            for machine_detection in machine_detections:
                mb = get_box(machine_detection)
                for person in people:
                    identity = self.identity_for(camera_id, person)
                    if identity and identity in authorized:
                        continue
                    pb = get_box(person)
                    ax1, ay1 = max(mb[0], pb[0]), max(mb[1], pb[1])
                    ax2, ay2 = min(mb[2], pb[2]), min(mb[3], pb[3])
                    inter = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
                    area_person = max(1.0, (pb[2] - pb[0]) * (pb[3] - pb[1]))
                    area_machine = max(1.0, (mb[2] - mb[0]) * (mb[3] - mb[1]))
                    overlap = inter / max(1.0, area_person + area_machine - inter)
                    if overlap < float(machine.get("touch_person_iou", self.touch_person_iou)):
                        continue
                    track_id = str(person.get("track_id") or person.get("tracker_id") or "unknown")
                    key = (str(camera_id), machine["machine_id"], track_id)
                    observed_touch_keys.add(key)
                    count, last = self._touch_counts.get(key, (0, 0.0))
                    count = count + 1 if now - last <= self.touch_max_gap_seconds else 1
                    self._touch_counts[key] = (count, now)
                    required = int(machine.get("touch_confirm_frames", self.touch_confirm_frames))
                    if count != required:
                        continue
                    if now - self._last_touch_alert.get(key, -float("inf")) < float(machine.get("touch_cooldown_seconds", self.touch_cooldown_seconds)):
                        continue
                    self._last_touch_alert[key] = now
                    events.append({
                        "event_id": str(uuid.uuid4()), "event_type": "unauthorized_machine_touch",
                        "severity": "critical", "title": "Unverified person overlapping machine",
                        "detail": f"Track {track_id} overlaps {machine['machine_id']}; camera overlap is a proxy and does not confirm hand contact.",
                        "camera_id": str(camera_id), "zone_id": None, "track_id": track_id,
                        "person_id": identity, "machine_id": machine["machine_id"],
                        "confidence": float(person.get("confidence", 0)) / 100.0,
                        "timestamp": now, "bbox": list(pb),
                        "evidence": {"person_machine_overlap": round(overlap, 3), "confirmed_frames": count},
                        "status": "new",
                    })
        for key in [key for key in self._touch_counts if key[0] == str(camera_id) and key not in observed_touch_keys]:
            self._touch_counts.pop(key, None)
        return events
