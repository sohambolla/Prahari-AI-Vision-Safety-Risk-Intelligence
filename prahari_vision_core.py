import cv2
import numpy as np
from ultralytics import YOLO
import supervision as sv
from collections import defaultdict
import time

class PrahariVisionEngine:
    def __init__(self, model_path="yolo11n.pt", video_source=0):
        """
        PRAHARI Tvashta Vision Core
        Features: Multi-Object Tracking, Dwell Time, Zone Intrusion, Metrics Distance.
        """
        # Load state-of-the-art YOLO model (YOLO11 natively supports tracking)
        self.model = YOLO(model_path)
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

        # PRAHARI Zone Defintion (e.g. Unprotected Edge / High Risk Area)
        # Using a polygon to define the hazard zone
        self.hazard_polygon = np.array([
            [200, 200], [600, 200], [600, 400], [200, 400]
        ])
        self.zone = sv.PolygonZone(polygon=self.hazard_polygon)
        self.zone_annotator = sv.PolygonZoneAnnotator(
            zone=self.zone, 
            color=sv.Color.RED, 
            thickness=2,
            text_thickness=1,
            text_scale=0.5
        )

    def calculate_distance_to_edge(self, bbox, polygon):
        """
        Calculate approximate 2D pixel distance from the bottom-center 
        of a bounding box to the nearest edge of the hazard polygon.
        (For PRAHARI 0.8m real-world calibration, you would apply a homography matrix here).
        """
        x1, y1, x2, y2 = bbox
        bottom_center = (int((x1 + x2) / 2), int(y2))
        
        # Simple point-to-polygon distance (cv2.pointPolygonTest)
        dist = cv2.pointPolygonTest(polygon, bottom_center, True)
        return abs(dist) # Absolute pixel distance

    def run(self):
        print("🚀 Starting PRAHARI Vision Engine...")
        
        while self.cap.isOpened():
            success, frame = self.cap.read()
            if not success:
                break

            # 1. Run YOLO Inference
            results = self.model(frame, verbose=False)[0]
            
            # 2. Convert to Supervision Detections
            detections = sv.Detections.from_ultralytics(results)
            
            # Filter for specific classes (e.g., Person class=0 in COCO)
            detections = detections[detections.class_id == 0]

            # 3. Apply ByteTrack (Temporal Tracking)
            detections = self.tracker.update_with_detections(detections)

            labels = []
            for i, (bbox, mask, conf, class_id, tracker_id, data) in enumerate(detections):
                # Calculate Dwell Time
                if tracker_id not in self.track_start_times:
                    self.track_start_times[tracker_id] = time.time()
                
                dwell = time.time() - self.track_start_times[tracker_id]
                self.dwell_times[tracker_id] = dwell
                
                # Calculate Distance to Hazard Edge
                dist = self.calculate_distance_to_edge(bbox, self.hazard_polygon)
                
                # Generate PRAHARI Label
                label = f"ID:{tracker_id} | {dwell:.1f}s | Edge:{dist:.0f}px"
                labels.append(label)

            # 4. Check Zone Intrusion (Risk Engine)
            zone_triggers = self.zone.trigger(detections=detections)

            # 5. Annotate Frame
            annotated_frame = frame.copy()
            annotated_frame = self.trace_annotator.annotate(scene=annotated_frame, detections=detections)
            annotated_frame = self.box_annotator.annotate(scene=annotated_frame, detections=detections)
            annotated_frame = self.label_annotator.annotate(scene=annotated_frame, detections=detections, labels=labels)
            annotated_frame = self.zone_annotator.annotate(scene=annotated_frame)

            # Overlay PRAHARI Risk Alerts
            if np.any(zone_triggers):
                cv2.putText(annotated_frame, "CRITICAL: WORKER IN HAZARD ZONE!", (50, 50), 
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

            cv2.imshow("PRAHARI AI Vision Intelligence", annotated_frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
        self.cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    # To test using webcam:
    # engine = PrahariVisionEngine(video_source=0)
    
    # Or to test using a video file from the repo:
    # engine = PrahariVisionEngine(video_source="./videos/video_2.mp4")
    
    # engine.run()
    print("PRAHARI Engine Initialization Complete. Call engine.run() to start.")
