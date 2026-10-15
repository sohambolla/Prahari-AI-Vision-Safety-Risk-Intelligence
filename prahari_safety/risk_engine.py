"""Temporal, track-based safety rules for detections produced by PRAHARI."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
import math
import time
import uuid


def _label(value):
    return " ".join(str(value or "").replace("_", " ").replace("-", " ").casefold().split())


def _matches(label, names):
    normalized = _label(label)
    return any(normalized == _label(name) or _label(name) in normalized for name in names)


def _confidence(detection):
    value = float(detection.get("confidence", 0) or 0)
    return value / 100.0 if value > 1.0 else value


def _box(detection, frame_width, frame_height):
    if isinstance(detection.get("bbox"), (list, tuple)) and len(detection["bbox"]) == 4:
        x1, y1, x2, y2 = (float(value) for value in detection["bbox"])
    elif all(key in detection for key in ("x", "y", "w", "h")):
        x1 = float(detection["x"]) * frame_width / 100.0
        y1 = float(detection["y"]) * frame_height / 100.0
        x2 = x1 + float(detection["w"]) * frame_width / 100.0
        y2 = y1 + float(detection["h"]) * frame_height / 100.0
    else:
        return None
    if not all(math.isfinite(value) for value in (x1, y1, x2, y2)) or x2 <= x1 or y2 <= y1:
        return None
    return (x1, y1, x2, y2)


def _center(box):
    return ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)


def _iou(box_a, box_b):
    x1, y1 = max(box_a[0], box_b[0]), max(box_a[1], box_b[1])
    x2, y2 = min(box_a[2], box_b[2]), min(box_a[3], box_b[3])
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def _box_gap(box_a, box_b):
    dx = max(box_a[0] - box_b[2], box_b[0] - box_a[2], 0.0)
    dy = max(box_a[1] - box_b[3], box_b[1] - box_a[3], 0.0)
    return math.hypot(dx, dy)


def _point_in_polygon(point, polygon):
    if not polygon or len(polygon) < 3:
        return False
    x, y = point
    inside = False
    j = len(polygon) - 1
    for i, current in enumerate(polygon):
        xi, yi = float(current[0]), float(current[1])
        xj, yj = float(polygon[j][0]), float(polygon[j][1])
        if (yi > y) != (yj > y):
            crossing = (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
            if x < crossing:
                inside = not inside
        j = i
    return inside


@dataclass
class _TrackState:
    last_seen: float = 0.0
    last_center: tuple[float, float] | None = None
    still_since: float | None = None
    horizontal_since: float | None = None
    down_still_since: float | None = None
    fire_count: int = 0
    smoke_count: int = 0
    ppe_count: int = 0
    zone_since: dict[str, float] = field(default_factory=dict)
    samples: deque = field(default_factory=lambda: deque(maxlen=8))


class RiskEngine:
    """Convert tracked detections into temporally confirmed safety incidents.

    This rule engine never infers an object that the detector did not return.
    Temporal rules require stable tracker IDs so frame-order changes cannot
    accidentally become an incident.
    """

    def __init__(self, config=None):
        self.config = config or {}
        self.rules = self.config.get("rules", {})
        self._tracks = {}
        self._active = defaultdict(set)
        self._last_emitted = {}
        self._confirm = {}

    def _rule(self, name):
        return self.rules.get(name, {})

    def _state(self, camera_id, detection, class_name, timestamp):
        track_id = detection.get("track_id") or detection.get("tracker_id")
        if not track_id or detection.get("tracking_confirmed") is False:
            # No stable tracker ID (first sighting, YOLO ID flicker, compressed
            # live stream). Fall back to a position-quantized key so temporal
            # rules (PPE confirm_frames, person_down, zone dwell) can still
            # accumulate instead of dropping every untracked detection.
            # 40px grid keeps nearby frames on the same key without merging
            # distinct people across the frame.
            try:
                box = _box(detection, 960.0, 540.0)
                if box is None:
                    return None, None
                cx = int(((box[0] + box[2]) / 2.0) // 40)
                cy = int(((box[1] + box[3]) / 2.0) // 40)
                key = (str(camera_id), f"pos-{cx}x{cy}", _label(class_name))
            except Exception:
                return None, None
            state = self._tracks.setdefault(key, _TrackState())
            state.last_seen = timestamp
            return key, state
        key = (str(camera_id), str(track_id), _label(class_name))
        state = self._tracks.setdefault(key, _TrackState())
        gap = timestamp - state.last_seen if state.last_seen else None
        max_gap = float(self.config.get("max_track_gap_seconds", 1.5))
        if gap is not None and gap > max_gap:
            state.fire_count = 0
            state.smoke_count = 0
            state.ppe_count = 0
            state.last_center = None
            state.still_since = None
            state.horizontal_since = None
            state.down_still_since = None
            state.zone_since.clear()
            state.samples.clear()
        state.last_seen = timestamp
        return key, state

    def evaluate(self, camera_id, detections, zones=None, timestamp=None, frame_size=None):
        now = float(timestamp if timestamp is not None else time.time())
        height, width = (frame_size or (540, 960))[:2]
        width, height = max(1.0, float(width)), max(1.0, float(height))
        normalized_zones = []
        for index, zone in enumerate(zones or self.config.get("zones", {}).get(str(camera_id), [])):
            if isinstance(zone, dict):
                polygon = zone.get("polygon") or zone.get("points") or []
                zone_id = str(zone.get("zone_id") or zone.get("id") or f"zone-{index + 1}")
                zone_type = _label(zone.get("type") or "restricted")
            else:
                polygon, zone_id, zone_type = zone, f"zone-{index + 1}", "restricted"
            polygon = [(float(point[0]) * width / 100.0, float(point[1]) * height / 100.0)
                       for point in polygon if isinstance(point, (list, tuple)) and len(point) >= 2]
            normalized_zones.append((zone_id, zone_type, polygon))

        observed = []
        for detection in detections or []:
            class_name = str(detection.get("class") or detection.get("class_name") or "")
            box = _box(detection, width, height)
            if not class_name or box is None:
                continue
            key, state = self._state(camera_id, detection, class_name, now)
            if state is not None:
                center = _center(box)
                state.samples.append((now, center[0], center[1], box[1], box))
            observed.append({"raw": detection, "class": _label(class_name), "box": box,
                             "center": _center(box), "key": key, "state": state,
                             "track_id": str(detection.get("track_id") or detection.get("tracker_id") or "")})

        people = [item for item in observed if _matches(item["class"], ("person", "worker"))]
        machines = [item for item in observed if _matches(item["class"], ("forklift", "vehicle", "car", "truck", "bus", "mewp"))]
        doors = [item for item in observed if _matches(item["class"], ("door", "emergency exit"))]
        loads = [item for item in observed if _matches(item["class"], self._rule("falling_object").get("labels", ["suspended load", "falling object", "load"]))]
        suspicious = [item for item in observed if _matches(item["class"], self._rule("suspicious_object").get("labels", ["weapon", "ammo box", "unattended bag", "bag"]))]
        candidates = {}

        def add(rule_name, event_type, severity, title, detail, items=(), zone_id=None,
                confidence=None, required_frames=1, extra=None):
            if any(item.get("state") is None for item in items):
                return
            ids = [item["track_id"] for item in items if item.get("track_id")]
            track_key = "+".join(ids) or "untracked"
            key = (str(camera_id), event_type, str(zone_id or ""), track_key)
            candidate = {
                "event_id": str(uuid.uuid4()),
                "event_type": event_type,
                "severity": severity,
                "title": title,
                "detail": detail,
                "camera_id": str(camera_id),
                "zone_id": zone_id,
                "track_id": ids[0] if ids else None,
                "person_id": next((item["raw"].get("person_id") for item in items if item["raw"].get("person_id")), None),
                "machine_id": next((item["raw"].get("machine_id") for item in items if item["raw"].get("machine_id")), None),
                "confidence": max([_confidence(item["raw"]) for item in items] or [0.0]) if confidence is None else confidence,
                "timestamp": now,
                "bbox": list(items[0]["box"]) if items else None,
                "evidence": {"rule": rule_name, "tracks": ids},
                "status": "new",
                "_key": key,
                "_required_frames": max(1, int(required_frames)),
            }
            if extra:
                candidate["evidence"].update(extra)
            candidates[key] = candidate

        person_rule = self._rule("person_down")
        down_ratio = float(person_rule.get("min_width_height_ratio", 1.5))
        for person in people:
            state = person["state"]
            if state is None:
                continue
            box = person["box"]
            box_width, box_height = box[2] - box[0], box[3] - box[1]
            center = person["center"]
            moved = False
            if person_rule.get("enabled", True):
                motion_limit = float(person_rule.get("movement_tolerance_px", 12))
                moved = state.last_center is not None and math.dist(center, state.last_center) > motion_limit
                if moved or state.still_since is None:
                    state.still_since = now
                if box_width / max(1.0, box_height) >= down_ratio:
                    if state.horizontal_since is None:
                        state.horizontal_since = now
                        state.down_still_since = now
                    elif moved:
                        state.down_still_since = now
                    possible_after = float(person_rule.get("possible_fall_seconds", 2.0))
                    critical_after = float(person_rule.get("critical_still_seconds", 5.0))
                    if now - state.horizontal_since >= possible_after:
                        add("person_down", "possible_fall", "warning", "Possible worker fall or slip",
                            f"Track {person['track_id']} is horizontal; confirm visually.", (person,),
                            required_frames=int(person_rule.get("confirm_frames", 1)))
                    if state.down_still_since is not None and now - state.down_still_since >= critical_after:
                        add("person_down", "person_down", "critical", "Worker down and not moving",
                            f"Track {person['track_id']} has remained horizontal and still.", (person,))
                else:
                    state.horizontal_since = None
                    state.down_still_since = None
            state.last_center = center

            ppe = person["raw"].get("ppe") or {}
            helmet = (ppe.get("helmet") or {}).get("detected")
            vest = (ppe.get("vest") or {}).get("detected")
            ppe_rule = self._rule("ppe")
            if ppe_rule.get("enabled", True) and (helmet is False or vest is False):
                state.ppe_count += 1
                if state.ppe_count >= int(ppe_rule.get("confirm_frames", 4)):
                    missing = ", ".join(name for name, ok in (("helmet", helmet), ("high-visibility vest", vest)) if ok is False)
                    add("ppe", "ppe_noncompliance", "critical", "PPE compliance alert",
                        f"Track {person['track_id']}: {missing} not detected.", (person,),
                        required_frames=1)
            else:
                state.ppe_count = 0

        fire_rule = self._rule("fire_smoke")
        fire_labels = set(_label(x) for x in fire_rule.get("labels", ["fire", "smoke"]))
        fire_min_conf = float(fire_rule.get("min_confidence", 0.30))
        fire_frames = int(fire_rule.get("consecutive_frames", 10))
        for item in observed:
            if not fire_rule.get("enabled", True):
                break
            if item["class"] not in fire_labels or item["state"] is None:
                continue
            state = item["state"]
            attr = "fire_count" if item["class"] == "fire" else "smoke_count"
            count = getattr(state, attr)
            if _confidence(item["raw"]) >= fire_min_conf:
                count += 1
            else:
                count = 0
            setattr(state, attr, count)
            if count >= fire_frames:
                title = "Fire detected" if item["class"] == "fire" else "Smoke detected"
                add("fire_smoke", f"{item['class'].replace(' ', '_')}_confirmed", "critical", title,
                    f"{item['class'].title()} persisted for {count} tracked frames.", (item,))

        falling_rule = self._rule("falling_object")
        history_frames = max(3, int(falling_rule.get("history_frames", 5)))
        min_velocity = float(falling_rule.get("min_downward_px_per_second", 240))
        start_y_max = float(falling_rule.get("start_y_max_px", 150))
        near_person = float(falling_rule.get("near_person_px", 200))
        for load in loads:
            if not falling_rule.get("enabled", True):
                break
            state = load["state"]
            if state is None or len(state.samples) < history_frames:
                continue
            samples = list(state.samples)[-history_frames:]
            elapsed = samples[-1][0] - samples[0][0]
            if elapsed <= 0 or samples[0][3] > start_y_max:
                continue
            downward_velocity = (samples[-1][2] - samples[0][2]) / elapsed
            if downward_velocity < min_velocity:
                continue
            load_x, load_y = load["center"]
            nearest = None
            nearest_gap = float("inf")
            for person in people:
                px, py = person["center"]
                distance = math.hypot(px - load_x, py - load_y)
                person_top = person["box"][1]
                if person_top >= load_y and distance < nearest_gap:
                    nearest, nearest_gap = person, distance
            if nearest is not None and nearest_gap <= near_person:
                add("falling_object", "falling_object_near_worker", "critical",
                    "Falling object near worker", f"Tracked load moving down at {downward_velocity:.0f}px/s.",
                    (load, nearest), confidence=_confidence(load["raw"]),
                    extra={"downward_velocity_px_s": round(downward_velocity, 1), "distance_px": round(nearest_gap, 1)})

        proximity_rule = self._rule("vehicle_proximity")
        for person in people:
            if not proximity_rule.get("enabled", True):
                break
            for vehicle in machines:
                gap = _box_gap(person["box"], vehicle["box"])
                if gap <= float(proximity_rule.get("distance_px", 120)):
                    add("vehicle_proximity", "vehicle_pedestrian_proximity",
                        "critical" if gap <= float(proximity_rule.get("critical_distance_px", 50)) else "warning",
                        "Worker close to moving vehicle", f"Track {person['track_id']} is {gap:.0f}px from {vehicle['class']}.",
                        (person, vehicle), required_frames=int(proximity_rule.get("confirm_frames", 3)),
                        extra={"distance_px": round(gap, 1)})

        exit_rule = self._rule("exit_blocked")
        for door in doors:
            if not exit_rule.get("enabled", True):
                break
            for vehicle in machines:
                overlap = _iou(door["box"], vehicle["box"])
                if overlap >= float(exit_rule.get("min_iou", 0.02)):
                    add("exit_blocked", "emergency_exit_blocked", "warning", "Emergency exit obstructed",
                        f"{vehicle['class'].title()} overlaps the door/exit area.", (vehicle, door),
                        required_frames=int(exit_rule.get("confirm_frames", 3)),
                        extra={"overlap_iou": round(overlap, 3)})

        restricted_rule = self._rule("restricted_zone")
        intrusion_frames = int(restricted_rule.get("intrusion_confirm_frames", 4))
        suspicious_labels = restricted_rule.get("suspicious_labels", ["weapon", "ammo box", "unattended bag", "bag"])
        for zone_id, zone_type, polygon in normalized_zones:
            if not restricted_rule.get("enabled", True):
                break
            for person in people:
                if person["state"] is None:
                    continue
                point = ((person["box"][0] + person["box"][2]) / 2.0, person["box"][3])
                inside = _point_in_polygon(point, polygon)
                entry_key = str(zone_id)
                if inside:
                    entered = person["state"].zone_since.setdefault(entry_key, now)
                    add("restricted_zone", "restricted_zone_intrusion", "critical", "Person entered restricted area",
                        f"Track {person['track_id']} crossed zone {zone_id}.", (person,), zone_id,
                        required_frames=intrusion_frames,
                        extra={"dwell_seconds": round(now - entered, 2)})
                else:
                    person["state"].zone_since.pop(entry_key, None)

            for obj in suspicious:
                if obj["state"] is None or not _matches(obj["class"], suspicious_labels):
                    continue
                point = obj["center"]
                if not _point_in_polygon(point, polygon):
                    obj["state"].zone_since.pop(f"suspicious:{zone_id}", None)
                    continue
                nearby_owner = any(_box_gap(obj["box"], person["box"]) <= float(restricted_rule.get("owner_distance_px", 100)) for person in people)
                dwell_key = f"suspicious:{zone_id}"
                if nearby_owner:
                    obj["state"].zone_since.pop(dwell_key, None)
                    continue
                entered = obj["state"].zone_since.setdefault(dwell_key, now)
                dwell = now - entered
                if dwell >= float(restricted_rule.get("suspicious_dwell_seconds", 10.0)):
                    add("suspicious_object", "unattended_suspicious_object", "critical",
                        "Unattended suspicious object in restricted area",
                        f"{obj['class'].title()} has been unattended in zone {zone_id} for {dwell:.0f}s.",
                        (obj,), zone_id, extra={"dwell_seconds": round(dwell, 2)})

        current_keys = set(candidates)
        previously_active = self._active[str(camera_id)]
        emitted = []
        for key, candidate in candidates.items():
            prior_ts, prior_count = self._confirm.get(key, (0.0, 0))
            max_gap = float(self.config.get("max_track_gap_seconds", 1.5))
            count = prior_count + 1 if prior_count and now - prior_ts <= max_gap else 1
            self._confirm[key] = (now, count)
            if count < candidate["_required_frames"]:
                continue
            rule_config = self._rule(candidate["evidence"]["rule"])
            cooldown = float(rule_config.get("cooldown_seconds", 15.0))
            if now - self._last_emitted.get(key, -float("inf")) < cooldown:
                continue
            candidate.pop("_key", None)
            candidate.pop("_required_frames", None)
            candidate["confidence"] = round(float(candidate["confidence"]), 3)
            self._last_emitted[key] = now
            emitted.append(candidate)

        self._active[str(camera_id)] = current_keys
        stale_after = float(self.config.get("track_state_ttl_seconds", 60.0))
        stale_tracks = [key for key, state in self._tracks.items() if now - state.last_seen > stale_after]
        for key in stale_tracks:
            self._tracks.pop(key, None)
        stale_confirm = [key for key, (seen, _) in self._confirm.items() if now - seen > stale_after]
        for key in stale_confirm:
            self._confirm.pop(key, None)
            self._last_emitted.pop(key, None)
        return emitted

    def reset(self, camera_id=None):
        if camera_id is None:
            self._tracks.clear()
            self._active.clear()
            self._last_emitted.clear()
            self._confirm.clear()
            return
        camera_id = str(camera_id)
        for key in [key for key in self._tracks if key[0] == camera_id]:
            self._tracks.pop(key, None)
        self._active.pop(camera_id, None)
        for key in [key for key in self._confirm if key[0] == camera_id]:
            self._confirm.pop(key, None)
            self._last_emitted.pop(key, None)
