"""Fine-tune the PRAHARI PPE detector on the Roboflow CSS YOLO dataset."""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / ".ultralytics-config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("YOLO_CONFIG_DIR", str(CONFIG_DIR))

from ultralytics import YOLO

CLASS_NAMES = [
    "Hardhat",
    "Mask",
    "NO-Hardhat",
    "NO-Mask",
    "NO-Safety Vest",
    "Person",
    "Safety Cone",
    "Safety Vest",
    "machinery",
    "vehicle",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path.home() / "Downloads" / "archive" / "css-data",
        help="Dataset root containing train/valid/test images and labels folders",
    )
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--batch", type=int, default=1)
    parser.add_argument("--device", default="0", help="Ultralytics device, for example 0 or cpu")
    parser.add_argument("--workers", type=int, default=0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    ultralytics_config = CONFIG_DIR / "Ultralytics"
    ultralytics_config.mkdir(parents=True, exist_ok=True)
    font = ultralytics_config / "Arial.ttf"
    system_font = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "arial.ttf"
    if not font.is_file() and system_font.is_file():
        shutil.copy2(system_font, font)

    dataset = args.dataset.expanduser().resolve()
    for split in ("train", "valid", "test"):
        for child in ("images", "labels"):
            path = dataset / split / child
            if not path.is_dir():
                raise FileNotFoundError(f"Expected dataset folder: {path}")

    if not (ROOT / "yolo11n.pt").is_file():
        raise FileNotFoundError(f"Pretrained base model not found: {ROOT / 'yolo11n.pt'}")

    names = "\n".join(f"  {index}: {name!r}" for index, name in enumerate(CLASS_NAMES))
    yaml_text = (
        f"path: {str(dataset)!r}\n"
        "train: train/images\n"
        "val: valid/images\n"
        "test: test/images\n"
        f"names:\n{names}\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", encoding="utf-8", delete=False) as config:
        config.write(yaml_text)
        data_yaml = Path(config.name)

    try:
        detector = YOLO(str(ROOT / "yolo11n.pt"))
        result = detector.train(
            data=str(data_yaml),
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch=args.batch,
            device=args.device,
            workers=args.workers,
            patience=8,
            project=str(ROOT / "runs" / "ppe"),
            name="yolo11n-css-v28",
            exist_ok=True,
            cache=False,
            plots=False,
            amp=True,
            close_mosaic=5,
            seed=42,
            verbose=True,
        )
        save_dir = Path(result.save_dir)
        best = save_dir / "weights" / "best.pt"
        if not best.is_file():
            raise FileNotFoundError(f"Training did not produce the best checkpoint: {best}")

        output = ROOT / "weights" / "ppe-yolo11n.pt"
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(best, output)
        print(f"PPE detector saved to {output}")
        print(f"Training run saved to {save_dir}")
    finally:
        data_yaml.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
