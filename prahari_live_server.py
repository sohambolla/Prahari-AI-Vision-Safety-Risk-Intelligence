"""
PRAHARI AI Vision - Real-Time Multi-Class YOLO Detection + WebSocket Server
Uses a fine-tuned construction PPE detector for hardhat and safety-vest checks.
"""

import asyncio
import base64
import cv2
import json
import math
import numpy as np
import os
import time
from pathlib import Path
from fastapi import Body, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from ultralytics import YOLO
try:
    from ultralytics import YOLOE
except ImportError:
    YOLOE = None
import uvicorn
from prahari_safety.runtime import SafetyRuntime
from prahari_safety.tracker import IoUFallbackTracker

app = FastAPI(title="PRAHARI AI Vision Engine")
safety_runtime = SafetyRuntime()
live_fallback_tracker = IoUFallbackTracker()
SAFETY_ALERT_CLIENTS = set()
SEEN_INCIDENT_IDS = set()          # capped at _SEEN_IDS_MAX to prevent unbounded growth
_SEEN_IDS_MAX = 2000               # trim when size exceeds this
app.mount("/incidents", StaticFiles(directory=str(safety_runtime.store.root)), name="incidents")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load the base model for a graceful person-only fallback, then the locally
# fine-tuned PPE detector when training has produced its checkpoint.
BASE_DIR = Path(__file__).resolve().parent
model = YOLO(str(BASE_DIR / "yolo11n.pt"))
COCO_NAMES = model.names
PPE_MODEL_PATH = Path(os.environ.get("PRAHARI_PPE_MODEL", str(BASE_DIR / "weights" / "ppe-yolo11n.pt")))
if not PPE_MODEL_PATH.is_absolute():
    PPE_MODEL_PATH = BASE_DIR / PPE_MODEL_PATH
ppe_model = None
ppe_model_error = ""
if PPE_MODEL_PATH.is_file():
    try:
        ppe_model = YOLO(str(PPE_MODEL_PATH))
    except Exception as exc:
        ppe_model_error = str(exc)
        print(f"[WARN] Fine-tuned PPE model unavailable: {exc}")
MODEL_LABEL = "CSS v28 PPE detector" if ppe_model is not None else "YOLO11n person fallback"

open_vocabulary_model = None
open_vocabulary_error = ""
active_open_vocabulary_prompts = []
active_open_vocabulary_camera = None
failed_open_vocabulary_prompts = []
if YOLOE is not None:
    try:
        ovs_model_path = os.environ.get("PRAHARI_OVS_MODEL", "weights/yoloe-11s-seg.pt")
        open_vocabulary_model = YOLOE(ovs_model_path)
    except Exception as exc:
        open_vocabulary_error = str(exc)
        print(f"[WARN] Open-vocabulary segmentation unavailable: {exc}")
else:
    open_vocabulary_error = "Install ultralytics 8.4.0 or newer to enable YOLOE object detection."

if open_vocabulary_model is not None:
    MODEL_LABEL += " + optional YOLOE object detection"

try:
    OVS_IMAGE_SIZE = min(1280, max(640, int(os.environ.get("PRAHARI_OVS_IMGSZ", "640"))))
except ValueError:
    OVS_IMAGE_SIZE = 640

# Object category color mapping (Ultra-bright vibrant neon palette)
CATEGORY_COLORS = {
    'person': '#a855f7',      # Purple person segmentation
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

COCO_PERSON_CLASS_ID = 0
PPE_LABEL_STATES = {
    "hardhat": ("helmet", True),
    "no hardhat": ("helmet", False),
    "no safety vest": ("vest", False),
    "safety vest": ("vest", True),
}
active_ppe_camera = None


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

def normalize_ppe_label(label):
    return " ".join(str(label).casefold().replace("_", " ").replace("-", " ").split())


def ppe_detection_class_ids():
    """Select only person, hardhat, and safety-vest classes from the PPE model."""
    if ppe_model is None:
        return []
    names = ppe_model.names
    entries = names.items() if isinstance(names, dict) else enumerate(names)
    allowed_labels = {"person", *PPE_LABEL_STATES}
    return [
        int(class_id)
        for class_id, label in entries
        if normalize_ppe_label(label) in allowed_labels
    ]


def ppe_evidence_for_person(person_box, candidates):
    """Associate explicit CSS v28 PPE detections with one person; no box means unknown."""
    px1, py1, px2, py2 = [float(value) for value in person_box]
    person_w = max(1.0, px2 - px1)
    person_h = max(1.0, py2 - py1)
    evidence = {"helmet": None, "vest": None}
    confidence = {"helmet": None, "vest": None}

    for candidate in candidates:
        state = PPE_LABEL_STATES.get(normalize_ppe_label(candidate["label"]))
        if state is None:
            continue
        category, detected = state
        x1, y1, x2, y2 = candidate["bbox"]
        gear_area = max(1.0, (x2 - x1) * (y2 - y1))
        ix1, iy1 = max(px1, x1), max(py1, y1)
        ix2, iy2 = min(px2, x2), min(py2, y2)
        intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        relative_y = (center_y - py1) / person_h
        if intersection / gear_area < 0.5 or not (px1 <= center_x <= px2):
            continue
        if category == "helmet" and relative_y > 0.42:
            continue
        if category == "vest" and not (0.18 <= relative_y <= 0.90):
            continue

        score = float(candidate["confidence"])
        if confidence[category] is None or score > confidence[category]:
            evidence[category] = detected
            confidence[category] = score

    return {
        category: {
            "detected": evidence[category],
            "confidence": round(confidence[category] * 100, 1) if confidence[category] is not None else None,
            "type": ("Detected" if evidence[category] else "Not detected") if evidence[category] is not None else "Unknown",
        }
        for category in evidence
    }


def deduplicate_person_rows(rows):
    """Remove the nested duplicate person annotations common in CSS v28."""
    kept = []
    for candidate in sorted(rows, key=lambda row: row["confidence"], reverse=True):
        x1, y1, x2, y2 = candidate["bbox"]
        candidate_area = max(1.0, (x2 - x1) * (y2 - y1))
        duplicate = False
        for prior in kept:
            px1, py1, px2, py2 = prior["bbox"]
            prior_area = max(1.0, (px2 - px1) * (py2 - py1))
            intersection = max(0.0, min(x2, px2) - max(x1, px1)) * max(0.0, min(y2, py2) - max(y1, py1))
            smaller_area = min(candidate_area, prior_area)
            containment = intersection / smaller_area
            area_ratio = smaller_area / max(candidate_area, prior_area)
            if box_iou(candidate["bbox"], prior["bbox"]) >= 0.78 or (containment >= 0.92 and area_ratio < 0.65):
                duplicate = True
                break
        if not duplicate:
            kept.append(candidate)
    return kept


def assign_ppe_candidates_to_people(people, candidates):
    """Give each PPE box to its best overlapping person so adjacent workers do not share PPE."""
    assigned = [[] for _ in people]
    for candidate in candidates:
        state = PPE_LABEL_STATES.get(normalize_ppe_label(candidate["label"]))
        if state is None:
            continue
        category, _ = state
        x1, y1, x2, y2 = candidate["bbox"]
        gear_area = max(1.0, (x2 - x1) * (y2 - y1))
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        best_index = None
        best_score = -1.0
        for index, person in enumerate(people):
            px1, py1, px2, py2 = person["bbox"]
            ix1, iy1 = max(px1, x1), max(py1, y1)
            ix2, iy2 = min(px2, x2), min(py2, y2)
            intersection = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
            overlap = intersection / gear_area
            person_h = max(1.0, py2 - py1)
            relative_y = (center_y - py1) / person_h
            if overlap < 0.5 or not (px1 <= center_x <= px2):
                continue
            if category == "helmet" and relative_y > 0.42:
                continue
            if category == "vest" and not (0.18 <= relative_y <= 0.90):
                continue
            relative_x = (center_x - px1) / max(1.0, px2 - px1)
            target_y = {"helmet": 0.18, "vest": 0.52}[category]
            score = overlap - abs(relative_x - 0.5) * 0.12 - abs(relative_y - target_y) * 0.08
            if score > best_score:
                best_index = index
                best_score = score
        if best_index is not None:
            assigned[best_index].append(candidate)
    return assigned

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


def process_frame(frame, track_first_seen, target_prompts=None, confidence=0.15, camera_id=None):
    """Detect people, check hardhat/vest PPE, and optionally detect prompted objects."""
    global active_open_vocabulary_prompts, active_open_vocabulary_camera
    global failed_open_vocabulary_prompts, open_vocabulary_error, active_ppe_camera

    height, width = frame.shape[:2]
    start_t = time.time()
    prompts = normalize_open_vocabulary_prompts(target_prompts)
    try:
        confidence = min(0.75, max(0.05, float(confidence)))
    except (TypeError, ValueError):
        confidence = 0.15
    if not math.isfinite(confidence):
        confidence = 0.15

    camera_changed = camera_id != active_ppe_camera
    if camera_changed:
        tracker_model = ppe_model or model
        predictor = getattr(tracker_model, "predictor", None)
        for tracker in getattr(predictor, "trackers", []):
            tracker.reset()
        active_ppe_camera = camera_id
        safety_runtime.risk_engine.reset(camera_id)
        live_fallback_tracker.reset(camera_id)

    # The fine-tuned detector returns both person tracks and explicit PPE boxes.
    # Without its checkpoint, fall back to person-only COCO detections and keep
    # PPE status unknown instead of guessing from pixel color.
    person_rows = []
    ppe_candidates = []
    ppe_inference_failed = False
    if ppe_model is not None:
        try:
            ppe_results = ppe_model.track(
                frame,
                persist=True,
                verbose=False,
                conf=0.15,
                imgsz=640,
                classes=ppe_detection_class_ids(),
                tracker="configs/prahari_ovs_tracker.yaml",
            )
            ppe_result = ppe_results[0] if ppe_results else None
            if ppe_result is not None and ppe_result.boxes is not None:
                names = ppe_result.names
                for box in ppe_result.boxes:
                    xyxy = [float(value) for value in box.xyxy[0].cpu().tolist()]
                    class_id = int(box.cls[0].cpu().item())
                    label = str(names.get(class_id, class_id))
                    row = {
                        "bbox": xyxy,
                        "class_id": class_id,
                        "label": label,
                        "confidence": float(box.conf[0].cpu().item()),
                        "track_id": int(box.id[0].cpu().item()) if box.id is not None else None,
                    }
                    if normalize_ppe_label(label) == "person":
                        if row["confidence"] >= 0.20:
                            person_rows.append(row)
                    elif normalize_ppe_label(label) in PPE_LABEL_STATES and row["confidence"] >= 0.20:
                        ppe_candidates.append(row)
        except Exception as exc:
            print(f"[WARN] Fine-tuned PPE inference failed; using person-only fallback: {exc}")
            person_rows = []
            ppe_candidates = []
            ppe_inference_failed = True

    if ppe_model is None or ppe_inference_failed:
        fallback_results = model.track(
            frame,
            persist=True,
            verbose=False,
            conf=0.25,
            imgsz=640,
            classes=[COCO_PERSON_CLASS_ID],
            tracker="configs/prahari_ovs_tracker.yaml",
        )
        fallback_result = fallback_results[0] if fallback_results else None
        if fallback_result is not None and fallback_result.boxes is not None:
            for box in fallback_result.boxes:
                xyxy = [float(value) for value in box.xyxy[0].cpu().tolist()]
                track_id = int(box.id[0].cpu().item()) if box.id is not None else None
                person_rows.append({
                    "bbox": xyxy,
                    "class_id": COCO_PERSON_CLASS_ID,
                    "label": "person",
                    "confidence": float(box.conf[0].cpu().item()),
                    "track_id": track_id,
                })

    person_rows = deduplicate_person_rows(person_rows)
    ppe_by_person = assign_ppe_candidates_to_people(person_rows, ppe_candidates)

    # Optional object prompts use YOLOE boxes. Person detection and PPE status
    # come from the fine-tuned model, and the dashboard draws one box per person.
    segment_result = None
    use_open_vocabulary = False
    segmentation_classes = expand_open_vocabulary_prompts(prompts)
    if prompts and open_vocabulary_model is not None and segmentation_classes != failed_open_vocabulary_prompts:
        try:
            prompts_changed = segmentation_classes != active_open_vocabulary_prompts
            if prompts_changed:
                open_vocabulary_model.set_classes(segmentation_classes)
                active_open_vocabulary_prompts = segmentation_classes
                failed_open_vocabulary_prompts = []
                open_vocabulary_error = ""
            if prompts_changed or camera_changed or camera_id != active_open_vocabulary_camera:
                predictor = getattr(open_vocabulary_model, "predictor", None)
                for tracker in getattr(predictor, "trackers", []):
                    tracker.reset()
                active_open_vocabulary_camera = camera_id
            segment_results = open_vocabulary_model.track(
                frame,
                persist=True,
                verbose=False,
                conf=confidence,
                imgsz=OVS_IMAGE_SIZE,
                tracker="configs/prahari_ovs_tracker.yaml",
            )
            segment_result = segment_results[0] if segment_results else None
            use_open_vocabulary = bool(prompts and segment_result is not None)
        except Exception as exc:
            open_vocabulary_error = str(exc)
            failed_open_vocabulary_prompts = segmentation_classes
            print(f"[WARN] Optional object detection failed: {exc}")

    optional_objects = []
    if segment_result is not None and segment_result.boxes is not None:
        segment_boxes = segment_result.boxes
        segment_names = segment_result.names
        requested_labels = {prompt.casefold() for prompt in prompts}
        negative_labels = {
            label.casefold() for label in get_screen_hard_negatives(prompts)
            if label.casefold() not in requested_labels
        }
        raw_optional = []
        internal_negatives = []
        for index, box in enumerate(segment_boxes):
            xyxy = [float(value) for value in box.xyxy[0].cpu().tolist()]
            class_id = int(box.cls[0].cpu().item())
            label = str(segment_names.get(class_id, class_id))
            if prompts:
                label = canonicalize_open_vocabulary_label(label, prompts)
            row = {
                "index": index,
                "bbox": xyxy,
                "class_id": class_id,
                "label": label,
                "confidence": float(box.conf[0].cpu().item()),
                "track_id": int(box.id[0].cpu().item()) if box.id is not None else None,
            }
            if use_open_vocabulary:
                if label.casefold() in negative_labels:
                    internal_negatives.append(row)
                else:
                    raw_optional.append(row)

        # Avoid synonym boxes for the same object showing up as duplicates.
        for row in sorted(raw_optional, key=lambda item: item["confidence"], reverse=True):
            if row["label"].casefold() in SCREEN_PROMPT_TERMS and any(
                box_iou(row["bbox"], negative["bbox"]) >= 0.45
                and negative["confidence"] >= max(0.20, row["confidence"] * 0.60)
                for negative in internal_negatives
            ):
                continue
            if any(box_iou(row["bbox"], prior["bbox"]) > 0.82 for prior in optional_objects):
                continue
            optional_objects.append(row)

    all_detections = []
    for person_index, person in enumerate(person_rows):
        x1, y1, x2, y2 = person["bbox"]
        x1 = max(0.0, min(float(width), x1))
        x2 = max(0.0, min(float(width), x2))
        y1 = max(0.0, min(float(height), y1))
        y2 = max(0.0, min(float(height), y2))
        if x2 <= x1 or y2 <= y1:
            continue

        ppe = ppe_evidence_for_person([x1, y1, x2, y2], ppe_by_person[person_index])
        if ppe["helmet"]["detected"] is not True:
            risk_level = "critical"
        elif ppe["vest"]["detected"] is not True:
            risk_level = "warning"
        else:
            risk_level = "safe"

        track_id = person["track_id"]
        person_detection = {
            "track_id": f"TRK-{track_id:02d}" if track_id is not None else None,
            "class": "Person",
            "class_id": person["class_id"],
            "confidence": round(person["confidence"] * 100, 1),
            "bbox": [x1, y1, x2, y2],
            "x": round(x1 / width * 100, 2),
            "y": round(y1 / height * 100, 2),
            "w": round((x2 - x1) / width * 100, 2),
            "h": round((y2 - y1) / height * 100, 2),
            "foot_x": round((x1 + x2) / (2 * width) * 100, 2),
            "foot_y": round(y2 / height * 100, 2),
            "color": {
                "critical": "#ef4444",
                "warning": "#facc15",
                "safe": "#22c55e",
            }[risk_level],
            "is_person": True,
            "tracking_confirmed": track_id is not None,
            "risk_level": risk_level,
            "ppe": ppe,
        }

        all_detections.append(person_detection)

    for item in optional_objects:
        x1, y1, x2, y2 = item["bbox"]
        track_id = item["track_id"]
        label = item["label"]
        all_detections.append({
            "track_id": f"OBJ-{track_id:02d}" if track_id is not None else None,
            "class": str(label).title(),
            "class_id": item["class_id"],
            "confidence": round(item["confidence"] * 100, 1),
            "bbox": [x1, y1, x2, y2],
            "x": round(x1 / width * 100, 2),
            "y": round(y1 / height * 100, 2),
            "w": round((x2 - x1) / width * 100, 2),
            "h": round((y2 - y1) / height * 100, 2),
            "color": CATEGORY_COLORS.get(str(label).casefold(), CATEGORY_COLORS["default"]),
            "is_person": False,
            "tracking_confirmed": track_id is not None,
            "risk_level": "object",
            "open_vocabulary": True,
        })

    all_detections = live_fallback_tracker.update(camera_id, all_detections)
    for detection in all_detections:
        if detection.get("is_person") and detection.get("tracking_confirmed") and detection.get("track_id"):
            track_id = detection["track_id"]
            if track_id not in track_first_seen:
                track_first_seen[track_id] = time.time()
            detection["dwell_time"] = round(time.time() - track_first_seen[track_id], 1)

    inference_ms = round((time.time() - start_t) * 1000, 1)
    return all_detections, inference_ms, use_open_vocabulary

@app.get("/")
def read_root():
    return {
        "status": "online",
        "vision_api": 2,
        "system": "PRAHARI AI Vision Intelligence Server",
        "version": "2.2.0",
        "mode": "Live person and PPE detection with optional open-vocabulary equipment tracking",
        "classes": len(COCO_NAMES),
        "model": MODEL_LABEL,
        "ppe_detector_loaded": ppe_model is not None,
        "ppe_detector_error": ppe_model_error or None,
        "open_vocabulary_segmentation": open_vocabulary_model is not None,
        "open_vocabulary_error": open_vocabulary_error or None,
        "safety_runtime": "online",
        "site_outputs": "dry-run",
    }


async def broadcast_safety_message(message):
    if message.get("type") in ("incident", "incident_update") and isinstance(message.get("incident"), dict):
        event_id = message["incident"].get("event_id") or message["incident"].get("id")
        if event_id:
            if message.get("type") == "incident" and event_id in SEEN_INCIDENT_IDS:
                print(f"[ALERT] Skipping duplicate event_id: {event_id}")
                return
            SEEN_INCIDENT_IDS.add(event_id)
            # Prevent unbounded growth – trim oldest half when cap is reached
            if len(SEEN_INCIDENT_IDS) > _SEEN_IDS_MAX:
                to_remove = list(SEEN_INCIDENT_IDS)[:_SEEN_IDS_MAX // 2]
                for eid in to_remove:
                    SEEN_INCIDENT_IDS.discard(eid)
    disconnected = []
    clients = tuple(SAFETY_ALERT_CLIENTS)
    print(f"[ALERT] Broadcasting '{message.get('type')}' to {len(clients)} client(s)")
    for client in clients:
        try:
            await client.send_json(message)
        except Exception as exc:
            print(f"[ALERT] Failed to send to client: {exc}")
            disconnected.append(client)
    for client in disconnected:
        SAFETY_ALERT_CLIENTS.discard(client)


@app.get("/api/debug/pipeline")
def debug_pipeline():
    """Quick health-check for the live-alert pipeline."""
    last_events = safety_runtime.list_events(limit=10)
    return {
        "ws_clients_connected": len(SAFETY_ALERT_CLIENTS),
        "seen_incident_ids_count": len(SEEN_INCIDENT_IDS),
        "last_10_events": [
            {
                "event_id": e.get("event_id"),
                "event_type": e.get("event_type"),
                "severity": e.get("severity"),
                "camera_id": e.get("camera_id"),
                "timestamp": e.get("timestamp"),
                "status": e.get("status"),
            }
            for e in last_events
        ],
        "risk_rules_enabled": {
            name: safety_runtime.risk_engine.rules.get(name, {}).get("enabled", True)
            for name in ("person_down", "ppe", "fire_smoke", "vehicle_proximity",
                         "restricted_zone", "falling_object", "exit_blocked")
        },
    }


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
    print(f"[WS] Safety-alert client connected. Total clients: {len(SAFETY_ALERT_CLIENTS)}")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        SAFETY_ALERT_CLIENTS.discard(websocket)
        print(f"[WS] Safety-alert client disconnected. Remaining clients: {len(SAFETY_ALERT_CLIENTS)}")


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
        # Seed SEEN_INCIDENT_IDS with all existing events so we don't replay history on boot
        existing = safety_runtime.list_events(limit=200)
        SEEN_INCIDENT_IDS.update(e.get("event_id") for e in existing if e.get("event_id"))
        print(f"[POLL] Seeded {len(SEEN_INCIDENT_IDS)} existing incident IDs from store")
    except Exception as exc:
        print(f"[WARN] Initial incident history scan failed: {exc}")
    while True:
        try:
            events = safety_runtime.list_events(limit=200)
            for event in reversed(events):
                event_id = event.get("event_id")
                # Only broadcast events NOT already seen – broadcast_safety_message also
                # checks SEEN_INCIDENT_IDS but we guard here to avoid redundant log spam.
                if event_id and event_id not in SEEN_INCIDENT_IDS:
                    print(f"[POLL] New external incident detected: {event_id} ({event.get('event_type')})")
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
                            "model": f"{MODEL_LABEL} + prompted YOLOE tracking" if ovs_active else MODEL_LABEL,
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
    print(f"Live Person & PPE Detection; Equipment Tracking Is Opt-In ({MODEL_LABEL})")
    print(f"Loaded {len(COCO_NAMES)} COCO classes")
    print("=" * 60)
    uvicorn.run("prahari_live_server:app", host="0.0.0.0", port=8000, reload=False)
