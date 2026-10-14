"""Compose the PRAHARI risk engine, local event store, and action adapters."""

from __future__ import annotations

import json
from pathlib import Path
import time

from .action_router import ActionRouter
from .interlock import SafetyInterlock
from .machine_safety import MachineRegistry
from .risk_engine import RiskEngine
from .store import IncidentStore


def read_json(path, fallback=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback or {}


class SafetyRuntime:
    def __init__(self, config_path="configs/risk_config.json"):
        self.config_path = Path(config_path)
        self.config = read_json(self.config_path, {})
        self.risk_engine = RiskEngine(self.config)
        self.store = IncidentStore(self.config.get("incident_store", {}))
        self.action_router = ActionRouter(self.config)
        machine_config = self.config.get("machines_file", "configs/machines.json")
        machine_rule = self.config.get("rules", {}).get("machine_shift", {})
        touch_rule = self.config.get("rules", {}).get("machine_touch", {})
        self.machines = MachineRegistry(
            machine_config,
            max_shift_px=machine_rule.get("max_shift_px", 50),
            cooldown_seconds=machine_rule.get("cooldown_seconds", 60),
            touch_person_iou=touch_rule.get("minimum_overlap_iou", 0.05),
            touch_confirm_frames=touch_rule.get("confirm_frames", 4),
            touch_max_gap_seconds=touch_rule.get("max_track_gap_seconds", 1.5),
            touch_cooldown_seconds=touch_rule.get("cooldown_seconds", 30),
        )
        self.interlock = SafetyInterlock(self.machines)

    def process_frame(self, camera_id, detections, frame, zones=None, timestamp=None, archive_frame=None):
        now = float(timestamp if timestamp is not None else time.time())
        self.store.append_frame(camera_id, archive_frame if archive_frame is not None else frame, now)
        size = frame.shape[:2] if frame is not None else (540, 960)
        events = self.risk_engine.evaluate(camera_id, detections, zones, now, size)
        machine_rules = self.config.get("rules", {})
        if frame is not None and machine_rules.get("machine_shift", {}).get("enabled", True):
            events.extend(self.machines.scan_qr_markers(frame, camera_id, now))
        if machine_rules.get("machine_touch", {}).get("enabled", True):
            events.extend(self.machines.evaluate_touches(camera_id, detections, now))

        output = []
        for event in events:
            saved = self.store.record_event(event, frame)
            saved["actions"] = self.action_router.dispatch(saved)
            self.store.update_payload(saved["event_id"], {"actions": saved["actions"]})
            saved["snapshot_url"] = self._media_url(saved.get("snapshot_path"))
            saved["clip_url"] = self._media_url(saved.get("clip_path"))
            output.append(saved)
        return output

    def _media_url(self, path):
        if not path:
            return None
        try:
            relative = Path(path).resolve().relative_to(self.store.root.resolve())
            return "/incidents/" + relative.as_posix()
        except (ValueError, OSError):
            return None

    def list_events(self, limit=50, camera_id=None):
        events = self.store.list_events(limit, camera_id)
        for event in events:
            event["snapshot_url"] = self._media_url(event.get("snapshot_path"))
            event["clip_url"] = self._media_url(event.get("clip_path"))
        return events

    def auto_escalate_due(self):
        delay = float(self.config.get("admin", {}).get("auto_escalate_seconds", 60))
        due = self.store.escalate_unacknowledged(time.time() - delay)
        escalated = []
        for event in due:
            event["actions"] = self.action_router.dispatch(event)
            escalated.append(event)
        return escalated
