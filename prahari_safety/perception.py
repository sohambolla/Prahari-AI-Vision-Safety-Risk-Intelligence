"""YOLO-World image perception adapter used by the standalone video runner."""

from __future__ import annotations


DEFAULT_SAFETY_LABELS = (
    "person", "forklift", "vehicle", "excavator", "construction equipment", "heavy machinery",
    "crane", "industrial machine", "helmet", "safety helmet", "safety vest", "safety gloves",
    "fire", "smoke", "cell phone", "door", "emergency exit", "conveyor belt", "handrail",
    "suspended load", "falling object", "MEWP", "weapon", "ammo box", "unattended bag",
    "machine", "gear", "bearing", "bottle",
)


def legacy_boxes_to_detections(box_list, class_ids):
    """Normalize securade.py YOLOv7 box rows into the shared risk-engine schema."""
    detections = []
    for row in box_list or []:
        if len(row) < 6:
            continue
        label = str(row[0]).strip()
        normalized = " ".join(label.casefold().replace("_", " ").replace("-", " ").split())
        try:
            box = [float(value) for value in row[1:5]]
            confidence = float(row[5])
        except (TypeError, ValueError):
            continue
        if not label or box[2] <= box[0] or box[3] <= box[1]:
            continue
        detections.append({
            "class": label,
            "class_id": class_ids.setdefault(normalized, len(class_ids)),
            "confidence": confidence,
            "bbox": box,
            "tracking_confirmed": False,
        })
    _attach_explicit_ppe_evidence(detections)
    return detections


def _attach_explicit_ppe_evidence(detections):
    """Attach only explicit positive/negative PPE labels; unknown stays unknown."""
    ppe_labels = {
        "helmet": ({"hardhat", "helmet", "safety helmet"}, {"no hardhat", "no helmet", "no safety helmet"}),
        "vest": ({"safety vest", "hi vis vest", "high visibility vest"}, {"no safety vest", "no vest", "no hi vis vest"}),
        "gloves": ({"safety gloves", "gloves"}, {"no gloves", "no safety gloves"}),
    }
    people = [item for item in detections if item["class"].casefold() in {"person", "worker", "pedestrian"}]
    for person in people:
        px1, py1, px2, py2 = person["bbox"]
        ppe = {}
        for category, (positive, negative) in ppe_labels.items():
            evidence = []
            for item in detections:
                label = " ".join(item["class"].casefold().replace("_", " ").replace("-", " ").split())
                if label not in positive | negative:
                    continue
                x1, y1 = max(px1, item["bbox"][0]), max(py1, item["bbox"][1])
                x2, y2 = min(px2, item["bbox"][2]), min(py2, item["bbox"][3])
                intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
                gear_area = max(1.0, (item["bbox"][2] - item["bbox"][0]) * (item["bbox"][3] - item["bbox"][1]))
                if intersection / gear_area >= 0.5:
                    evidence.append((label, float(item["confidence"])))
            state = None
            if evidence:
                strongest = max(evidence, key=lambda value: value[1])[0]
                state = strongest in positive
            ppe[category] = {"detected": state}
        person["ppe"] = ppe


class YoloWorldPerception:
    """Load YOLO-World lazily and return detector-neutral box dictionaries."""

    def __init__(self, model_path="yolov8s-world.pt", labels=None, confidence=0.10, image_size=960):
        try:
            from ultralytics import YOLOWorld
        except ImportError as exc:
            raise RuntimeError("Install ultralytics to run PRAHARI video perception") from exc
        self.model = YOLOWorld(model_path)
        self.labels = list(labels or DEFAULT_SAFETY_LABELS)
        self.model.set_classes(self.labels)
        self.confidence = float(confidence)
        self.image_size = int(image_size)

    def infer(self, frame):
        result = self.model.predict(
            frame, verbose=False, conf=self.confidence, imgsz=self.image_size
        )[0]
        if result.boxes is None:
            return []
        detections = []
        names = result.names
        height, width = frame.shape[:2]
        for box in result.boxes:
            class_id = int(box.cls[0].item())
            raw_xyxy = [float(value) for value in box.xyxy[0].tolist()]
            xyxy = [
                min(max(raw_xyxy[0], 0.0), float(width)),
                min(max(raw_xyxy[1], 0.0), float(height)),
                min(max(raw_xyxy[2], 0.0), float(width)),
                min(max(raw_xyxy[3], 0.0), float(height)),
            ]
            if xyxy[2] <= xyxy[0] or xyxy[3] <= xyxy[1]:
                continue
            detections.append({
                "class": str(names.get(class_id, class_id)),
                "class_id": class_id,
                "confidence": float(box.conf[0].item()),
                "bbox": xyxy,
                "tracking_confirmed": False,
            })
        detections.sort(key=lambda item: item["confidence"], reverse=True)
        kept = []
        for candidate in detections:
            x1, y1, x2, y2 = candidate["bbox"]
            candidate_area = (x2 - x1) * (y2 - y1)
            duplicate = False
            for prior in kept:
                px1, py1, px2, py2 = prior["bbox"]
                intersection = max(0.0, min(x2, px2) - max(x1, px1)) * max(0.0, min(y2, py2) - max(y1, py1))
                prior_area = (px2 - px1) * (py2 - py1)
                union = candidate_area + prior_area - intersection
                if union > 0 and intersection / union >= 0.85:
                    duplicate = True
                    break
            if not duplicate:
                kept.append(candidate)
        return kept
