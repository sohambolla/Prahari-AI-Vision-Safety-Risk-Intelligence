# PRAHARI Real-Time Safety Pipeline

This repository now has one temporal risk engine that can be called by the live dashboard server, the legacy `securade.py` multi-camera pipeline, and a standalone YOLO-World video runner. Existing camera policy checks in `securade.py` remain in place.

## Data flow

```mermaid
flowchart LR
  A[RTSP or local camera] --> B[YOLOv7 in securade.py]
  C[Browser video or webcam] --> D[YOLO11 and YOLOE in prahari_live_server.py]
  E[Test video] --> F[YOLO-World perception]
  B --> G[ByteTrack]
  D --> H[Ultralytics tracking IDs]
  F --> I[Supervision ByteTrack]
  G --> J[RiskEngine]
  H --> J
  I --> J
  J --> K[ActionRouter: dry-run by default]
  J --> L[SQLite + snapshot + pre-event clip]
  K --> M[Safety-alert WebSocket and optional Telegram/webhook]
  L --> M
  M --> N[Dashboard alert inbox, actions, replay]
```

The reusable modules live in `prahari_safety/`:

- `perception.py` normalizes YOLO-World and legacy YOLOv7 detections.
- `tracker.py` adapts Supervision ByteTrack for the standalone and legacy pipelines.
- `risk_engine.py` applies track-based rules and temporal confirmation.
- `machine_safety.py` stores machine settings, checks QR-marker shifts, and checks identity/PPE interlock requests.
- `action_router.py` queues optional site webhook, Telegram, and call-webhook actions.
- `store.py` writes incidents to SQLite and saves snapshots plus a bounded rolling clip.
- `runtime.py` connects the engine, machine registry, router, and event store.
- `interlock.py` evaluates start requests without controlling hardware.

## Start the dashboard path

From the repository root, start the vision API:

```powershell
python -m uvicorn prahari_live_server:app --host 0.0.0.0 --port 8000
```

In another terminal:

```powershell
cd prahari-dashboard
npm run dev
```

The dashboard sends its selected video/webcam frames to the API. Incidents are shown in Live Safety Alerts, where an operator can acknowledge, escalate, or mark a false alarm. Snapshot and replay links use the local `/incidents` mount.

## Connect the legacy RTSP pipeline

`securade.py` now sends each camera's YOLOv7 detections through a per-camera ByteTrack instance and the shared risk runtime. Existing config files can optionally set a stable camera `id`; otherwise IDs are assigned as `camera-01`, `camera-02`, and so on. For example:

```json
{
  "id": "factory-east-01",
  "url": "rtsp://user:password@camera/stream",
  "policy_file": "policy.json",
  "duration": 10,
  "alert_url": ""
}
```

Set `mask_faces` to `true` in the Securade config to blur faces in the rolling archive frames. An incident snapshot is captured from the original frame for review. The old `alert_url` path is still governed by the existing Securade policy; the new PRAHARI site router remains dry-run unless separately configured.

## Risk rules and restricted zones

Thresholds are in [`configs/risk_config.json`](configs/risk_config.json). Rules include:

- Fire/smoke: confidence threshold and consecutive tracked-frame count.
- Falling load: tracked downward velocity, initial image height, and distance to a worker.
- Possible fall/person down: horizontal person box, elapsed time, and stillness.
- PPE: explicit helmet/vest negative evidence with temporal confirmation.
- Vehicle proximity, blocked exits, restricted-zone entry, and unattended objects.
- Machine QR shift and repeated person/machine overlap thresholds.

The dashboard sends configured camera hazard polygons as percentages of frame width and height. In the legacy Securade policy, exclusion-zone polygons are read from the camera's policy file. A zone in a demo video is only a test polygon; calibrate it for the real camera view before using it.

## Dashboard incident schema

The incident REST and WebSocket payload uses one record shape:

```json
{
  "event_id": "uuid",
  "timestamp": 1790000000.0,
  "camera_id": "factory-east-01",
  "zone_id": "restricted",
  "event_type": "restricted_zone_intrusion",
  "severity": "critical",
  "title": "Person entered restricted area",
  "detail": "Track 12 crossed zone restricted.",
  "confidence": 0.87,
  "track_id": "12",
  "person_id": null,
  "machine_id": null,
  "bbox": [120, 80, 260, 420],
  "status": "new",
  "snapshot_url": "/incidents/factory-east-01/.../snapshot.jpg",
  "clip_url": "/incidents/factory-east-01/.../incident.mp4",
  "actions": {
    "site": {"mode": "dry-run", "dispatched": false},
    "admin": {"websocket": true, "telegram_queued": false, "call_queued": false}
  },
  "evidence": {"rule": "restricted_zone", "tracks": ["12"]}
}
```

`bbox` uses pixel `[x1, y1, x2, y2]` coordinates from the source frame. Confidence is between `0` and `1`. Status is `new`, `acknowledged`, `escalated`, or `false_alarm`.

| Endpoint | Use |
| --- | --- |
| `GET /api/safety/events?limit=50&camera_id=...` | Read recent incidents and replay links |
| `POST /api/safety/events/{event_id}/actions/acknowledge` | Acknowledge an incident |
| `POST /api/safety/events/{event_id}/actions/escalate` | Dispatch the configured escalation route |
| `POST /api/safety/events/{event_id}/actions/false-alarm` | Mark an incident as a false alarm |
| `GET /api/machines` | Read the machine registry |
| `POST /api/machines/{machine_id}` | Add/update a machine (admin bearer token required) |
| `POST /api/machines/{machine_id}/calibrate` | Save its QR home position (admin token required) |
| `POST /api/machines/{machine_id}/interlock` | Simulate a machine start check; never actuates hardware |
| `POST /api/identity/presence` | Register a short-lived verified ID from an external source (admin token required) |

## Register and calibrate a machine

The dashboard's Machine Registry writes require a server-side admin token. In PowerShell, configure it before starting the API:

```powershell
$env:PRAHARI_ADMIN_TOKEN = "use-a-long-random-token"
python -m uvicorn prahari_live_server:app --host 0.0.0.0 --port 8000
```

Add a machine ID, camera ID, the detector labels used for that machine, and authorized person IDs. Put a QR marker on the machine and set its payload to `PRAHARI:MACHINE:<machine-id>` (or the configured QR value). Use the calibration action to store the marker's home center in percent coordinates. Shift alerts are emitted when the observed QR center exceeds `machine_shift.max_shift_px`; maintenance mode suppresses these alerts.

Identity presence can be registered through `POST /api/identity/presence` with the admin bearer token. This accepts an identity from an external RFID/face-verification system; the application does not enroll faces or infer a verified identity itself. `POST /api/machines/{id}/interlock` is a simulation: it reports whether an authorized identity and helmet, vest, and gloves were supplied, and never activates a relay.

## Optional alert integrations

All integrations are disabled or dry-run by default in `configs/risk_config.json`. Dry-run incidents record the simulated zone output plan (hooter/beacon/PA for critical alerts) without activating hardware.

- To enable Telegram, set `admin.telegram_enabled` to `true` and provide `PRAHARI_TELEGRAM_BOT_TOKEN` and `PRAHARI_TELEGRAM_CHAT_ID`. A saved incident snapshot is sent with the message when available.
- To configure an isolated site relay, set `site.dry_run` to `false`, enable the matching `site.zone_routes` entry, and provide its `webhook_url`. The endpoint is called in a background worker. The receiver must map that camera/zone route to a safe, independently tested output.
- To request an administrator call, set `admin.auto_call_enabled` to `true` and `PRAHARI_CALL_WEBHOOK_URL`. This is a generic provider webhook, not a built-in Twilio/Exotel client. The external adapter owns provider authentication and call status.
- New incidents are available over `/ws/safety-alerts`; unacknowledged incidents are escalated after `admin.auto_escalate_seconds`.

## Validation

Run the deterministic rule/store checks:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Run the standalone video runner on the bundled drilling-site clip:

```powershell
python prahari_vision_core.py --source videos/testing/construction/foundation-drilling.webm --max-frames 40 --headless
```

Press `q` to stop the preview when running interactively. The runner uses `yolov8s-world.pt` and saves confirmed incidents under `output/incidents/` and `output/incidents.sqlite3`. Replace the sample clip and polygon with footage from the target camera for site calibration.

On the local validation run, the first 40 frames of `excavator-stockton.webm` produced 22 tracked detections and no incidents; `foundation-drilling.webm` produced 24 tracked detections and one restricted-zone event. That zone event used the runner's demo polygon. The first 40 frames of the Intel worker-zone sample were an empty view and produced no detections. These counts are smoke checks, not precision/recall or a model-accuracy score; the clips do not include ground-truth annotations.

## Current limits

- The default site action is a dry-run record; no GPIO, MQTT relay, beacon, or PA output is activated.
- The interlock API reports a decision but does not block a real machine start. A qualified, isolated machine controller integration is still required for actuation.
- Machine “touch” is repeated box overlap and explicitly does not prove hand contact. QR shift depends on a visible, correctly configured marker.
- PPE evidence from `securade.py` uses the selected YOLOv7 model's explicit positive/negative labels. The live dashboard uses its configured YOLO/YOLOE models. Open-vocabulary labels can miss small or occluded workshop components; tune and validate against camera-specific labeled footage.
- The event clip contains the buffered footage before the trigger. It is not a 15-second post-event recording.
- The `<1s` site and `<3s` admin targets are not certified or measured in this prototype. Latency depends on camera frame rate, model, device, and inference backlog. The fire rule's ten-frame confirmation also delays notification until those frames arrive.
- Face blurring is opt-in through the existing Securade `mask_faces` setting. The browser live-server archive path has not yet been validated for face redaction.
