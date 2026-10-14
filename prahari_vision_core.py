import cv2
import numpy as np
from ultralytics import YOLOWorld
import supervision as sv
from collections import defaultdict
import time

class PrahariVisionEngine:
    def __init__(self, model_path="yolov8s-world.pt", video_source=0):
        """
        PRAHARI Tvashta Vision Core - 18 Hazards ML Model
        Features: Multi-Object Tracking, Dwell Time, Zone Intrusion, 18 Workplace Hazards.
        """
        # Load state-of-the-art YOLO-World model for high accuracy zero-shot detection
        self.model = YOLOWorld(model_path)

        # Define classes for the 18 hazards
        self.classes = [
            "person", "forklift", "helmet", "safety vest", "fire", "smoke",
            "cell phone", "door", "conveyor belt", "handrail", "suspended load", "MEWP", "vehicle"
        ]
        self.model.set_classes(self.classes)

        self.video_info = sv.VideoInfo.from_video_path(video_source) if isinstance(video_source, str) else None
        self.cap = cv2.VideoCapture(video_source)

        # Supervision Trackers & Annotators
        self.tracker = sv.ByteTrack()
        self.box_annotator = sv.BoxAnnotator(thickness=2)
        self.label_annotator = sv.LabelAnnotator(text_thickness=2, text_scale=0.5)
        self.trace_annotator = sv.TraceAnnotator(thickness=2, trace_length=50)

        # PRAHARI Dwell Time tracking
        self.track_start_times = defaultdict(lambda: time.time())
        self.dwell_times = defaultdict(float)

        # PRAHARI Zone Defintions
        self.hazard_polygon = np.array([[200, 200], [600, 200], [600, 400], [200, 400]])
        self.zone = sv.PolygonZone(polygon=self.hazard_polygon)
        self.zone_annotator = sv.PolygonZoneAnnotator(zone=self.zone, color=sv.Color.RED, thickness=2)

    def run(self):
        print("🚀 Starting PRAHARI Vision Engine with 18 Hazards AI Model...")

        while self.cap.isOpened():
            success, frame = self.cap.read()
            if not success:
                break

            # 1. Run YOLO-World Inference
            results = self.model(frame, verbose=False)[0]

            # 2. Convert to Supervision Detections
            detections = sv.Detections.from_ultralytics(results)

            # 3. Apply ByteTrack (Temporal Tracking on Person class = 0)
            person_detections = detections[detections.class_id == 0]
            person_detections = self.tracker.update_with_detections(person_detections)

            # Hazard State Tracking
            alerts = set()

            # Simulated checks for all 18 Hazards based on bounding boxes
            for i in range(len(detections.xyxy)):
                bbox = detections.xyxy[i]
                cls_id = detections.class_id[i]
                conf = detections.confidence[i]

                # 6. Fire and Smoke Detection
                if cls_id == 4 and conf > 0.3: alerts.add("Fire detected")
                if cls_id == 5 and conf > 0.3: alerts.add("Smoke detected")

                # 4. Emergency Exit Blocked / Escape Route Obstruction
                if cls_id in [1, 12]: # Forklift or Vehicle
                    for j in range(len(detections.xyxy)):
                        if detections.class_id[j] == 7: # Door
                            if self._iou(bbox, detections.xyxy[j]) > 0:
                                alerts.add("Emergency Exit Blocked")

            labels = []
            for i, (bbox, mask, conf, class_id, tracker_id, data) in enumerate(person_detections):
                # Calculate Dwell Time
                if tracker_id not in self.track_start_times:
                    self.track_start_times[tracker_id] = time.time()
                dwell = time.time() - self.track_start_times[tracker_id]
                self.dwell_times[tracker_id] = dwell

                person_alerts = []

                # Check overlaps for PPE and objects
                has_helmet = False
                has_vest = False
                using_phone = False
                near_handrail = False
                for j in range(len(detections.xyxy)):
                    other_bbox = detections.xyxy[j]
                    other_cls = detections.class_id[j]
                    if self._iou(bbox, other_bbox) > 0:
                        if other_cls == 2: has_helmet = True
                        if other_cls == 3: has_vest = True
                        if other_cls == 6: using_phone = True
                        if other_cls == 9: near_handrail = True

                # 10. Missing Hi-Vis Vest
                if not has_vest: person_alerts.append("Missing Hi-Vis Vest")
                # 11. Missing PPE
                if not has_helmet: person_alerts.append("Missing PPE (Helmet)")

                # 8. Inattentiveness (Mobile phone in use)
                if using_phone: alerts.add("Inattentiveness (Mobile phone in use)")

                # 18. Inattentiveness + Wearable Alert
                if using_phone and (not has_helmet or not has_vest):
                    alerts.add("Inattentiveness + Wearable Alert")

                # 7. Handrail Non-compliance at Height
                if not near_handrail and bbox[1] < 100: alerts.add("Handrail Non-compliance at Height")

                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]

                # 5. Falling / Person on the Ground & 16. Warehouse Worker Slip
                if width > height * 1.5:
                    alerts.add("Falling / Person on the Ground")
                    if dwell < 2.0:
                        alerts.add("Warehouse Worker Slip")

                # 17. Working at Height
                if bbox[1] < 50: alerts.add("Working at Height")

                # 12. Person Running
                if dwell < 1.0 and width > 50: alerts.add("Person Running")

                # 1. Vehicle & Pedestrian Separation & 2. Vehicle Proximity Alerts & 15. Vehicle Proximity
                for j in range(len(detections.xyxy)):
                    if detections.class_id[j] == 1: # Forklift
                        if self._distance(bbox, detections.xyxy[j]) < 150:
                            alerts.add("Vehicle Proximity Alerts (Forklift)")
                            alerts.add("Vehicle & Pedestrian Separation Breach")
                    elif detections.class_id[j] == 12: # Vehicle
                        if self._distance(bbox, detections.xyxy[j]) < 150:
                            alerts.add("Vehicle Proximity")

                # 13. Suspended Load / Working Under Suspended Loads
                for j in range(len(detections.xyxy)):
                    if detections.class_id[j] == 10: # Suspended load
                        if self._distance(bbox, detections.xyxy[j]) < 200:
                            alerts.add("Working Under Suspended Loads")

                for j in range(len(detections.xyxy)):
                    if detections.class_id[j] == 11: # MEWP
                        if self._iou(bbox, detections.xyxy[j]) == 0 and self._distance(bbox, detections.xyxy[j]) < 100:
                            alerts.add("MEWP Non-rider proximity risk")

                # 9. Jumping Over Belts
                for j in range(len(detections.xyxy)):
                    if detections.class_id[j] == 8: # Conveyor belt
                        if self._iou(bbox, detections.xyxy[j]) > 0:
                            alerts.add("Jumping Over Belts")

                # 14. Unsafe Position
                if dwell > 10.0 and bbox[1] < 150:
                    alerts.add("Unsafe Position")

                label = f"ID:{tracker_id} | " + ", ".join(person_alerts)
                labels.append(label)

            # 3. Restricted Zone Entry
            zone_triggers = self.zone.trigger(detections=person_detections)
            if np.any(zone_triggers):
                alerts.add("Restricted Zone Entry")

            # 5. Annotate Frame
            annotated_frame = frame.copy()
            annotated_frame = self.trace_annotator.annotate(scene=annotated_frame, detections=person_detections)
            annotated_frame = self.box_annotator.annotate(scene=annotated_frame, detections=detections)
            annotated_frame = self.label_annotator.annotate(scene=annotated_frame, detections=person_detections, labels=labels)
            annotated_frame = self.zone_annotator.annotate(scene=annotated_frame)

            # Overlay PRAHARI Risk Alerts
            y_offset = 50
            for alert in list(alerts)[:5]: # Show top 5 alerts
                cv2.putText(annotated_frame, f"CRITICAL: {alert}!", (50, y_offset),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                y_offset += 30

            cv2.imshow("PRAHARI AI Vision - 18 Hazards", annotated_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        self.cap.release()
        cv2.destroyAllWindows()

    def _iou(self, box1, box2):
        x1 = max(box1[0], box2[0])
        y1 = max(box1[1], box2[1])
        x2 = min(box1[2], box2[2])
        y2 = min(box1[3], box2[3])
        inter_area = max(0, x2 - x1) * max(0, y2 - y1)
        return inter_area

    def _distance(self, box1, box2):
        center1 = ((box1[0]+box1[2])/2, (box1[1]+box1[3])/2)
        center2 = ((box2[0]+box2[2])/2, (box2[1]+box2[3])/2)
        return np.sqrt((center1[0]-center2[0])**2 + (center1[1]-center2[1])**2)

if __name__ == "__main__":
    engine = PrahariVisionEngine(video_source="videos/testing/worker-zone-detection.mp4")
    print("PRAHARI Engine Initialization Complete. Starting inference...")
    engine.run()
