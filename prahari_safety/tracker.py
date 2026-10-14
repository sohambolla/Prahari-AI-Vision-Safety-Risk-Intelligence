"""Supervision ByteTrack adapter for detections from any supported detector."""

from __future__ import annotations


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
