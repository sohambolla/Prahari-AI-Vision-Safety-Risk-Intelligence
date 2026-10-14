import { useState, useEffect, useRef } from 'react'
import {
  Camera, Maximize2, VideoOff,
  AlertTriangle, ShieldAlert, Radio,
  Volume2, VolumeX, Eye, Play, Pause, Layers,
  Scan, Crosshair, Sparkles, Activity
} from 'lucide-react'
import './LiveVisionPanel.css'
import trackingData from '../data/tracked_detections.json'

const CAM_FEEDS = [
  { id: 'cam-01', name: 'CAM 01: Construction Site CCTV', location: 'Excavation Area', src: '/videos/video_2.mp4', defaultDist: 0.8 },
  { id: 'cam-02', name: 'CAM 02: Foundry Workshop CCTV', location: 'Metal Casting Floor', src: '/videos/video_1.mp4', defaultDist: 2.1 },
  { id: 'cam-03', name: 'CAM 03: Production Floor CCTV', location: 'Industrial Workshop', src: '/videos/video_3.mp4', defaultDist: 1.2 },
  { id: 'cam-04', name: 'CAM 04: Workshop Machine CCTV', location: 'Machine Area', src: '/videos/video_4.mp4', defaultDist: 3.4 },
  {
    id: 'cam-05', name: 'CAM 05: Restricted Walkway CCTV', location: 'Factory Pedestrian Aisle',
    src: '/videos/cctv-0_te1.mp4', defaultDist: 1.8,
    hazardZone: [[67, 34], [83, 34], [83, 82], [67, 82]],
  },
  {
    id: 'cam-06', name: 'CAM 06: Restricted Machine Access CCTV', location: 'Production Machine',
    src: '/videos/cctv-1_te1.mp4', defaultDist: 2.0,
    hazardZone: [[77, 28], [91, 28], [91, 78], [77, 78]],
  },
  {
    id: 'cam-07', name: 'CAM 07: Forklift Handling CCTV', location: 'Factory Loading Aisle',
    src: '/videos/cctv-3_te1.mp4', defaultDist: 3.0,
    hazardZone: [[72, 72], [99, 72], [99, 99], [72, 99]],
  },
  {
    id: 'cam-08', name: 'CAM 08: Concrete Worksite Camera', location: 'Slab Pour Area',
    src: '/videos/construction_0.mp4', defaultDist: 2.0,
    hazardZone: [[48, 42], [90, 42], [90, 97], [48, 97]],
  },
  {
    id: 'cam-09', name: 'CAM 09: Construction Yard Camera', location: 'Equipment Yard',
    src: '/videos/construction_7.mp4', defaultDist: 3.0,
    hazardZone: [[2, 55], [26, 55], [26, 88], [2, 88]],
  },
  { id: 'cam-10', name: 'CAM 10: Warehouse Forklift CCTV', location: 'Warehouse Floor', src: '/videos/construction_17.mp4', defaultDist: 3.5 },
  { id: 'cam-11', name: 'CAM 11: Warehouse Aisle CCTV', location: 'Forklift Aisle', src: '/videos/machinery_vid_0.mp4', defaultDist: 2.5 },
  { id: 'cam-12', name: 'CAM 12: Car Classification Test', location: 'Vehicle Test', src: '/videos/car-detection.mp4', defaultDist: 4.5 },
  { id: 'cam-webcam', name: 'LIVE WEBCAM: Real-Time Test', location: 'Local Operator Cam', src: '', defaultDist: 1.5 },
]

const isPersonDetection = (detection) =>
  detection.is_person || /^person$/i.test(detection.class || '')

const EQUIPMENT_COLORS = {
  cup: '#ff9f1c',
  bottle: '#14b8a6',
  'water bottle': '#14b8a6',
  screen: '#a855f7',
  monitor: '#a855f7',
  tv: '#a855f7',
  laptop: '#22c55e',
  keyboard: '#ec4899',
  mouse: '#eab308',
  gear: '#f97316',
  bearing: '#8b5cf6',
  washer: '#06b6d4',
  bolt: '#84cc16',
  nut: '#84cc16',
  wrench: '#fb7185',
  forklift: '#38bdf8',
  'forklift truck': '#38bdf8',
  car: '#f43f5e',
  truck: '#f97316',
}

const getEquipmentColor = (className = '') => {
  const normalizedClass = className.trim().toLocaleLowerCase()
  if (Object.prototype.hasOwnProperty.call(EQUIPMENT_COLORS, normalizedClass)) {
    return EQUIPMENT_COLORS[normalizedClass]
  }

  // Stable class-based fallback for open-vocabulary labels not listed above.
  let hash = 2166136261
  for (const character of normalizedClass) {
    hash = Math.imul(hash ^ character.charCodeAt(0), 16777619)
  }
  return `hsl(${(hash >>> 0) % 360} 88% 58%)`
}

const getDetectionColor = (detection) => {
  if (isPersonDetection(detection)) {
    return detection.color || (detection.risk_level === 'critical'
      ? '#ff1744'
      : detection.risk_level === 'warning' ? '#ffea00' : '#00e676')
  }
  return getEquipmentColor(detection.class)
}

const pointInPolygon = (point, polygon) => {
  let inside = false
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const [xi, yi] = polygon[i]
    const [xj, yj] = polygon[j]
    const crossesY = (yi > point.y) !== (yj > point.y)
    const crossingX = ((xj - xi) * (point.y - yi)) / (yj - yi) + xi
    if (crossesY && point.x < crossingX) inside = !inside
  }
  return inside
}

export default function LiveVisionPanel({ time, onSafetyAlert, alertRefreshSignal = 0 }) {
  const [selectedCam, setSelectedCam] = useState(CAM_FEEDS[6])
  const [isPlaying, setIsPlaying] = useState(true)
  const [showOverlays, setShowOverlays] = useState(true)
  const [showPPE, setShowPPE] = useState(true)
  const [showZones, setShowZones] = useState(true)
  const [showVectors, setShowVectors] = useState(true)
  const [filterMode, setFilterMode] = useState('all') // all, critical, ppe, ovs
  const [isAlertActive, setIsAlertActive] = useState(true)
  const [isScanning, setIsScanning] = useState(false)
  const [fps, setFps] = useState(null)
  const [inferenceMs, setInferenceMs] = useState(null)
  const [modelName, setModelName] = useState('YOLO11n')
  const [promptText, setPromptText] = useState('forklift truck')
  const [targetPrompts, setTargetPrompts] = useState(['forklift truck'])
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.15)
  const [openVocabularyActive, setOpenVocabularyActive] = useState(null)
  const [openVocabularyError, setOpenVocabularyError] = useState('')
  const [currentDetections, setCurrentDetections] = useState([])
  const [webcamActive, setWebcamActive] = useState(false)
  const [webcamFaceBox, setWebcamFaceBox] = useState({ x: 38, y: 22, w: 24, h: 56 })

  const videoRef = useRef(null)
  const detectionMemoryRef = useRef(new Map())
  const trajectoryMemoryRef = useRef(new Map())
  const webcamVideoRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const containerRef = useRef(null)
  const animFrameRef = useRef(null)
  const reportedSafetyAlertRef = useRef({ key: '', clearTimer: null })
  const lastAlertRefreshSignalRef = useRef(alertRefreshSignal)

  // Switch feeds & handle video / webcam
  useEffect(() => {
    setCurrentDetections([]) // Immediately clear previous camera's detections
    detectionMemoryRef.current.clear()
    setFps(null)
    setInferenceMs(null)
    if (selectedCam.id === 'cam-webcam') {
      startWebcam()
    } else {
      stopWebcam()
      if (videoRef.current) {
        videoRef.current.load()
        videoRef.current.play().catch(() => {})
      }
    }
    return () => {
      stopWebcam()
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    }
  }, [selectedCam])

  const startWebcam = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 } }
      })
      mediaStreamRef.current = stream
      if (webcamVideoRef.current) {
        webcamVideoRef.current.srcObject = stream
        webcamVideoRef.current.play()
      }
      setWebcamActive(true)
    } catch (err) {
      console.warn('Webcam not accessible:', err)
      setWebcamActive(false)
    }
  }

  const stopWebcam = () => {
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop())
      mediaStreamRef.current = null
    }
    setWebcamActive(false)
  }

  const [wsStatus, setWsStatus] = useState('connecting')
  const isWsConnected = wsStatus === 'connected'
  const wsRef = useRef(null)

  // Connect the selected video or webcam to live inference.
  useEffect(() => {
    let disposed = false
    let retryTimer
    let retryDelay = 1000
    const wsBase = (import.meta.env.VITE_VISION_WS_URL ||
      `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname || 'localhost'}:8000`).replace(/\/$/, '')
    const scheduleReconnect = () => {
      if (disposed) return
      setWsStatus('offline')
      retryTimer = window.setTimeout(() => {
        if (disposed) return
        setWsStatus('connecting')
        connect()
      }, retryDelay)
      retryDelay = Math.min(retryDelay * 2, 10000)
    }

    const connect = () => {
      if (disposed) return
      let ws
      try {
        ws = new WebSocket(`${wsBase}/ws/vision/${selectedCam.id}`)
        wsRef.current = ws
        ws.onopen = () => {
          if (disposed) return ws.close()
          retryDelay = 1000
          console.log(`Connected to PRAHARI Live YOLO WebSocket for ${selectedCam.id}`)
          setWsStatus('connected')
        }
        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            if (data.camera_id && data.camera_id !== selectedCam.id) return
            if (typeof data.open_vocabulary_active !== 'boolean') {
              setOpenVocabularyActive(false)
              setOpenVocabularyError('Vision server is outdated. Restart the dashboard and vision server.')
            }
            if (typeof data.open_vocabulary_active === 'boolean') {
              setOpenVocabularyActive(data.open_vocabulary_active)
              setOpenVocabularyError(data.open_vocabulary_error || '')
            }
            if (data.detections) {
              const now = performance.now()
              const previous = detectionMemoryRef.current
              const next = new Map()
              const freshIds = new Set()

              data.detections.forEach(detection => {
                const id = detection.track_id
                const last = previous.get(id)
                const pointX = detection.foot_x ?? (detection.x + detection.w / 2)
                const pointY = detection.foot_y ?? (detection.y + detection.h)
                const trailRecord = trajectoryMemoryRef.current.get(id) || { points: [], lastSeen: now }
                const lastPoint = trailRecord.points[trailRecord.points.length - 1]
                const moved = !lastPoint || Math.hypot(pointX - lastPoint.x, pointY - lastPoint.y) > 0.5
                const points = moved
                  ? [...trailRecord.points, { x: pointX, y: pointY }].slice(-16)
                  : trailRecord.points
                trajectoryMemoryRef.current.set(id, { points, lastSeen: now })
                const sameClass = last?.detection.class === detection.class
                const smoothed = sameClass ? {
                  ...detection,
                  x: last.detection.x * 0.3 + detection.x * 0.7,
                  y: last.detection.y * 0.3 + detection.y * 0.7,
                  w: last.detection.w * 0.3 + detection.w * 0.7,
                  h: last.detection.h * 0.3 + detection.h * 0.7,
                } : detection

                next.set(id, { detection: { ...smoothed, trail: points }, lastSeen: now })
                freshIds.add(id)
              })

              previous.forEach((record, id) => {
                if (!freshIds.has(id) && now - record.lastSeen < 750) next.set(id, record)
              })
              trajectoryMemoryRef.current.forEach((record, id) => {
                if (now - record.lastSeen > 2500) trajectoryMemoryRef.current.delete(id)
              })

              detectionMemoryRef.current = next
              setCurrentDetections(Array.from(next.values(), record => record.detection))
              if (typeof data.fps === 'number') setFps(data.fps)
              if (typeof data.inference_ms === 'number') setInferenceMs(data.inference_ms)
              if (typeof data.model === 'string') setModelName(data.model)
            }
          } catch (e) {}
        }
        ws.onerror = () => ws.close()
        ws.onclose = () => {
          if (wsRef.current === ws) wsRef.current = null
          scheduleReconnect()
        }
      } catch (e) {
        scheduleReconnect()
      }
    }

    setWsStatus('connecting')
    setCurrentDetections([])
    detectionMemoryRef.current.clear()
    trajectoryMemoryRef.current.clear()
    setFps(null)
    setInferenceMs(null)
    setOpenVocabularyActive(null)
    connect()

    return () => {
      disposed = true
      window.clearTimeout(retryTimer)
      const ws = wsRef.current
      wsRef.current = null
      if (ws) ws.close()
    }
  }, [selectedCam])

  // =============================================
  // Stream live frames to YOLO server
  // Send a bounded frame rate so segmentation cannot build an inference backlog.
  // =============================================
  useEffect(() => {
    if (!isWsConnected || !isPlaying) return

    const canvas = document.createElement('canvas')
    canvas.width = 960
    canvas.height = 540
    const ctx = canvas.getContext('2d')

    const frameInterval = setInterval(() => {
      const vidSource = selectedCam.id === 'cam-webcam' ? webcamVideoRef.current : videoRef.current
      if (
        vidSource &&
        vidSource.readyState >= 2 &&
        wsRef.current &&
        wsRef.current.readyState === WebSocket.OPEN &&
        wsRef.current.bufferedAmount < 1000000
      ) {
        try {
          ctx.drawImage(vidSource, 0, 0, canvas.width, canvas.height)
          const dataUrl = canvas.toDataURL('image/jpeg', 0.55)
          wsRef.current.send(JSON.stringify({
            image: dataUrl,
            prompts: targetPrompts,
            confidence: confidenceThreshold,
          }))
        } catch (e) {}
      }
    }, 250)

    return () => clearInterval(frameInterval)
  }, [selectedCam, isWsConnected, isPlaying, targetPrompts, confidenceThreshold])


  const toggleFullscreen = () => {
    if (!containerRef.current) return
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch(() => {})
    } else {
      document.exitFullscreen().catch(() => {})
    }
  }

  const togglePlayback = () => {
    if (selectedCam.id === 'cam-webcam') return
    if (videoRef.current) {
      if (isPlaying) {
        videoRef.current.pause()
      } else {
        videoRef.current.play()
      }
      setIsPlaying(!isPlaying)
    }
  }

  const triggerRadarScan = () => {
    setIsScanning(true)
    setTimeout(() => setIsScanning(false), 2400)
  }

  const applyOpenVocabularyPrompts = (event) => {
    event.preventDefault()
    const prompts = [...new Set(promptText.split(',').map(prompt => prompt.trim()).filter(Boolean))].slice(0, 12)
    setTargetPrompts(prompts)
    setCurrentDetections([])
    detectionMemoryRef.current.clear()
    trajectoryMemoryRef.current.clear()
  }

  // Only show a geofence where this camera has a configured polygon.
  const activeHazardZone = selectedCam.hazardZone || trackingData[selectedCam.id]?.hazard_zone || null
  const hazardPointsStr = activeHazardZone?.map(p => `${p[0]},${p[1]}`).join(' ')

  // Filter detections based on user selection
  const visibleDetections = currentDetections.filter(d => {
    const isPerson = isPersonDetection(d)
    if (filterMode === 'critical') return isPerson && d.risk_level === 'critical'
    if (filterMode === 'ppe') return isPerson  // Show only persons for PPE scan
    if (filterMode === 'ovs') return Boolean(d.open_vocabulary) && !isPerson
    return true  // 'all' shows everything: persons + objects
  })

  // Alert logic uses all detections so a display filter cannot hide a real alert.
  const criticalRiskDetection = currentDetections.find(d => isPersonDetection(d) && d.risk_level === 'critical')
  const watchedPromptNames = new Set(targetPrompts.map(prompt => prompt.toLocaleLowerCase()))
  const watchlistIntruder = activeHazardZone && currentDetections.find(detection => {
    if (isPersonDetection(detection)) return false
    if (!detection.open_vocabulary && !watchedPromptNames.has((detection.class || '').toLocaleLowerCase())) return false
    const footX = detection.foot_x ?? (detection.x + detection.w / 2)
    const footY = detection.foot_y ?? (detection.y + detection.h)
    return Number.isFinite(footX) && Number.isFinite(footY) &&
      pointInPolygon({ x: footX, y: footY }, activeHazardZone)
  })
  const personIntruder = activeHazardZone && currentDetections.find(detection => {
    if (!isPersonDetection(detection)) return false
    const footX = detection.foot_x ?? (detection.x + detection.w / 2)
    const footY = detection.foot_y ?? (detection.y + detection.h)
    return Number.isFinite(footX) && Number.isFinite(footY) &&
      pointInPolygon({ x: footX, y: footY }, activeHazardZone)
  })
  const alertCameraEnabled = isAlertActive && selectedCam.id !== 'cam-webcam'
  const activeSafetyAlert = !alertCameraEnabled ? null : watchlistIntruder ? {
    type: 'restricted-object',
    severity: 'critical',
    title: 'Monitored object entered restricted area',
    detail: `${watchlistIntruder.class} · ${watchlistIntruder.track_id}`,
    location: selectedCam.location,
  } : personIntruder ? {
    type: 'restricted-person',
    severity: 'critical',
    title: 'Person entered restricted area',
    detail: personIntruder.track_id,
    location: selectedCam.location,
  } : criticalRiskDetection ? {
    type: 'ppe-compliance',
    severity: 'critical',
    title: 'PPE compliance alert',
    detail: `${criticalRiskDetection.track_id} · helmet and high-visibility vest not detected`,
    location: selectedCam.location,
  } : null
  const activeSafetyAlertKey = activeSafetyAlert
    ? `${selectedCam.id}:${activeSafetyAlert.type}:${activeSafetyAlert.title}`
    : ''

  useEffect(() => {
    const reported = reportedSafetyAlertRef.current
    const refreshed = lastAlertRefreshSignalRef.current !== alertRefreshSignal
    lastAlertRefreshSignalRef.current = alertRefreshSignal
    if (refreshed) {
      reported.key = ''
      if (reported.clearTimer) {
        window.clearTimeout(reported.clearTimer)
        reported.clearTimer = null
      }
    }

    if (!activeSafetyAlertKey) {
      if (reported.key && !reported.clearTimer) {
        reported.clearTimer = window.setTimeout(() => {
          reported.key = ''
          reported.clearTimer = null
        }, 1200)
      }
      return
    }

    if (reported.clearTimer) {
      window.clearTimeout(reported.clearTimer)
      reported.clearTimer = null
    }
    if (reported.key === activeSafetyAlertKey) return

    reported.key = activeSafetyAlertKey
    onSafetyAlert?.({
      ...activeSafetyAlert,
      cameraId: selectedCam.id,
    })
  }, [activeSafetyAlertKey, alertRefreshSignal, onSafetyAlert, activeSafetyAlert?.detail, activeSafetyAlert?.location, activeSafetyAlert?.severity, activeSafetyAlert?.title, activeSafetyAlert?.type, selectedCam.id])

  return (
    <div className="card live-vision-card" ref={containerRef}>
      {/* Header Bar */}
      <div className="card-header">
        <div className="vision-header-left">
          <div className="live-pulse-badge">
            <span className="live-dot pulse" /> LIVE AI SCANNER
          </div>
          <select
            className="cam-selector-dropdown"
            value={selectedCam.id}
            onChange={(e) => {
              const found = CAM_FEEDS.find(c => c.id === e.target.value)
              if (found) setSelectedCam(found)
            }}
          >
            {CAM_FEEDS.map(c => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <span className="vision-location-tag">{selectedCam.location}</span>
        </div>

        <div className="vision-header-right">
          <div className="telemetry-chip">
            {isWsConnected ? (
              <span style={{ color: '#10b981', fontWeight: 800, display: 'inline-flex', alignItems: 'center', gap: 3 }}>
                <span className="live-dot pulse" style={{ background: '#10b981', width: 6, height: 6 }} /> PY-WS
                <span className="telemetry-sep">|</span>
              </span>
            ) : null}
            <span className="telemetry-label">FPS:</span>
            <span className="telemetry-val">{fps ?? '--'}</span>
            <span className="telemetry-sep">|</span>
            <span className="telemetry-label">INFERENCE:</span>
            <span className="telemetry-val">{inferenceMs == null ? '--' : `${inferenceMs}ms`}</span>
            <span className="telemetry-sep">|</span>
            <span className="telemetry-label">DETS:</span>
            <span className="telemetry-val">{visibleDetections.length}</span>
          </div>

          <button
            className={`icon-btn ${isScanning ? 'active' : ''}`}
            title="Trigger AI Frame Radar Scan"
            onClick={triggerRadarScan}
          >
            <Scan size={14} />
          </button>
          <button
            className={`icon-btn ${showPPE ? 'active' : ''}`}
            title="Toggle PPE Kit Bounding Boxes (Helmet, Vest, Harness)"
            onClick={() => setShowPPE(!showPPE)}
          >
            <Crosshair size={14} />
          </button>
          <button
            className={`icon-btn ${showOverlays ? 'active' : ''}`}
            title="Toggle Body Bounding Boxes"
            onClick={() => setShowOverlays(!showOverlays)}
          >
            <Eye size={14} />
          </button>
          <button
            className={`icon-btn ${showZones ? 'active' : ''}`}
            title="Toggle Spatial Geofence Zones"
            onClick={() => setShowZones(!showZones)}
          >
            <Layers size={14} />
          </button>
          <button className="icon-btn" title="Fullscreen" onClick={toggleFullscreen}>
            <Maximize2 size={14} />
          </button>
        </div>
      </div>

      <form className="open-vocabulary-controls" onSubmit={applyOpenVocabularyPrompts}>
        <div className="open-vocabulary-copy">
          <strong>Open-vocabulary equipment tracking</strong>
          <span>Comma-separated labels; tracked entries into this camera’s red zone trigger an alert.</span>
        </div>
        <input
          aria-label="Equipment and object prompts"
          className="open-vocabulary-input"
          value={promptText}
          onChange={event => setPromptText(event.target.value)}
          placeholder="forklift truck, generator, gear, bearing"
        />
        <label className="open-vocabulary-threshold">
          CONF {Math.round(confidenceThreshold * 100)}%
          <input
            type="range"
            min="0.05"
            max="0.5"
            step="0.05"
            value={confidenceThreshold}
            onChange={event => setConfidenceThreshold(Number(event.target.value))}
            aria-label="Open-vocabulary confidence threshold"
          />
        </label>
        <button className="open-vocabulary-apply" type="submit">Apply targets</button>
        <span
          className={`open-vocabulary-status ${openVocabularyActive ? 'ready' : openVocabularyActive === false && openVocabularyError ? 'unavailable' : ''}`}
          title={openVocabularyError || (openVocabularyActive ? 'Text-prompted segmentation is active.' : 'Waiting for the first inference frame.')}
        >
          {openVocabularyActive
            ? 'MASKS + TRACKING'
            : openVocabularyActive === false
              ? openVocabularyError ? 'OVS UNAVAILABLE' : targetPrompts.length ? 'OVS INACTIVE' : 'YOLO DETECTION'
              : 'OVS STARTING'}
        </span>
      </form>

      {/* Main Vision Viewport */}
      <div className="vision-viewport">
        {/* Real Video Stream / Webcam */}
        {selectedCam.id === 'cam-webcam' ? (
          <div className="webcam-container">
            <video
              ref={webcamVideoRef}
              className="vision-media-element"
              autoPlay
              playsInline
              muted
            />
            {!webcamActive && (
              <div className="webcam-permission-msg">
                <VideoOff size={32} />
                <p>Requesting Webcam Access...</p>
                <button className="btn-retry" onClick={startWebcam}>Retry Access</button>
              </div>
            )}
          </div>
        ) : (
          <video
            ref={videoRef}
            key={selectedCam.src}
            className="vision-media-element"
            src={selectedCam.src}
            autoPlay
            loop
            muted
            playsInline
          />
        )}

        {/* HUD Scanner Grid & Animated Scanline */}
        <div className="hud-overlay-grid" />
        <div className={`hud-scanline ${isScanning ? 'scanning-laser' : ''}`} />

        {/* Spatial Hazard Zone Geofencing Polygon (Videos only) */}
        {showZones && activeHazardZone && selectedCam.id !== 'cam-webcam' && (
          <svg className="hazard-zone-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
            <defs>
              <pattern id="hazardStripe" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                <line x1="0" y1="0" x2="0" y2="6" stroke="rgba(239, 68, 68, 0.35)" strokeWidth="3" />
              </pattern>
            </defs>
            <polygon
              points={hazardPointsStr}
              className="hazard-polygon pulse-poly"
              fill="url(#hazardStripe)"
            />
            <polygon
              points={hazardPointsStr}
              fill="none"
              stroke="#ef4444"
              strokeWidth="0.6"
              strokeDasharray="2 1"
            />
          </svg>
        )}

        {showOverlays && (
          <svg className="segmentation-mask-layer" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            {visibleDetections.filter(detection => detection.mask_polygon?.length >= 3).map(detection => {
              const points = detection.mask_polygon.map(([x, y]) => `${x},${y}`).join(' ')
              const color = getDetectionColor(detection)
              return (
                <polygon
                  key={`mask-${detection.track_id}`}
                  points={points}
                  fill={color}
                  fillOpacity="0.25"
                  stroke={color}
                  strokeWidth="0.28"
                  vectorEffect="non-scaling-stroke"
                />
              )
            })}
          </svg>
        )}

        {showOverlays && visibleDetections.some(detection => detection.open_vocabulary && detection.trail?.length > 1) && (
          <svg className="object-trail-layer" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
            {visibleDetections.filter(detection => detection.open_vocabulary && detection.trail?.length > 1).map(detection => (
              <polyline
                key={`trail-${detection.track_id}`}
                points={detection.trail.map(point => `${point.x},${point.y}`).join(' ')}
                fill="none"
                stroke={getDetectionColor(detection)}
                strokeWidth="0.35"
                strokeDasharray="0.8 0.5"
                vectorEffect="non-scaling-stroke"
              />
            ))}
          </svg>
        )}

        {/* Dynamic Laser Proximity Vectors (Videos only) */}
        {showVectors && showZones && activeHazardZone && selectedCam.id !== 'cam-webcam' && (
          <svg className="proximity-vectors-svg" viewBox="0 0 100 100" preserveAspectRatio="none">
            {visibleDetections.map((det) => {
              const hzCenter = activeHazardZone[0] || [35, 60]
              const isCrit = det.risk_level === 'critical'
              const color = isCrit ? '#ef4444' : det.risk_level === 'warning' ? '#f59e0b' : '#10b981'
              return (
                <g key={`vec-${det.track_id}`}>
                  <line
                    x1={det.foot_x}
                    y1={det.foot_y}
                    x2={hzCenter[0]}
                    y2={hzCenter[1]}
                    stroke={color}
                    strokeWidth="0.4"
                    strokeDasharray={isCrit ? "1.5 1" : "3 2"}
                    className={isCrit ? "laser-line-pulse" : ""}
                  />
                  <circle cx={det.foot_x} cy={det.foot_y} r="0.8" fill={color} />
                  <circle cx={hzCenter[0]} cy={hzCenter[1]} r="0.6" fill={color} />
                </g>
              )
            })}
          </svg>
        )}

        {/* ========================================================
            UNIFIED REAL-TIME DETECTION RENDERER
            Works for ALL modes: webcam, video files, WS live stream
            Step 1: Renders ALL detected objects (person, chair, car, etc.)
            Step 2: For persons only, adds PPE sub-boxes (helmet, vest)
            ======================================================== */}
        {showOverlays && (selectedCam.id !== 'cam-webcam' || (webcamActive && isWsConnected)) && visibleDetections.map((det) => {
          const isPerson = det.is_person || det.class === 'Person' || det.class === 'person'
          const isCritical = det.risk_level === 'critical'
          const isWarning = det.risk_level === 'warning'
          const helmet = det.ppe?.helmet
          const vest = det.ppe?.vest
          const harness = det.ppe?.harness

          // Color: vibrant high-visibility colors
          const boxColor = isPerson
            ? (isCritical ? '#ff1744' : isWarning ? '#ffea00' : '#00e676')
            : getDetectionColor(det)

          // CSS class for risk-based styling (person) or generic object
          const riskClass = isPerson
            ? (det.risk_level || 'safe')
            : 'object'

          return (
            <div key={det.track_id}>
              {/* Main Bounding Box for ANY detected object */}
              <div
                className={`ai-bbox bbox-${riskClass}`}
                style={{
                  '--bbox-color': boxColor,
                  left: `${det.x}%`,
                  top: `${det.y}%`,
                  width: `${det.w}%`,
                  height: `${det.h}%`,
                  borderColor: boxColor,
                }}
              >
                <div className="corner top-left" style={{ borderColor: boxColor }} />
                <div className="corner top-right" style={{ borderColor: boxColor }} />
                <div className="corner bottom-left" style={{ borderColor: boxColor }} />
                <div className="corner bottom-right" style={{ borderColor: boxColor }} />

                {/* Object Class Tag */}
                <div
                  className="bbox-tag"
                  style={{ background: boxColor, color: (isWarning ? '#000' : '#fff') }}
                >
                  <span className="bbox-id">{det.track_id}</span>
                  <span className="bbox-type">
                    {det.class} [{det.confidence}%]
                  </span>
                  {isPerson && isCritical && (
                    <span className="bbox-alert-pill">NO PPE ⚠️</span>
                  )}
                  {isPerson && !isCritical && !isWarning && (
                    <span className="bbox-alert-pill" style={{ color: '#00e676' }}>COMPLIANT ✓</span>
                  )}
                </div>

                {/* Meta info: Person gets safety telemetry, objects get simple label */}
                <div className="bbox-meta">
                  {isPerson ? (
                    <>
                      <div className="bbox-meta-row">
                        <span className="meta-k">HELMET:</span>
                        <span className={`meta-v ${helmet?.detected ? 'text-success' : 'text-critical'}`}>
                          {helmet?.detected ? `YES [${helmet.confidence}%]` : 'NOT DETECTED ⚠️'}
                        </span>
                      </div>
                      <div className="bbox-meta-row">
                        <span className="meta-k">VEST:</span>
                        <span className={`meta-v ${vest?.detected ? 'text-success' : 'text-critical'}`}>
                          {vest?.detected ? `YES [${vest.confidence}%]` : 'NOT DETECTED ⚠️'}
                        </span>
                      </div>
                      {det.dwell_time != null && (
                        <div className="bbox-meta-row">
                          <span className="meta-k">DWELL:</span>
                          <span className="meta-v">{det.dwell_time}s</span>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="bbox-meta-row">
                      <span className="meta-k">TYPE:</span>
                      <span className="meta-v">{det.class}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* PPE Sub-Boxes: ONLY rendered for Person detections */}
              {isPerson && showPPE && helmet?.box && (
                <div
                  className={`ppe-sub-box ppe-helmet ${helmet.detected ? 'ppe-ok' : 'ppe-missing pulse-glow-red'}`}
                  style={{
                    left: `${helmet.box.x}%`,
                    top: `${helmet.box.y}%`,
                    width: `${helmet.box.w}%`,
                    height: `${helmet.box.h}%`
                  }}
                >
                  <span className="ppe-tag font-mono">
                    {helmet.detected ? `Hardhat ✓ [${helmet.confidence}%]` : `NO HARDHAT ⚠️`}
                  </span>
                </div>
              )}

              {isPerson && showPPE && vest?.box && (
                <div
                  className={`ppe-sub-box ppe-vest ${vest.detected ? 'ppe-ok' : 'ppe-missing'}`}
                  style={{
                    left: `${vest.box.x}%`,
                    top: `${vest.box.y}%`,
                    width: `${vest.box.w}%`,
                    height: `${vest.box.h}%`
                  }}
                >
                  <span className="ppe-tag font-mono">
                    {vest.detected ? `Safety Vest ✓ [${vest.confidence}%]` : `NO VEST ⚠️`}
                  </span>
                </div>
              )}

              {/* Distance badge: only for persons with foot position */}
              {isPerson && det.foot_x != null && det.dist_m != null && (
                <div
                  className="live-distance-badge font-mono"
                  style={{
                    left: `${det.foot_x}%`,
                    top: `${Math.min(92, (det.foot_y || det.y + det.h) + 1)}%`
                  }}
                >
                  <span>DIST: {det.dist_m}m</span>
                </div>
              )}
            </div>
          )
        })}

        {/* Hazard Zone Label */}
        {showZones && activeHazardZone && selectedCam.id !== 'cam-webcam' && (
          <div
            className="hazard-zone-badge"
            style={{
              left: `${activeHazardZone[0]?.[0] || 25}%`,
              top: `${activeHazardZone[0]?.[1] || 45}%`
            }}
          >
            <AlertTriangle size={12} />
            <span>CONFIGURED RESTRICTED AREA</span>
          </div>
        )}

        {/* Live HUD Cam Watermark */}
        <div className="hud-cam-watermark">
          <div className="hud-cam-header">
            <Radio size={12} className="pulse text-critical" />
            <span className="font-mono">{selectedCam.name}</span>
          </div>
          <div className="hud-cam-sub font-mono">
            <span>MODEL: {modelName}</span>
            <span style={{ color: isWsConnected ? '#10b981' : wsStatus === 'offline' ? '#f87171' : '#fbbf24' }}>
              SCAN MODE: {isWsConnected ? 'LIVE INFERENCE' : wsStatus === 'offline' ? 'SERVER OFFLINE · RETRYING' : 'CONNECTING...'}
            </span>
          </div>
        </div>

        {/* Critical Alarm Banner */}
        {activeSafetyAlert && (
          <div className="onscreen-hazard-alert">
            <ShieldAlert size={16} className="text-critical pulse" />
            <span>{activeSafetyAlert.title.toLocaleUpperCase()}</span>
          </div>
        )}

        {/* Video Control Bar */}
        <div className="vision-control-bar">
          <div className="control-left">
            <button className="ctrl-btn" onClick={togglePlayback} title={isPlaying ? "Pause" : "Play"}>
              {isPlaying ? <Pause size={14} /> : <Play size={14} />}
            </button>
            <div className="filter-pill-group">
              <button
                className={`filter-pill ${filterMode === 'all' ? 'active' : ''}`}
                onClick={() => setFilterMode('all')}
              >
                All Detections
              </button>
              <button
                className={`filter-pill ${filterMode === 'critical' ? 'active' : ''}`}
                onClick={() => setFilterMode('critical')}
              >
                Critical Risk Only
              </button>
              <button
                className={`filter-pill ${filterMode === 'ppe' ? 'active' : ''}`}
                onClick={() => setFilterMode('ppe')}
              >
                PPE Kit Scanner
              </button>
              <button
                className={`filter-pill ${filterMode === 'ovs' ? 'active' : ''}`}
                onClick={() => setFilterMode('ovs')}
                title="Open-vocabulary equipment tracking detections"
                aria-pressed={filterMode === 'ovs'}
              >
                OVET
              </button>
            </div>
          </div>

          <div className="control-right">
            <button
              className={`ctrl-btn ${isAlertActive ? 'alert-on' : ''}`}
              onClick={() => setIsAlertActive(!isAlertActive)}
              title="Toggle Audio-Visual Alarm"
            >
              {isAlertActive ? <Volume2 size={14} /> : <VolumeX size={14} />}
            </button>
            <button
              className="ctrl-btn-action"
              onClick={triggerRadarScan}
            >
              <Sparkles size={12} style={{ display: 'inline', marginRight: 4 }} />
              Scan Video Frame
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
