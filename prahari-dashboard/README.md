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

The Vite development server starts `prahari_live_server.py` automatically when port 8000 is free. It uses `python` by default. Set `PRAHARI_PYTHON` to the Python executable for the environment containing the vision requirements if needed. The first startup downloads the YOLOE-11 segmentation checkpoint to the repository's `weights` directory. Its text encoder is fetched when you first apply object prompts, so allow network access on first use. Set `PRAHARI_OVS_MODEL` to use a different local YOLOE segmentation checkpoint and `PRAHARI_OVS_IMGSZ` to adjust inference resolution (default 960).

The browser retries the WebSocket connection while the model loads. Enter comma-separated equipment names (for example, `forklift, generator, gear, bearing`) and select **Apply targets**. The server adds `person` automatically and displays masks, track IDs, and short movement trails for prompted objects. Adjust **CONF** to trade missed detections for more false alarms. On CAM 07, the demo restricted area is placed across the forklift's route. Other feeds retain their existing configured zones.

YOLOE is a zero-shot starting point, not a guarantee for every machine part or camera angle. The screen reports if the optional segmentation model could not load and the existing YOLO detector remains available as a fallback. For a real "unauthorized asset" policy, configure the exact approved asset list and the site's entry zones; category prompts alone cannot decide whether a particular machine is authorized.

If the HUD reports that the server is offline, check the Vite terminal for the Python startup error. To manage the vision server yourself, set `PRAHARI_AUTOSTART_VISION=0`; the dashboard will keep reconnecting to port 8000. To use a different host or secure WebSocket endpoint, set `VITE_VISION_WS_URL` to its base URL, such as `wss://vision.example.com`.
