"""
PRAHARI AI Vision - Real-Time Multi-Class YOLO Detection + WebSocket Server
Enhanced with:
1. Robust Hardhat / Helmet discrimination (Hair/Skin vs Industrial Polymer Hardhat)
2. Fluorescent Hi-Vis Safety Vest discrimination (Neon Green/Orange vs casual clothing)
3. High-Voltage Bright Neon Bounding Box Colors (#ff1744 Red, #00e676 Green, #00e5ff Cyan)
"""

import asyncio
import base64
import cv2
import json
import math
import numpy as np
import os
import time
from fastapi import Body, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO, YOLOWorld
try:
    from ultralytics import YOLOE
except ImportError:
    YOLOE = None
import uvicorn
from prahari_safety.runtime import SafetyRuntime

app = FastAPI(title="PRAHARI AI Vision Engine")
safety_runtime = SafetyRuntime()
SAFETY_ALERT_CLIENTS = set()
SEEN_INCIDENT_IDS = set()
app.mount("/incidents", StaticFiles(directory=str(safety_runtime.store.root)), name="incidents")

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
COCO_ID_BY_NAME = {name: class_id for class_id, name in COCO_NAMES.items()}
VEHICLE_CLASS_NAMES = ["car", "truck", "bus"]
VEHICLE_CONFIRMATION_MIN_CONF = 0.30
VEHICLE_CONFIRMATION_MIN_IOU = 0.50

# Verify COCO phone detections against the project's existing open-vocabulary
# vehicle model. This is only called when YOLO11n proposes a cell phone.
vehicle_model = None
vehicle_model_path = os.path.join(os.path.dirname(__file__), "yolov8s-world.pt")
if os.path.isfile(vehicle_model_path):
    try:
        vehicle_model = YOLOWorld(vehicle_model_path)
        vehicle_model.set_classes(VEHICLE_CLASS_NAMES)
        vehicle_model.predict(np.zeros((360, 640, 3), dtype=np.uint8), verbose=False, conf=VEHICLE_CONFIRMATION_MIN_CONF)
    except Exception as exc:
        vehicle_model = None
        print(f"[WARN] Vehicle confirmation model unavailable: {exc}")

MODEL_LABEL = "YOLO11n"
if vehicle_model is not None:
    MODEL_LABEL += " + vehicle verification"

open_vocabulary_model = None
open_vocabulary_error = ""
active_open_vocabulary_prompts = []
active_open_vocabulary_camera = None
failed_open_vocabulary_prompts = []
if YOLOE is not None:
    try:
        ovs_model_path = os.environ.get("PRAHARI_OVS_MODEL", "weights/yoloe-11s-seg.pt")
        open_vocabulary_model = YOLOE(ovs_model_path)
        MODEL_LABEL += " + YOLOE segmentation"
    except Exception as exc:
        open_vocabulary_error = str(exc)
        print(f"[WARN] Open-vocabulary segmentation unavailable: {exc}")
else:
    open_vocabulary_error = "Install ultralytics 8.4.0 or newer to enable YOLOE segmentation."

try:
    OVS_IMAGE_SIZE = min(1280, max(640, int(os.environ.get("PRAHARI_OVS_IMGSZ", "960"))))
except ValueError:
    OVS_IMAGE_SIZE = 960

# Object category color mapping (Ultra-bright vibrant neon palette)
CATEGORY_COLORS = {
    'person': '#ff1744',      # Default red until PPE verified
    'bicycle': '#ff9100',
    'car': '#ff1744',
    'motorcycle': '#ff9100',
    'bus': '#ff1744',
    'truck': '#ff1744',
    'traffic light': '#00e676',
    'chair': '#00e5ff',
    'laptop': '#00e5ff',
    'cell phone': '#00e5ff',
    'bottle': '#d500f9',
    'cup': '#d500f9',
    'book': '#00e5ff',
    'backpack': '#ff9100',
    'handbag': '#ff9100',
    'suitcase': '#ff9100',
    'dining table': '#2979ff',
    'tv': '#00e5ff',
    'keyboard': '#00e5ff',
    'mouse': '#00e5ff',
    'default': '#00e5ff',
}

PERSON_CLASS_ID = 0
AMBIGUOUS_PHONE_CLASS = COCO_ID_BY_NAME.get("cell phone")


def box_iou(box1, box2):
    """Return intersection-over-union for two xyxy boxes."""
    x1 = max(float(box1[0]), float(box2[0]))
    y1 = max(float(box1[1]), float(box2[1]))
    x2 = min(float(box1[2]), float(box2[2]))
    y2 = min(float(box1[3]), float(box2[3]))
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area1 = max(0.0, float(box1[2]) - float(box1[0])) * max(0.0, float(box1[3]) - float(box1[1]))
    area2 = max(0.0, float(box2[2]) - float(box2[0])) * max(0.0, float(box2[3]) - float(box2[1]))
    union = area1 + area2 - intersection
    return intersection / union if union > 0 else 0.0

def analyze_head_ppe(head_crop):
    """
    Robust Computer Vision filter to distinguish:
    - Normal Human Hair / Exposed Head / Skin -> NO HARDHAT
    - Industrial Safety Hardhats (Saturated Yellow, Orange, Blue, Red) -> HARDHAT DETECTED
    """
    if head_crop is None or head_crop.size == 0 or head_crop.shape[0] < 8 or head_crop.shape[1] < 8:
        return False, 0.0

    hsv = cv2.cvtColor(head_crop, cv2.COLOR_BGR2HSV)
    total_p = head_crop.shape[0] * head_crop.shape[1]

    # 1. Dark Hair Mask (black / dark brown hair)
    dark_hair_mask = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 255, 75]))

    # 2. Exposed Facial Skin / Forehead Mask
    skin_mask = cv2.inRange(hsv, np.array([0, 30, 60]), np.array([25, 160, 240]))

    # 3. Industrial Safety Hardhat Colors (High saturation + High brightness)
    # Industrial Safety Yellow
    yellow_hat = cv2.inRange(hsv, np.array([18, 110, 110]), np.array([36, 255, 255]))
    # Industrial Safety Orange
    orange_hat = cv2.inRange(hsv, np.array([7, 140, 130]), np.array([18, 255, 255]))
    # Industrial Safety Blue
    blue_hat = cv2.inRange(hsv, np.array([95, 120, 90]), np.array([130, 255, 255]))
    # Industrial Safety Red
    red_hat1 = cv2.inRange(hsv, np.array([0, 150, 110]), np.array([6, 255, 255]))
    red_hat2 = cv2.inRange(hsv, np.array([172, 150, 110]), np.array([180, 255, 255]))
    red_hat = cv2.bitwise_or(red_hat1, red_hat2)

    hat_mask = yellow_hat | orange_hat | blue_hat | red_hat

    hat_pixels = cv2.countNonZero(hat_mask)
    hair_pixels = cv2.countNonZero(dark_hair_mask)
    skin_pixels = cv2.countNonZero(skin_mask)

    hat_ratio = hat_pixels / max(1, total_p)
    hair_ratio = hair_pixels / max(1, total_p)

    # If top of the head is dominated by exposed hair or skin, NO helmet
    if hair_ratio > 0.20 or (hair_pixels + skin_pixels) > (hat_pixels * 1.5):
        return False, 0.0

    # Must have at least 22% coverage of saturated industrial helmet polymer
    if hat_ratio >= 0.22 and hat_pixels > (hair_pixels * 1.2):
        conf = round(min(99.0, 72.0 + hat_ratio * 100), 1)
        return True, conf

    return False, 0.0

def analyze_torso_ppe(torso_crop):
    """
    Robust Computer Vision filter to distinguish:
    - Normal casual clothes / shirts / t-shirts -> NO VEST
    - Fluorescent Neon Hi-Vis Safety Vests (Day-glo Green / Day-glo Orange) -> SAFETY VEST DETECTED
    """
    if torso_crop is None or torso_crop.size == 0 or torso_crop.shape[0] < 10 or torso_crop.shape[1] < 10:
        return False, 0.0

    hsv = cv2.cvtColor(torso_crop, cv2.COLOR_BGR2HSV)
    total_t = torso_crop.shape[0] * torso_crop.shape[1]

    # Fluorescent Hi-Vis Neon Yellow/Green
    hivis_green = cv2.inRange(hsv, np.array([28, 130, 150]), np.array([55, 255, 255]))

    # Fluorescent Hi-Vis Day-Glo Orange
    hivis_orange = cv2.inRange(hsv, np.array([8, 160, 160]), np.array([18, 255, 255]))

    vest_mask = hivis_green | hivis_orange
    vest_pixels = cv2.countNonZero(vest_mask)
    vest_ratio = vest_pixels / max(1, total_t)

    # Must cover at least 22% of torso in neon high-luminance colors
    if vest_ratio >= 0.22:
        conf = round(min(99.0, 70.0 + vest_ratio * 100), 1)
        return True, conf

    return False, 0.0

def normalize_open_vocabulary_prompts(prompts):
    """Return a bounded, de-duplicated prompt list received from the dashboard."""
    if not isinstance(prompts, list):
        return []

    normalized = []
    for prompt in prompts:
        if not isinstance(prompt, str):
            continue
        prompt = " ".join(prompt.strip().split())[:64]
        if prompt and prompt.lower() != "person" and prompt.casefold() not in {p.casefold() for p in normalized}:
            normalized.append(prompt)
        if len(normalized) >= 12:
            break
    return normalized


OPEN_VOCABULARY_SYNONYMS = {
    "screen": ("computer monitor", "monitor", "computer display"),
    "monitor": ("computer monitor", "computer screen", "display"),
    "display": ("computer monitor", "screen"),
    "computer monitor": ("monitor", "computer screen"),
    "computer screen": ("computer monitor", "screen"),
    "computer display": ("computer monitor", "screen"),
    "cup": ("drinking cup", "mug"),
    "keyboard": ("computer keyboard",),
    "mouse": ("computer mouse",),
    "bottle": ("water bottle", "drinking bottle"),
    "water bottle": ("bottle", "drinking bottle"),
    "mobile phone": ("smartphone", "cell phone"),
    "cell phone": ("smartphone", "mobile phone"),
    "smartphone": ("mobile phone", "cell phone"),
    "gear": ("cogwheel",),
    "bearing": ("ball bearing",),
    "bolt": ("hex bolt",),
    "washer": ("metal washer",),
}
MAX_EXPANDED_OVS_PROMPTS = 18
SAFETY_MONITOR_PROMPTS = (
    "fire", "smoke", "suspended load", "forklift", "safety helmet", "safety vest",
    "safety gloves", "door", "conveyor belt", "handrail", "MEWP", "weapon",
    "ammo box", "unattended bag", "machine",
)
SCREEN_PROMPT_TERMS = {
    "screen", "monitor", "display", "computer monitor", "computer screen", "computer display",
}
SCREEN_HARD_NEGATIVES = ("whiteboard", "poster")


def get_screen_hard_negatives(prompts):
    if any(prompt.casefold() in SCREEN_PROMPT_TERMS for prompt in prompts):
        return SCREEN_HARD_NEGATIVES
    return ()


def expand_open_vocabulary_prompts(prompts):
    """Add a small set of visual synonyms while keeping user labels first."""
    expanded = list(prompts[:MAX_EXPANDED_OVS_PROMPTS])
    seen = {prompt.casefold() for prompt in expanded}
    for negative in get_screen_hard_negatives(prompts):
        if negative.casefold() not in seen and len(expanded) < MAX_EXPANDED_OVS_PROMPTS:
            expanded.append(negative)
            seen.add(negative.casefold())
    for prompt in prompts:
        aliases = OPEN_VOCABULARY_SYNONYMS.get(prompt.casefold(), ())
        for alias in aliases:
            normalized_alias = alias.casefold()
            if normalized_alias in seen:
                continue
            expanded.append(alias)
            seen.add(normalized_alias)
            if len(expanded) >= MAX_EXPANDED_OVS_PROMPTS:
                return expanded
    return expanded


def canonicalize_open_vocabulary_label(label, requested_prompts):
    """Show the label the operator requested when a matching synonym fires."""
    normalized_label = " ".join(str(label).split()).casefold()
    requested_by_name = {prompt.casefold(): prompt for prompt in requested_prompts}
    if normalized_label in requested_by_name:
        return requested_by_name[normalized_label]
    for prompt in requested_prompts:
        aliases = OPEN_VOCABULARY_SYNONYMS.get(prompt.casefold(), ())
        if normalized_label in {alias.casefold() for alias in aliases}:
            return prompt
    return label


def mask_polygon_for_result(result, detection_index, width, height):
    """Convert an instance mask contour to a compact 0..100 SVG polygon."""
    if result.masks is None or detection_index >= len(result.masks.xy):
        return None
    contour = result.masks.xy[detection_index]
    if contour is None or len(contour) < 3:
        return None

    contour = np.asarray(contour, dtype=np.float32).reshape(-1, 1, 2)
    perimeter = cv2.arcLength(contour, True)
    simplified = cv2.approxPolyDP(contour, max(1.5, perimeter * 0.005), True).reshape(-1, 2)
    if len(simplified) < 3:
        return None
    return [
        [round(float(x) / width * 100, 2), round(float(y) / height * 100, 2)]
        for x, y in simplified[:120]
    ]


def process_frame(frame, track_first_seen, target_prompts=None, confidence=0.15, camera_id=None):
    """Track fixed COCO objects or text-prompted instances and analyze PPE."""
    global active_open_vocabulary_prompts, active_open_vocabulary_camera
    global failed_open_vocabulary_prompts, open_vocabulary_error
    h, w = frame.shape[:2]
    start_t = time.time()

    prompts = normalize_open_vocabulary_prompts(target_prompts)
    try:
        confidence = min(0.75, max(0.05, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.15
    if not math.isfinite(confidence):
        confidence = 0.15
    # Keep the safety rule engine supplied with its core visual classes while
    # still accepting arbitrary operator prompts in the same segmentation pass.
    use_open_vocabulary = bool((prompts or SAFETY_MONITOR_PROMPTS) and open_vocabulary_model is not None)
    if use_open_vocabulary:
        expanded_prompts = expand_open_vocabulary_prompts(prompts)
        classes = ["person", *expanded_prompts]
        seen_classes = {label.casefold() for label in classes}
        for label in SAFETY_MONITOR_PROMPTS:
            if label.casefold() not in seen_classes:
                classes.append(label)
                seen_classes.add(label.casefold())
        if classes == failed_open_vocabulary_prompts:
            use_open_vocabulary = False
        else:
            try:
                prompts_changed = classes != active_open_vocabulary_prompts
                camera_changed = camera_id != active_open_vocabulary_camera
                if prompts_changed:
                    open_vocabulary_model.set_classes(classes)
                    active_open_vocabulary_prompts = classes
                    failed_open_vocabulary_prompts = []
                    open_vocabulary_error = ""
                if prompts_changed or camera_changed:
                    predictor = getattr(open_vocabulary_model, "predictor", None)
                    for tracker in getattr(predictor, "trackers", []):
                        tracker.reset()
                    active_open_vocabulary_camera = camera_id
                    safety_runtime.risk_engine.reset(camera_id)
                results = open_vocabulary_model.track(
                    frame,
                    persist=True,
                    verbose=False,
                    conf=confidence,
                    imgsz=OVS_IMAGE_SIZE,
                    tracker="configs/prahari_ovs_tracker.yaml",
                )
            except Exception as exc:
                open_vocabulary_error = str(exc)
                failed_open_vocabulary_prompts = classes
                print(f"[WARN] Open-vocabulary prompt inference failed: {exc}")
                use_open_vocabulary = False

    if not use_open_vocabulary:
        # Keep the proven COCO/PPE pipeline available when no prompt is selected
        # or when the optional open-vocabulary model cannot initialize.
        results = model.track(frame, persist=True, verbose=False, conf=0.25)

    all_detections = []
    vehicle_overrides = {}

    if results and len(results) > 0 and results[0].boxes is not None:
        result = results[0]
        boxes = result.boxes
        result_names = result.names if use_open_vocabulary else COCO_NAMES
        candidate_indices = list(range(len(boxes)))
        requested_labels = {prompt.casefold() for prompt in prompts}
        internal_negative_labels = {
            label.casefold() for label in get_screen_hard_negatives(prompts)
            if label.casefold() not in requested_labels
        } if use_open_vocabulary else set()

        # Whiteboards and posters often look like screens to open-vocabulary
        # prompts. Use those labels as internal counter-evidence and suppress a
        # screen candidate when a matching negative box overlaps it strongly.
        if use_open_vocabulary and internal_negative_labels and len(candidate_indices) > 1:
            negative_indices = []
            screen_indices = []
            for index in candidate_indices:
                candidate_class_id = int(boxes[index].cls[0].cpu().numpy())
                candidate_label = str(result_names.get(candidate_class_id, "")).casefold()
                if candidate_label in internal_negative_labels:
                    negative_indices.append(index)
                elif candidate_label in SCREEN_PROMPT_TERMS:
                    screen_indices.append(index)

            suppressed_screen_indices = set()
            for screen_index in screen_indices:
                screen_box = boxes[screen_index].xyxy[0].cpu().numpy()
                screen_confidence = float(boxes[screen_index].conf[0].cpu().numpy())
                for negative_index in negative_indices:
                    negative_box = boxes[negative_index].xyxy[0].cpu().numpy()
                    negative_confidence = float(boxes[negative_index].conf[0].cpu().numpy())
                    if box_iou(screen_box, negative_box) >= 0.45 and negative_confidence >= max(0.20, screen_confidence * 0.60):
                        suppressed_screen_indices.add(screen_index)
                        break

            candidate_indices = [
                index for index in candidate_indices
                if index not in suppressed_screen_indices
                and not (
                    int(boxes[index].cls[0].cpu().numpy()) in result_names
                    and str(result_names[int(boxes[index].cls[0].cpu().numpy())]).casefold() in internal_negative_labels
                )
            ]

        if use_open_vocabulary and len(candidate_indices) > 1:
            # Prompt synonyms can return the same physical item under two
            # labels. Suppress only near-identical boxes and keep the stronger one.
            ranked = sorted(
                candidate_indices,
                key=lambda index: float(boxes[index].conf[0].cpu().numpy()),
                reverse=True,
            )
            kept = []
            for index in ranked:
                candidate_box = boxes[index].xyxy[0].cpu().numpy()
                if any(box_iou(candidate_box, boxes[other].xyxy[0].cpu().numpy()) > 0.82 for other in kept):
                    continue
                kept.append(index)
            candidate_indices = kept

        phone_candidates = []
        if not use_open_vocabulary and vehicle_model is not None and AMBIGUOUS_PHONE_CLASS is not None:
            phone_candidates = [
                (index, box, box.xyxy[0].cpu().numpy())
                for index, box in enumerate(boxes)
                if int(box.cls[0].cpu().numpy()) == AMBIGUOUS_PHONE_CLASS
            ]

        if phone_candidates:
            try:
                vehicle_results = vehicle_model.predict(frame, verbose=False, conf=VEHICLE_CONFIRMATION_MIN_CONF)[0]
                if vehicle_results.boxes is not None:
                    for vehicle_box in vehicle_results.boxes:
                        vehicle_cls_id = int(vehicle_box.cls[0].cpu().numpy())
                        vehicle_name = vehicle_model.names.get(vehicle_cls_id, "vehicle")
                        if vehicle_name not in VEHICLE_CLASS_NAMES:
                            continue

                        vehicle_conf = float(vehicle_box.conf[0].cpu().numpy())
                        vehicle_xyxy = vehicle_box.xyxy[0].cpu().numpy()
                        for phone_index, _, phone_xyxy in phone_candidates:
                            overlap = box_iou(phone_xyxy, vehicle_xyxy)
                            if overlap < VEHICLE_CONFIRMATION_MIN_IOU:
                                continue
                            if vehicle_conf > vehicle_overrides.get(phone_index, {}).get("confidence", 0):
                                vehicle_overrides[phone_index] = {
                                    "class_name": vehicle_name,
                                    "class_id": COCO_ID_BY_NAME.get(vehicle_name, AMBIGUOUS_PHONE_CLASS),
                                    "confidence": vehicle_conf,
                                    "xyxy": vehicle_xyxy,
                                }
            except Exception as exc:
                print(f"[WARN] Vehicle confirmation skipped for frame: {exc}")

        for i in candidate_indices:
            box = boxes[i]
            xyxy = box.xyxy[0].cpu().numpy()
            conf = float(box.conf[0].cpu().numpy())
            cls_id = int(box.cls[0].cpu().numpy())
            tracking_confirmed = box.id is not None
            track_id = int(box.id[0].cpu().numpy()) if tracking_confirmed else (i + 1)

            # Replace a phone label only when the vehicle model finds a strongly
            # overlapping car/truck/bus/bike of its own with a matching box.
            vehicle_override = vehicle_overrides.get(i)
            if vehicle_override:
                xyxy = vehicle_override["xyxy"]
                conf = vehicle_override["confidence"]
                cls_id = vehicle_override["class_id"]

            x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])

            x_pct = round((x1 / w) * 100, 2)
            y_pct = round((y1 / h) * 100, 2)
            w_pct = round(((x2 - x1) / w) * 100, 2)
            h_pct = round(((y2 - y1) / h) * 100, 2)

            class_name = result_names.get(cls_id, f"class_{cls_id}")
            if use_open_vocabulary:
                class_name = canonicalize_open_vocabulary_label(class_name, prompts)
            is_person = str(class_name).casefold() == "person"
            color = CATEGORY_COLORS.get(str(class_name).casefold(), CATEGORY_COLORS['default'])

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
                "is_person": is_person,
                "tracking_confirmed": tracking_confirmed,
            }
            if use_open_vocabulary:
                det["open_vocabulary"] = not is_person
                det["mask_polygon"] = mask_polygon_for_result(result, i, w, h)

            # For Person detections, add PPE sub-checks
            if is_person:
                det["track_id"] = f"TRK-{track_id:02d}"

                if track_id not in track_first_seen:
                    track_first_seen[track_id] = time.time()
                dwell_sec = round(time.time() - track_first_seen[track_id], 1)
                det["dwell_time"] = dwell_sec

                foot_x = round(((x1 + x2) / 2 / w) * 100, 2)
                foot_y = round((y2 / h) * 100, 2)
                det["foot_x"] = foot_x
                det["foot_y"] = foot_y

                # Head region coordinates (Top 22% of person height)
                head_w = round(w_pct * 0.55, 2)
                head_h = round(h_pct * 0.22, 2)
                head_x = round(x_pct + (w_pct - head_w) / 2, 2)
                head_y = round(y_pct, 2)

                # Torso region coordinates (22% to 58% of person height)
                vest_w = round(w_pct * 0.78, 2)
                vest_h = round(h_pct * 0.36, 2)
                vest_x = round(x_pct + (w_pct - vest_w) / 2, 2)
                vest_y = round(y_pct + head_h + 1, 2)

                # Pixel crops for analysis
                hx1 = max(0, int(x1 + (x2 - x1) * 0.15))
                hy1 = max(0, int(y1))
                hx2 = min(w, int(x1 + (x2 - x1) * 0.85))
                hy2 = min(h, int(y1 + (y2 - y1) * 0.24))

                vx1 = max(0, int(x1 + (x2 - x1) * 0.10))
                vy1 = max(0, int(y1 + (y2 - y1) * 0.22))
                vx2 = min(w, int(x1 + (x2 - x1) * 0.90))
                vy2 = min(h, int(y1 + (y2 - y1) * 0.58))

                head_crop = frame[hy1:hy2, hx1:hx2] if (hy2 > hy1 and hx2 > hx1) else None
                torso_crop = frame[vy1:vy2, vx1:vx2] if (vy2 > vy1 and vx2 > vx1) else None

                has_helmet, helmet_conf = analyze_head_ppe(head_crop)
                has_vest, vest_conf = analyze_torso_ppe(torso_crop)

                # Risk level & dynamic glowing colors
                if has_helmet and has_vest:
                    risk_level = "safe"
                    person_color = "#00e676"  # Vibrant Neon Green
                elif has_helmet or has_vest:
                    risk_level = "warning"
                    person_color = "#ffea00"  # Vibrant Neon Amber
                else:
                    risk_level = "critical"
                    person_color = "#ff1744"  # Vibrant Neon Red

                det["risk_level"] = risk_level
                det["color"] = person_color
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
                det["color"] = "#00e5ff"  # Vibrant Neon Cyan for objects

            all_detections.append(det)

    inference_ms = round((time.time() - start_t) * 1000, 1)
    return all_detections, inference_ms, use_open_vocabulary

@app.get("/")
def read_root():
    return {
        "status": "online",
        "vision_api": 2,
        "system": "PRAHARI AI Vision Intelligence Server",
        "version": "2.2.0",
        "mode": "Live PPE and object detection",
        "classes": len(COCO_NAMES),
        "model": MODEL_LABEL,
        "open_vocabulary_segmentation": open_vocabulary_model is not None,
        "open_vocabulary_error": open_vocabulary_error or None,
        "safety_runtime": "online",
        "site_outputs": "dry-run",
    }


async def broadcast_safety_message(message):
    if message.get("type") == "incident" and isinstance(message.get("incident"), dict):
        event_id = message["incident"].get("event_id") or message["incident"].get("id")
        if event_id:
            if event_id in SEEN_INCIDENT_IDS:
                return
            SEEN_INCIDENT_IDS.add(event_id)
    disconnected = []
    for client in tuple(SAFETY_ALERT_CLIENTS):
        try:
            await client.send_json(message)
        except Exception:
            disconnected.append(client)
    for client in disconnected:
        SAFETY_ALERT_CLIENTS.discard(client)


@app.get("/api/safety/events")
def get_safety_events(limit: int = 50, camera_id: str | None = None):
    return {"events": safety_runtime.list_events(limit, camera_id)}


@app.post("/api/safety/events/{event_id}/actions/{action}")
async def update_safety_event(event_id: str, action: str):
    action = {"acknowledge": "ack", "false-alarm": "false_alarm"}.get(action, action)
    try:
        event = safety_runtime.store.update_status(event_id, action)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if event is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    event["snapshot_url"] = safety_runtime._media_url(event.get("snapshot_path"))
    event["clip_url"] = safety_runtime._media_url(event.get("clip_path"))
    if action == "escalate":
        event["actions"] = safety_runtime.action_router.dispatch(event)
    await broadcast_safety_message({"type": "incident_update", "incident": event})
    return event


@app.get("/api/machines")
def get_machines():
    return {"machines": safety_runtime.machines.list_machines(), "interlock_mode": "dry-run"}


def require_machine_admin(authorization: str | None):
    token_name = safety_runtime.config.get("admin_token_env", "PRAHARI_ADMIN_TOKEN")
    expected = os.environ.get(token_name, "")
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not expected:
        raise HTTPException(status_code=503, detail=f"Set {token_name} to enable machine registry writes")
    if not supplied or not __import__("hmac").compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Valid admin bearer token required")


@app.post("/api/machines/{machine_id}")
def save_machine(machine_id: str, payload: dict = Body(...), authorization: str | None = Header(default=None)):
    require_machine_admin(authorization)
    try:
        machine = safety_runtime.machines.upsert(
            machine_id,
            payload.get("camera_id"),
            payload.get("detection_labels", []),
            payload.get("authorized_person_ids", []),
            payload.get("qr_value"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return machine


@app.post("/api/machines/{machine_id}/calibrate")
def calibrate_machine(machine_id: str, payload: dict = Body(...), authorization: str | None = Header(default=None)):
    require_machine_admin(authorization)
    try:
        return safety_runtime.machines.calibrate(
            machine_id, payload.get("camera_id"), payload.get("x_percent"), payload.get("y_percent")
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Machine is not registered") from exc
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/machines/{machine_id}/maintenance")
def set_machine_maintenance(machine_id: str, payload: dict = Body(...), authorization: str | None = Header(default=None)):
    require_machine_admin(authorization)
    try:
        return safety_runtime.machines.set_maintenance(machine_id, payload.get("enabled", False))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Machine is not registered") from exc


@app.post("/api/machines/{machine_id}/interlock")
def evaluate_machine_interlock(machine_id: str, payload: dict = Body(...)):
    result = safety_runtime.interlock.evaluate_start(
        machine_id, payload.get("person_id"), payload.get("ppe", {})
    )
    return result


@app.post("/api/identity/presence")
def register_identity_presence(payload: dict = Body(...), authorization: str | None = Header(default=None)):
    require_machine_admin(authorization)
    try:
        safety_runtime.machines.register_identity_presence(
            payload.get("camera_id"), payload.get("track_id"), payload.get("person_id"),
            payload.get("source", "rfid"), payload.get("ttl_seconds", 30),
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"registered": True, "expires_in_seconds": min(300, max(1, float(payload.get("ttl_seconds", 30))))}


@app.websocket("/ws/safety-alerts")
async def websocket_safety_alerts(websocket: WebSocket):
    await websocket.accept()
    SAFETY_ALERT_CLIENTS.add(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        SAFETY_ALERT_CLIENTS.discard(websocket)


async def _auto_escalate_loop():
    while True:
        try:
            for event in safety_runtime.auto_escalate_due():
                event["snapshot_url"] = safety_runtime._media_url(event.get("snapshot_path"))
                event["clip_url"] = safety_runtime._media_url(event.get("clip_path"))
                await broadcast_safety_message({"type": "incident_update", "incident": event})
        except Exception as exc:
            print(f"[WARN] Incident auto-escalation loop: {exc}")
        await asyncio.sleep(1.0)


async def _external_incident_poll_loop():
    """Forward incidents written by securade.py or another local process."""
    try:
        SEEN_INCIDENT_IDS.update(event.get("event_id") for event in safety_runtime.list_events(limit=200)
                                 if event.get("event_id"))
    except Exception as exc:
        print(f"[WARN] Initial incident history scan failed: {exc}")
    while True:
        try:
            events = safety_runtime.list_events(limit=200)
            for event in reversed(events):
                event_id = event.get("event_id")
                if event_id and event_id not in SEEN_INCIDENT_IDS:
                    await broadcast_safety_message({"type": "incident", "incident": event})
        except Exception as exc:
            print(f"[WARN] External incident poll failed: {exc}")
        await asyncio.sleep(0.5)


@app.on_event("startup")
async def start_auto_escalation():
    app.state.escalation_task = asyncio.create_task(_auto_escalate_loop())
    app.state.incident_poll_task = asyncio.create_task(_external_incident_poll_loop())


@app.on_event("shutdown")
async def stop_auto_escalation():
    task = getattr(app.state, "escalation_task", None)
    if task:
        task.cancel()
    poll_task = getattr(app.state, "incident_poll_task", None)
    if poll_task:
        poll_task.cancel()

@app.websocket("/ws/vision/{camera_id}")
async def websocket_vision_feed(websocket: WebSocket, camera_id: str):
    await websocket.accept()
    print(f"[STREAM] Client connected for live camera: {camera_id}")

    track_first_seen = {}
    cap = None

    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.08)
                data = json.loads(msg)

                # Direct browser webcam frames
                if "image" in data and data["image"]:
                    target_prompts = normalize_open_vocabulary_prompts(data.get("prompts"))
                    confidence = data.get("confidence", 0.15)
                    zones = data.get("zones") if isinstance(data.get("zones"), list) else None
                    b64_str = data["image"]
                    if "," in b64_str:
                        b64_str = b64_str.split(",")[1]
                    img_bytes = base64.b64decode(b64_str)
                    np_arr = np.frombuffer(img_bytes, np.uint8)
                    frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                    if frame is not None:
                        detections, inference_ms, ovs_active = process_frame(
                            frame, track_first_seen, target_prompts, confidence, camera_id
                        )
                        safety_alerts = safety_runtime.process_frame(camera_id, detections, frame, zones)
                        for alert in safety_alerts:
                            await broadcast_safety_message({"type": "incident", "incident": alert})
                        payload = {
                            "camera_id": camera_id,
                            "vision_api": 2,
                            "timestamp": round(time.time(), 2),
                            "inference_ms": inference_ms,
                            "fps": round(1000 / max(1, inference_ms + 10), 1),
                            "model": f"YOLOE-11s Seg + tracking" if ovs_active else MODEL_LABEL,
                            "open_vocabulary_active": ovs_active,
                            "open_vocabulary_error": open_vocabulary_error or None,
                            "confidence_threshold": confidence,
                            "total_detections": len(detections),
                            "detections": detections,
                            "safety_alerts": safety_alerts,
                        }
                        await websocket.send_text(json.dumps(payload))
                        continue
            except asyncio.TimeoutError:
                pass

            # Fallback for OpenCV video capture
            if cap is None:
                source = 0 if camera_id == "cam-webcam" else f"videos/{camera_id.replace('cam-', 'video_')}.mp4"
                cap = cv2.VideoCapture(source)

            if cap and cap.isOpened():
                success, frame = cap.read()
                if success and frame is not None:
                    detections, inference_ms, ovs_active = process_frame(
                        frame, track_first_seen, camera_id=camera_id
                    )
                    safety_alerts = safety_runtime.process_frame(camera_id, detections, frame)
                    for alert in safety_alerts:
                        await broadcast_safety_message({"type": "incident", "incident": alert})
                    payload = {
                        "camera_id": camera_id,
                        "vision_api": 2,
                        "timestamp": round(time.time(), 2),
                        "inference_ms": inference_ms,
                        "fps": round(cap.get(cv2.CAP_PROP_FPS) or 30.0, 1),
                        "model": MODEL_LABEL,
                        "open_vocabulary_active": ovs_active,
                        "open_vocabulary_error": open_vocabulary_error or None,
                        "total_detections": len(detections),
                        "detections": detections,
                        "safety_alerts": safety_alerts,
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
    print("PRAHARI AI Vision Intelligence Server v2.2")
    print(f"Live PPE & Object Detection ({MODEL_LABEL})")
    print(f"Loaded {len(COCO_NAMES)} COCO classes")
    print("=" * 60)
    uvicorn.run("prahari_live_server:app", host="0.0.0.0", port=8000, reload=False)
