"""Standalone video runner composed from PRAHARI perception, tracking and risk modules."""

from __future__ import annotations

import argparse
import time

from prahari_safety.perception import YoloWorldPerception
from prahari_safety.runtime import SafetyRuntime, read_json
from prahari_safety.tracker import ByteTrackAdapter


class PrahariVisionEngine:
    """Run the shared safety pipeline against a local video or camera source."""

    def __init__(self, model_path="yolov8s-world.pt", video_source=0,
                 camera_id="test-video", config_path="configs/risk_config.json"):
        try:
            import cv2
        except ImportError as exc:
            raise RuntimeError("Install OpenCV to run PRAHARI video validation") from exc
        self.cv2 = cv2
        config = read_json(config_path, {})
        perception_config = config.get("perception", {})
        self.perception = YoloWorldPerception(
            model_path,
            confidence=perception_config.get("confidence", 0.1),
            image_size=perception_config.get("image_size", 960),
        )
        self.tracker = ByteTrackAdapter(**config.get("tracker", {}))
        self.runtime = SafetyRuntime(config_path)
        self.camera_id = str(camera_id)
        self.cap = cv2.VideoCapture(video_source)
        if not self.cap.isOpened():
            raise RuntimeError(f"Could not open video source: {video_source}")
        self.zones = self.runtime.config.get("zones", {}).get(self.camera_id) or [{
            "zone_id": "restricted-test-zone",
            "type": "restricted",
            "polygon": [[20, 37], [60, 37], [60, 74], [20, 74]],
        }]
        self.zone = self.zones[0]

    def _draw(self, frame, detections, events):
        cv2 = self.cv2
        annotated = frame.copy()
        height, width = annotated.shape[:2]
        polygon = [(int(x * width / 100), int(y * height / 100)) for x, y in self.zone["polygon"]]
        import numpy as np
        cv2.polylines(annotated, [np.asarray(polygon, dtype=np.int32)], True, (40, 70, 255), 2)
        for detection in detections:
            x1, y1, x2, y2 = (int(value) for value in detection["bbox"])
            label = f"{detection['class']} {detection.get('track_id') or 'untracked'} {detection['confidence']:.0%}"
            color = (0, 220, 130) if detection.get("tracking_confirmed") else (0, 190, 255)
            cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
            cv2.putText(annotated, label, (x1, max(20, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        for index, event in enumerate(events[:5]):
            text = f"{event['severity'].upper()}: {event['title']}"
            cv2.putText(annotated, text, (16, 28 + 28 * index), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 255), 2)
        return annotated

    def run(self, display=True, max_frames=None):
        print(f"PRAHARI video runner started for {self.camera_id}; site outputs are dry-run.")
        frame_count = 0
        detection_count = 0
        incident_count = 0
        started_at = time.perf_counter()
        try:
            while self.cap.isOpened():
                success, frame = self.cap.read()
                if not success:
                    break
                started = time.perf_counter()
                detections = self.tracker.update(self.perception.infer(frame))
                events = self.runtime.process_frame(self.camera_id, detections, frame, self.zones)
                detection_count += len(detections)
                incident_count += len(events)
                annotated = self._draw(frame, detections, events)
                for event in events:
                    print(f"[{event['severity'].upper()}] {event['title']} ({event['event_id']})")
                if display:
                    self.cv2.imshow("PRAHARI Safety Video Validation", annotated)
                    if self.cv2.waitKey(1) & 0xFF == ord("q"):
                        break
                frame_count += 1
                if max_frames and frame_count >= max_frames:
                    break
                if not display:
                    elapsed = time.perf_counter() - started
                    if elapsed > 0.5 and frame_count % 20 == 0:
                        print(f"Processed {frame_count} frames; latest inference + risk pass {elapsed * 1000:.0f} ms")
        finally:
            self.cap.release()
            if display:
                self.cv2.destroyAllWindows()
            elapsed = max(0.001, time.perf_counter() - started_at)
            print(f"Processed {frame_count} frames ({frame_count / elapsed:.2f} FPS), "
                  f"{detection_count} tracked detections, {incident_count} new incidents.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run PRAHARI risk checks on a video or camera source.")
    parser.add_argument("--source", default="videos/testing/construction/foundation-drilling.webm")
    parser.add_argument("--camera-id", default="test-video")
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    engine = PrahariVisionEngine(video_source=args.source, camera_id=args.camera_id)
    engine.run(display=not args.headless, max_frames=args.max_frames)
