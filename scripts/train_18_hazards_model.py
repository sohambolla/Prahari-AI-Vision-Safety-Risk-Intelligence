import os
from ultralytics import YOLO

def train_best_ml_model():
    """
    This script fine-tunes the best ML model (YOLO11 / YOLO-World) for the 18 workplace hazards.
    It expects a dataset in YOLO format (e.g., from Kaggle or Roboflow) containing classes for:
    person, forklift, helmet, safety vest, fire, smoke, mobile phone, MEWP, etc.
    """
    # Initialize a YOLO-World or YOLO11 model
    # YOLO-World is chosen as the base because it already has zero-shot capabilities for many required classes
    model = YOLO("yolov8s-world.pt")

    # Dataset path (e.g., downloaded from Kaggle)
    # Ensure you have your dataset in 'datasets/workplace_hazards/' with a 'data.yaml'
    dataset_yaml = "datasets/workplace_hazards/data.yaml"

    if not os.path.exists(dataset_yaml):
        print("Dataset not found! Please download the Kaggle dataset to 'datasets/workplace_hazards/data.yaml'")
        print("You can use: kaggle datasets download -d <dataset-name> -p datasets/workplace_hazards/")
        return

    print("Starting training for the 18 Hazards ML Model...")
    # Train the model
    results = model.train(
        data=dataset_yaml,
        epochs=100, # High epochs for the best accuracy
        imgsz=640,
        batch=16,
        device="cuda", # Use GPU for training
        name="18_hazards_model",
        plots=True
    )

    print("Training complete. The best model is saved at 'runs/detect/18_hazards_model/weights/best.pt'")

if __name__ == "__main__":
    train_best_ml_model()
