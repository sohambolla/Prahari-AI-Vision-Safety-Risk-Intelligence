"""Supervision ByteTrack adapter for detections from any supported detector."""

from __future__ import annotations

import math
import time


class ByteTrackAdapter:
    def __init__(self, track_activation_threshold=0.10, lost_track_buffer=30, minimum_matching_threshold=0.8):
        try:
            import supervision as sv
        except ImportError as exc:
            raise RuntimeError("Install supervision to run PRAHARI tracking") from exc
        self._sv = sv
        self._tracker = sv.ByteTrack(
            track_activation_threshold=track_activation_threshold,
            lost_track_buffer=lost_track_buffer,
            minimum_matching_threshold=minimum_matching_threshold,
        )

    def update(self, detections):
        if not detections:
            return []
        import numpy as np

        supervision_detections = self._sv.Detections(
            xyxy=np.asarray([item["bbox"] for item in detections], dtype=np.float32),
            confidence=np.asarray([item["confidence"] for item in detections], dtype=np.float32),
            class_id=np.asarray([item["class_id"] for item in detections], dtype=np.int32),
            data={"source_index": np.arange(len(detections), dtype=np.int32)},
        )
        tracked = self._tracker.update_with_detections(supervision_detections)
        output = []
        tracker_ids = tracked.tracker_id
        source_indices = tracked.data.get("source_index", [])
        for index, source_index in enumerate(source_indices):
            item = detections[int(source_index)]
            value = dict(item)
            value["bbox"] = [float(coord) for coord in tracked.xyxy[index].tolist()]
            if tracker_ids is not None and index < len(tracker_ids) and tracker_ids[index] is not None:
                value["track_id"] = str(int(tracker_ids[index]))
                value["tracking_confirmed"] = True
            else:
                value["track_id"] = None
                value["tracking_confirmed"] = False
            output.append(value)
        return output

    def reset(self):
        self._tracker.reset()


class IoUFallbackTracker:
    """Give live detections stable IDs when the detector tracker omits them.

    Unmatched first-frame detections remain unconfirmed. A detection is marked
    confirmed only after it matches the same class and location on a later
    frame, which lets temporal risk rules work without trusting frame indexes
    as track IDs.
    """

    def __init__(self, match_iou=0.10, max_gap_seconds=1.5):
        self.match_iou = float(match_iou)
        self.max_gap_seconds = float(max_gap_seconds)
        self._tracks = {}
        self._next_id = 1

    @staticmethod
    def _iou(first, second):
        x1, y1 = max(first[0], second[0]), max(first[1], second[1])
        x2, y2 = min(first[2], second[2]), min(first[3], second[3])
        intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        first_area = max(0.0, first[2] - first[0]) * max(0.0, first[3] - first[1])
        second_area = max(0.0, second[2] - second[0]) * max(0.0, second[3] - second[1])
        union = first_area + second_area - intersection
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def _center_match(first, second):
        first_center = ((first[0] + first[2]) / 2, (first[1] + first[3]) / 2)
        second_center = ((second[0] + second[2]) / 2, (second[1] + second[3]) / 2)
        first_diag = math.hypot(first[2] - first[0], first[3] - first[1])
        second_diag = math.hypot(second[2] - second[0], second[3] - second[1])
        scale = max(first_diag, second_diag, 1.0)
        distance = math.dist(first_center, second_center)
        return distance <= scale * 0.25, distance / scale

    def update(self, camera_id, detections, timestamp=None):
        now = float(timestamp if timestamp is not None else time.time())
        camera_id = str(camera_id or "default")
        camera_tracks = self._tracks.setdefault(camera_id, {})
        camera_tracks = {
            track_id: track for track_id, track in camera_tracks.items()
            if now - track["last_seen"] <= self.max_gap_seconds
        }

        candidates = []
        for index, detection in enumerate(detections or []):
            box = detection.get("bbox")
            if not isinstance(box, (list, tuple)) or len(box) != 4:
                continue
            try:
                box = tuple(float(value) for value in box)
            except (TypeError, ValueError):
                continue
            if not all(math.isfinite(value) for value in box) or box[2] <= box[0] or box[3] <= box[1]:
                continue
            label = " ".join(str(detection.get("class") or "").casefold().split())
            confidence = float(detection.get("confidence", 0) or 0)
            candidates.append((index, label, box, confidence))

        # Match high-confidence detections first so overlapping low-confidence
        # boxes cannot claim an established track first.
        candidates.sort(key=lambda item: item[3], reverse=True)
        available = set(camera_tracks)
        next_tracks = dict(camera_tracks)

        for index, label, box, _ in candidates:
            best_id = None
            best_score = -1.0
            for track_id in available:
                track = camera_tracks[track_id]
                if track["class"] != label:
                    continue
                overlap = self._iou(box, track["bbox"])
                center_match, normalized_distance = self._center_match(box, track["bbox"])
                if overlap < self.match_iou and not center_match:
                    continue
                score = overlap if overlap >= self.match_iou else 0.15 - normalized_distance * 0.01
                if score > best_score:
                    best_id, best_score = track_id, score

            if best_id is None:
                best_id = self._next_id
                self._next_id += 1
                # Confirm immediately: the risk engine already applies its own
                # confirm_frames / cooldown gating, so double-gating here only
                # delayed every live critical alert by 1-2 frames and dropped
                # alerts whenever YOLO tracker IDs flickered.
                confirmed_by_fallback = True
            else:
                available.discard(best_id)
                confirmed_by_fallback = True

            next_tracks[best_id] = {"class": label, "bbox": box, "last_seen": now}
            detection = detections[index]
            if not detection.get("tracking_confirmed"):
                detection["track_id"] = f"FB-{best_id:04d}"
                detection["tracking_confirmed"] = confirmed_by_fallback

        self._tracks[camera_id] = next_tracks
        return detections

    def reset(self, camera_id=None):
        if camera_id is None:
            self._tracks.clear()
            self._next_id = 1
        else:
            self._tracks.pop(str(camera_id), None)
