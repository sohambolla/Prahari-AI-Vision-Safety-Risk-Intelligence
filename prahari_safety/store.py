"""Local SQLite incident log with snapshots and a bounded pre-event video ring."""

from __future__ import annotations

from collections import defaultdict, deque
from contextlib import contextmanager
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time


class IncidentStore:
    def __init__(self, config=None):
        config = config or {}
        self.root = Path(config.get("root", "output/incidents"))
        self.root.mkdir(parents=True, exist_ok=True)
        self.db_path = Path(config.get("db_path", "output/incidents.sqlite3"))
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.clip_seconds = max(1.0, float(config.get("clip_seconds", 15)))
        self.buffer_fps = max(1.0, float(config.get("buffer_fps", 4)))
        self.max_frames = max(2, int(self.clip_seconds * self.buffer_fps))
        self._frames = defaultdict(lambda: deque(maxlen=self.max_frames))
        self._last_frame_at = {}
        self._lock = threading.RLock()
        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(self.db_path, timeout=5)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self):
        with self._connection() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS incidents (
                    event_id TEXT PRIMARY KEY,
                    timestamp REAL NOT NULL,
                    camera_id TEXT NOT NULL,
                    zone_id TEXT,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    title TEXT NOT NULL,
                    detail TEXT,
                    confidence REAL,
                    track_id TEXT,
                    person_id TEXT,
                    machine_id TEXT,
                    status TEXT NOT NULL DEFAULT 'new',
                    snapshot_path TEXT,
                    clip_path TEXT,
                    payload TEXT NOT NULL,
                    acknowledged_at REAL,
                    false_alarm_at REAL,
                    escalated_at REAL
                )
            """)
            connection.execute("CREATE INDEX IF NOT EXISTS incidents_time_idx ON incidents(timestamp DESC)")
            connection.execute("CREATE INDEX IF NOT EXISTS incidents_camera_idx ON incidents(camera_id, timestamp DESC)")

    @staticmethod
    def _safe_name(value):
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "unknown"))[:80] or "unknown"

    def append_frame(self, camera_id, frame, timestamp=None):
        """Keep at most 15 seconds of JPEG-compressed frames for incident clips."""
        if frame is None:
            return
        now = float(timestamp if timestamp is not None else time.time())
        with self._lock:
            if now - self._last_frame_at.get(str(camera_id), 0.0) < 1.0 / self.buffer_fps:
                return
            try:
                import cv2
                ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                if not ok:
                    return
                self._frames[str(camera_id)].append((now, encoded.tobytes(), int(frame.shape[1]), int(frame.shape[0])))
                self._last_frame_at[str(camera_id)] = now
            except Exception:
                return

    def _save_snapshot(self, directory, frame, camera_id):
        if frame is None:
            frames = self._frames.get(str(camera_id))
            if not frames:
                return None
            try:
                import cv2
                frame = cv2.imdecode(__import__("numpy").frombuffer(frames[-1][1], dtype=__import__("numpy").uint8), cv2.IMREAD_COLOR)
            except Exception:
                return None
        try:
            import cv2
            ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 88])
            if not ok:
                return None
            path = directory / "snapshot.jpg"
            path.write_bytes(encoded.tobytes())
            return path
        except Exception:
            return None

    def _save_clip(self, directory, camera_id):
        frames = list(self._frames.get(str(camera_id), ()))
        if len(frames) < 2:
            return None
        try:
            import cv2
            import numpy as np
            width, height = frames[-1][2], frames[-1][3]
            path = directory / "incident.mp4"
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), self.buffer_fps, (width, height))
            if not writer.isOpened():
                writer.release()
                return None
            for _, data, frame_width, frame_height in frames:
                image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
                if image is None:
                    continue
                if image.shape[1] != width or image.shape[0] != height:
                    image = cv2.resize(image, (width, height))
                writer.write(image)
            writer.release()
            return path if path.exists() and path.stat().st_size > 0 else None
        except Exception:
            return None

    def record_event(self, event, frame=None):
        event = dict(event)
        event_id = str(event.get("event_id") or event.get("id") or f"evt-{int(time.time() * 1000)}")
        event["event_id"] = event_id
        stamp = float(event.get("timestamp") or time.time())
        local = datetime.fromtimestamp(stamp)
        camera = self._safe_name(event.get("camera_id"))
        folder = self.root / camera / local.strftime("%Y-%m-%d") / f"{local.strftime('%H-%M-%S')}_{self._safe_name(event_id)}"
        folder.mkdir(parents=True, exist_ok=True)

        with self._lock:
            snapshot = self._save_snapshot(folder, frame, event.get("camera_id"))
            clip = self._save_clip(folder, event.get("camera_id"))

        event["snapshot_path"] = str(snapshot) if snapshot else None
        event["clip_path"] = str(clip) if clip else None
        event.setdefault("status", "new")
        with self._connection() as connection:
            connection.execute("""
                INSERT OR IGNORE INTO incidents (
                    event_id, timestamp, camera_id, zone_id, event_type, severity,
                    title, detail, confidence, track_id, person_id, machine_id,
                    status, snapshot_path, clip_path, payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event_id, stamp, str(event.get("camera_id") or "unknown"), event.get("zone_id"),
                str(event.get("event_type") or "safety_event"), str(event.get("severity") or "warning"),
                str(event.get("title") or "Safety event"), event.get("detail"), event.get("confidence"),
                event.get("track_id"), event.get("person_id"), event.get("machine_id"), event["status"],
                event["snapshot_path"], event["clip_path"], json.dumps(event, ensure_ascii=False),
            ))
        return event

    @staticmethod
    def _decode_row(row):
        result = json.loads(row["payload"])
        result.update({
            "event_id": row["event_id"], "status": row["status"],
            "snapshot_path": row["snapshot_path"], "clip_path": row["clip_path"],
        })
        for field in ("acknowledged_at", "false_alarm_at", "escalated_at"):
            if row[field] is not None:
                result[field] = row[field]
        return result

    def list_events(self, limit=50, camera_id=None):
        limit = min(200, max(1, int(limit)))
        with self._connection() as connection:
            if camera_id:
                rows = connection.execute("SELECT * FROM incidents WHERE camera_id = ? ORDER BY timestamp DESC LIMIT ?", (str(camera_id), limit)).fetchall()
            else:
                rows = connection.execute("SELECT * FROM incidents ORDER BY timestamp DESC LIMIT ?", (limit,)).fetchall()
        return [self._decode_row(row) for row in rows]

    def update_status(self, event_id, action):
        columns = {"ack": ("acknowledged", "acknowledged_at"),
                   "escalate": ("escalated", "escalated_at"),
                   "false_alarm": ("false_alarm", "false_alarm_at")}
        if action not in columns:
            raise ValueError("action must be ack, escalate, or false_alarm")
        status, column = columns[action]
        now = time.time()
        with self._connection() as connection:
            cursor = connection.execute(f"UPDATE incidents SET status = ?, {column} = ? WHERE event_id = ?", (status, now, str(event_id)))
            row = connection.execute("SELECT * FROM incidents WHERE event_id = ?", (str(event_id),)).fetchone()
        return self._decode_row(row) if cursor.rowcount and row else None

    def update_payload(self, event_id, patch):
        with self._connection() as connection:
            row = connection.execute("SELECT payload FROM incidents WHERE event_id = ?", (str(event_id),)).fetchone()
            if row is None:
                return False
            payload = json.loads(row["payload"])
            payload.update(patch or {})
            connection.execute("UPDATE incidents SET payload = ? WHERE event_id = ?",
                               (json.dumps(payload, ensure_ascii=False), str(event_id)))
        return True

    def escalate_unacknowledged(self, before_timestamp):
        now = time.time()
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM incidents WHERE status = 'new' AND timestamp <= ?",
                (float(before_timestamp),),
            ).fetchall()
            if rows:
                connection.executemany(
                    "UPDATE incidents SET status = 'escalated', escalated_at = ? WHERE event_id = ? AND status = 'new'",
                    [(now, row["event_id"]) for row in rows],
                )
                rows = connection.execute(
                    "SELECT * FROM incidents WHERE status = 'escalated' AND escalated_at = ? ORDER BY timestamp DESC",
                    (now,),
                ).fetchall()
        return [self._decode_row(row) for row in rows]
