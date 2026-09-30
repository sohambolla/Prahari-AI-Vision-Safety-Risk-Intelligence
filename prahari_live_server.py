"""
PRAHARI AI Vision - Real-Time Multi-Class YOLO Detection + WebSocket Server
Mode 1: Direct browser webcam frame streaming (Zero device conflicts, exact frame sync)
Mode 2: Local video capture fallback via OpenCV
Step 1: Detect ALL objects in frame (person, chair, laptop, bottle, cell phone, etc.)
Step 2: For detected persons, analyze PPE regions (helmet, vest)
Step 3: Stream detection coordinates to React dashboard
"""

import asyncio
import base64
import cv2
import json
import numpy as np
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from ultralytics import YOLO
import uvicorn

app = FastAPI(title="PRAHARI AI Vision Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load YOLO model (detects all 80 COCO classes)
model = YOLO("yolo11n.pt")
COCO_NAMES = model.names

# Object category color mapping
CATEGORY_COLORS = {
    'person': '#3b82f6',
    'bicycle': '#f59e0b',
    'car': '#ef4444',
    'motorcycle': '#f97316',
    'bus': '#ef4444',
    'truck': '#ef4444',
    'traffic light': '#10b981',
    'chair': '#8b5cf6',
    'laptop': '#06b6d4',
    'cell phone': '#06b6d4',
    'bottle': '#a855f7',
    'cup': '#a855f7',
    'book': '#64748b',
    'backpack': '#f59e0b',
    'handbag': '#f59e0b',
    'suitcase': '#f59e0b',
    'dining table': '#6366f1',
    'tv': '#06b6d4',
    'keyboard': '#06b6d4',
    'mouse': '#06b6d4',
    'default': '#94a3b8',
}

PERSON_CLASS_ID = 0

def process_frame(frame, track_first_seen):
    """Run full YOLO multi-class detection and layer PPE analysis on persons."""
    h, w = frame.shape[:2]
    start_t = time.time()

    # Detect all objects (conf=0.25 for responsive live tracking)
    results = model.track(frame, persist=True, verbose=False, conf=0.25)
    inference_ms = round((time.time() - start_t) * 1000, 1)

    all_detections = []

    if results and len(results) > 0 and results[0].boxes is not None:
        boxes = results[0].boxes

        for i, box in enumerate(boxes):
            xyxy = box.xyxy[0].cpu().numpy()
            conf = float(box.conf[0].cpu().numpy())
            cls_id = int(box.cls[0].cpu().numpy())
            track_id = int(box.id[0].cpu().numpy()) if box.id is not None else (i + 1)

            x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])

            x_pct = round((x1 / w) * 100, 2)
            y_pct = round((y1 / h) * 100, 2)
            w_pct = round(((x2 - x1) / w) * 100, 2)
            h_pct = round(((y2 - y1) / h) * 100, 2)

            class_name = COCO_NAMES.get(cls_id, f"class_{cls_id}")
            color = CATEGORY_COLORS.get(class_name, CATEGORY_COLORS['default'])

            det = {
                "track_id": f"OBJ-{track_id:02d}",
                "class": class_name.title(),
                "class_id": cls_id,
                "confidence": round(conf * 100, 1),
                "x": x_pct,
                "y": y_pct,
                "w": w_pct,
                "h": h_pct,
                "color": color,
                "is_person": cls_id == PERSON_CLASS_ID,
            }

            # For Person detections, add PPE sub-checks
            if cls_id == PERSON_CLASS_ID:
                det["track_id"] = f"TRK-{track_id:02d}"

                if track_id not in track_first_seen:
                    track_first_seen[track_id] = time.time()
                dwell_sec = round(time.time() - track_first_seen[track_id], 1)
                det["dwell_time"] = dwell_sec

                foot_x = round(((x1 + x2) / 2 / w) * 100, 2)
                foot_y = round((y2 / h) * 100, 2)
                det["foot_x"] = foot_x
                det["foot_y"] = foot_y

                # Head region
                head_w = round(w_pct * 0.55, 2)
                head_h = round(h_pct * 0.24, 2)
                head_x = round(x_pct + (w_pct - head_w) / 2, 2)
                head_y = round(y_pct, 2)

                # Torso region
                vest_w = round(w_pct * 0.78, 2)
                vest_h = round(h_pct * 0.36, 2)
                vest_x = round(x_pct + (w_pct - vest_w) / 2, 2)
                vest_y = round(y_pct + head_h + 1, 2)

                # Crop head for hardhat color verification
                hx1 = max(0, int(x1 + (x2 - x1) * 0.15))
                hy1 = max(0, int(y1))
                hx2 = min(w, int(x1 + (x2 - x1) * 0.85))
                hy2 = min(h, int(y1 + (y2 - y1) * 0.25))

                has_helmet = False
                helmet_conf = 0.0
                if hy2 > hy1 and hx2 > hx1:
                    head_crop = frame[hy1:hy2, hx1:hx2]
                    if head_crop.size > 0:
                        hsv = cv2.cvtColor(head_crop, cv2.COLOR_BGR2HSV)
                        yellow_mask = cv2.inRange(hsv, np.array([15, 80, 80]), np.array([45, 255, 255]))
                        white_mask = cv2.inRange(hsv, np.array([0, 0, 180]), np.array([180, 40, 255]))
                        orange_mask = cv2.inRange(hsv, np.array([5, 100, 100]), np.array([20, 255, 255]))
                        total_p = head_crop.shape[0] * head_crop.shape[1]
                        helmet_pixels = cv2.countNonZero(yellow_mask) + cv2.countNonZero(white_mask) + cv2.countNonZero(orange_mask)
                        ratio = helmet_pixels / max(1, total_p)
                        has_helmet = ratio > 0.10
                        helmet_conf = round(min(99.0, 60 + ratio * 200), 1)

                # Crop torso for hi-vis vest verification
                vx1 = max(0, int(x1 + (x2 - x1) * 0.1))
                vy1 = max(0, int(y1 + (y2 - y1) * 0.22))
                vx2 = min(w, int(x1 + (x2 - x1) * 0.9))
                vy2 = min(h, int(y1 + (y2 - y1) * 0.58))

                has_vest = False
                vest_conf = 0.0
                if vy2 > vy1 and vx2 > vx1:
                    torso_crop = frame[vy1:vy2, vx1:vx2]
                    if torso_crop.size > 0:
                        hsv_t = cv2.cvtColor(torso_crop, cv2.COLOR_BGR2HSV)
                        hivis_mask = cv2.inRange(hsv_t, np.array([5, 100, 100]), np.array([35, 255, 255]))
                        green_mask = cv2.inRange(hsv_t, np.array([35, 80, 80]), np.array([85, 255, 255]))
                        total_t = torso_crop.shape[0] * torso_crop.shape[1]
                        vest_pixels = cv2.countNonZero(hivis_mask) + cv2.countNonZero(green_mask)
                        vest_ratio = vest_pixels / max(1, total_t)
                        has_vest = vest_ratio > 0.08
                        vest_conf = round(min(99.0, 55 + vest_ratio * 220), 1)

                risk_level = "safe" if (has_helmet and has_vest) else ("warning" if (has_helmet or has_vest) else "critical")

                det["risk_level"] = risk_level
                det["ppe"] = {
                    "helmet": {
                        "detected": has_helmet,
                        "confidence": helmet_conf,
                        "type": "Hardhat Detected" if has_helmet else "NO HARDHAT",
                        "box": {"x": head_x, "y": head_y, "w": head_w, "h": head_h}
                    },
                    "vest": {
                        "detected": has_vest,
                        "confidence": vest_conf,
                        "type": "Hi-Vis Vest" if has_vest else "NO VEST",
                        "box": {"x": vest_x, "y": vest_y, "w": vest_w, "h": vest_h}
                    },
                    "harness": {
                        "detected": False,
                        "confidence": 0.0,
                        "type": "NOT DETECTED"
                    }
                }
            else:
                det["risk_level"] = "object"

            all_detections.append(det)

    return all_detections, inference_ms

@app.get("/")
def read_root():
    return {
        "status": "online",
        "system": "PRAHARI AI Vision Intelligence Server",
        "version": "2.1.0",
        "mode": "Live Camera Object Detection + PPE Scanner",
        "classes": len(COCO_NAMES),
    }

@app.websocket("/ws/vision/{camera_id}")
async def websocket_vision_feed(websocket: WebSocket, camera_id: str):
    await websocket.accept()
    print(f"[STREAM] Client connected for live camera: {camera_id}")

    track_first_seen = {}
    cap = None

    try:
        # Check if client sends image frames or if we should open local OpenCV capture
        while True:
            # Check for client-sent frame with short timeout
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.08)
                data = json.loads(msg)

                # Client sent base64 frame from browser webcam
                if "image" in data and data["image"]:
                    b64_str = data["image"]
                    if "," in b64_str:
                        b64_str = b64_str.split(",")[1]
                    img_bytes = base64.b64decode(b64_str)
                    np_arr = np.frombuffer(img_bytes, np.uint8)
                    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                    if frame is not None:
                        detections, inference_ms = process_frame(frame, track_first_seen)
                        payload = {
                            "camera_id": camera_id,
                            "timestamp": round(time.time(), 2),
                            "inference_ms": inference_ms,
                            "fps": round(1000 / max(1, inference_ms + 10), 1),
                            "total_detections": len(detections),
                            "detections": detections,
                        }
                        await websocket.send_text(json.dumps(payload))
                        continue
            except asyncio.TimeoutError:
                pass

            # Fallback: Local OpenCV capture for camera_id
            if cap is None:
                source = 0 if camera_id == "cam-webcam" else f"videos/{camera_id.replace('cam-', 'video_')}.mp4"
                cap = cv2.VideoCapture(source)

            if cap and cap.isOpened():
                success, frame = cap.read()
                if success and frame is not None:
                    detections, inference_ms = process_frame(frame, track_first_seen)
                    payload = {
                        "camera_id": camera_id,
                        "timestamp": round(time.time(), 2),
                        "inference_ms": inference_ms,
                        "fps": round(cap.get(cv2.CAP_PROP_FPS) or 30.0, 1),
                        "total_detections": len(detections),
                        "detections": detections,
                    }
                    await websocket.send_text(json.dumps(payload))
                elif isinstance(source, str):
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

            await asyncio.sleep(0.04)

    except WebSocketDisconnect:
        print(f"[DISCONNECT] Client disconnected: {camera_id}")
    except Exception as e:
        print(f"[ERROR] {camera_id}: {e}")
    finally:
        if cap:
            cap.release()

if __name__ == "__main__":
    print("=" * 60)
    print("PRAHARI AI Vision Intelligence Server v2.1")
    print("Multi-Class Object Detection + PPE Safety Scanner (Live Webcam Only)")
    print(f"Loaded {len(COCO_NAMES)} COCO classes")
    print("=" * 60)
    uvicorn.run("prahari_live_server:app", host="0.0.0.0", port=8000, reload=False)
