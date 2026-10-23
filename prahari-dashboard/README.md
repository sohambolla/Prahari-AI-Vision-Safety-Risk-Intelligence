# PRAHARI dashboard

## Pull the shared feature branch

From an existing clone of the repository, run these commands from the repository root to get the equipment-detection changes and their Git LFS assets:

```bash
git lfs install
git fetch origin
git switch --track origin/feature/equipment-detection
git lfs pull
```

## Run the dashboard with live detection

Install the dashboard's vision-server requirements in the Python environment you will use (`pip install -r requirements-vision.txt` from this directory), install the dashboard packages (`npm install`), then start the dashboard with `npm run dev`.

The Vite development server starts `prahari_live_server.py` automatically when port 8000 is free. It uses `python` by default. Set `PRAHARI_PYTHON` to the Python executable for the environment containing the vision requirements if needed. The detector uses the fine-tuned PPE checkpoint at `weights/ppe-yolo11n.pt` and checks hardhat and safety-vest classes only. Person status uses one box around the full person: red when a hardhat is not detected, yellow when the hardhat is detected but the vest is not, and green when both are detected. Face-mask PPE detection and person-mask overlays are disabled. YOLOE remains available for optional text-prompted object boxes. Set `PRAHARI_OVS_MODEL` to use a different local YOLOE checkpoint and `PRAHARI_OVS_IMGSZ` to adjust inference resolution (default 640). YOLOE loads its MobileCLIP text encoder when object prompts are first used.

### Fine-tune the PPE detector

The Construction Site Safety v28 dataset was provided by Roboflow Universe Projects and is licensed CC BY 4.0. Source: [Roboflow Universe](https://universe.roboflow.com/roboflow-universe-projects/construction-site-safety). Keep the dataset outside the repository. From the repository root, run:

```powershell
python scripts\train_ppe_detector.py --dataset "C:\Users\sandip\Downloads\archive\css-data" --epochs 30 --imgsz 640 --batch 1 --device 0
```

Training uses `train/` and `valid/`, leaves `test/` held out, and writes the runtime checkpoint to `weights/ppe-yolo11n.pt`. Restart the vision server after training so it loads the new checkpoint. When that checkpoint is unavailable, the live view still tracks people and displays PPE as unknown rather than estimating PPE from clothing color.

The default live scan detects and tracks people, checks hardhat and safety-vest labels, and monitors configured restricted areas. Equipment detection is off until you enter comma-separated labels (for example, `forklift, generator, gear, bearing`) and select **Apply targets**. The server keeps person/PPE and restricted-area monitoring active while displaying one status-colored box around each person and optional boxes for prompted equipment. Adjust **CONF** to trade missed detections for more false alarms. On CAM 07, the demo restricted area is placed across the forklift's route. Other feeds retain their existing configured zones.

YOLOE is a zero-shot starting point, not a guarantee for every machine part or camera angle. The screen reports if the optional object model could not load; the fallback keeps person/PPE and restricted-area monitoring active, while equipment tracking requires YOLOE. For a real "unauthorized asset" policy, configure the exact approved asset list and the site's entry zones; category prompts alone cannot decide whether a particular machine is authorized.

If the HUD reports that the server is offline, check the Vite terminal for the Python startup error. To manage the vision server yourself, set `PRAHARI_AUTOSTART_VISION=0`; the dashboard will keep reconnecting to port 8000. To use a different host or secure WebSocket endpoint, set `VITE_VISION_WS_URL` to its base URL, such as `wss://vision.example.com`.
