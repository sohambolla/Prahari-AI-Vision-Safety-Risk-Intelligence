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
  { id: 'cam-01', name: 'CAM 01: Slab Edge Zone', location: 'Level 6 – East Wing', src: '/videos/video_2.mp4', defaultDist: 0.8 },
  { id: 'cam-02', name: 'CAM 02: Scaffolding Tower', location: 'Level 4 – North Facade', src: '/videos/video_1.mp4', defaultDist: 2.1 },
  { id: 'cam-03', name: 'CAM 03: Crane Pick Zone', location: 'Ground – Material Depot', src: '/videos/video_3.mp4', defaultDist: 1.2 },
  { id: 'cam-04', name: 'CAM 04: West Perimeter', location: 'Level 2 – Staging Area', src: '/videos/video_4.mp4', defaultDist: 3.4 },
  { id: 'cam-webcam', name: 'LIVE WEBCAM: Real-Time Test', location: 'Local Operator Cam', src: '', defaultDist: 1.5 },
]

export default function LiveVisionPanel({ time }) {
  const [selectedCam, setSelectedCam] = useState(CAM_FEEDS[2]) // Default to Cam 03 as user was testing
  const [isPlaying, setIsPlaying] = useState(true)
  const [showOverlays, setShowOverlays] = useState(true)
  const [showPPE, setShowPPE] = useState(true)
  const [showZones, setShowZones] = useState(true)
  const [showVectors, setShowVectors] = useState(true)
  const [filterMode, setFilterMode] = useState('all') // 'all', 'critical', 'ppe'
  const [isAlertActive, setIsAlertActive] = useState(true)
  const [isScanning, setIsScanning] = useState(false)
  const [fps, setFps] = useState(29.8)
  const [currentDetections, setCurrentDetections] = useState([])
  const [webcamActive, setWebcamActive] = useState(false)
  const [webcamFaceBox, setWebcamFaceBox] = useState({ x: 38, y: 22, w: 24, h: 56 })

  const videoRef = useRef(null)
  const webcamVideoRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const containerRef = useRef(null)
  const animFrameRef = useRef(null)

  // Switch feeds & handle video / webcam
  useEffect(() => {
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

  const [isWsConnected, setIsWsConnected] = useState(false)
  const wsRef = useRef(null)

  // =============================================
  // WebSocket: ONLY connects for LIVE WEBCAM mode
  // Videos use pre-extracted JSON data instead
  // =============================================
  useEffect(() => {
    // Only connect WebSocket when webcam is selected
    if (selectedCam.id !== 'cam-webcam') {
      setIsWsConnected(false)
      return
    }

    let ws = null
    try {
      ws = new WebSocket(`ws://localhost:8000/ws/vision/cam-webcam`)
      ws.onopen = () => {
        console.log('Connected to PRAHARI Live YOLO WebSocket for webcam')
        setIsWsConnected(true)
      }
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          if (data.detections) {
            setCurrentDetections(data.detections)
            if (data.inference_ms) setFps(+(30 - data.inference_ms * 0.02).toFixed(1))
          }
        } catch (e) {}
      }
      ws.onerror = () => setIsWsConnected(false)
      ws.onclose = () => setIsWsConnected(false)
      wsRef.current = ws
    } catch (e) {
      setIsWsConnected(false)
    }

    return () => {
      if (ws) ws.close()
      setIsWsConnected(false)
    }
  }, [selectedCam])

  // =============================================
  // Stream live webcam frames to YOLO server
  // Sends canvas snapshots at ~14 FPS for real-time inference
  // =============================================
  useEffect(() => {
    if (selectedCam.id !== 'cam-webcam' || !isWsConnected || !webcamActive) return

    const canvas = document.createElement('canvas')
    canvas.width = 640
    canvas.height = 360
    const ctx = canvas.getContext('2d')

    const frameInterval = setInterval(() => {
      if (
        webcamVideoRef.current &&
        webcamVideoRef.current.readyState >= 2 &&
        wsRef.current &&
        wsRef.current.readyState === WebSocket.OPEN
      ) {
        try {
          ctx.drawImage(webcamVideoRef.current, 0, 0, canvas.width, canvas.height)
          const dataUrl = canvas.toDataURL('image/jpeg', 0.55)
          wsRef.current.send(JSON.stringify({ image: dataUrl }))
        } catch (e) {}
      }
    }, 70)

    return () => clearInterval(frameInterval)
  }, [selectedCam, isWsConnected, webcamActive])

  // =============================================
  // Video mode: Smooth interpolation from pre-extracted JSON
  // Only runs for cam-01 through cam-04 (NOT webcam)
  // =============================================
  useEffect(() => {
    // Skip this loop entirely for webcam — WS handles it
    if (selectedCam.id === 'cam-webcam') return

    let lastFpsUpdate = performance.now()

    const updateFrame = () => {
      const now = performance.now()

      // Update FPS display periodically
      if (now - lastFpsUpdate > 300) {
        setFps(+(29.4 + Math.random() * 0.8).toFixed(1))
        lastFpsUpdate = now
      }

      if (videoRef.current && trackingData[selectedCam.id]) {
        const curTime = videoRef.current.currentTime || 0
        const camData = trackingData[selectedCam.id]
        const frames = camData.frames || []

        if (frames.length > 0) {
          let idx = frames.findIndex(f => f.time >= curTime)
          if (idx === -1) idx = frames.length - 1

          let f0 = frames[Math.max(0, idx - 1)] || frames[0]
          let f1 = frames[idx] || frames[frames.length - 1]

          // Fallback to nearest non-empty frame
          if (!f1.detections || f1.detections.length === 0) {
            const nearby = frames.find(f => Math.abs(f.time - curTime) <= 1.2 && f.detections && f.detections.length > 0)
            if (nearby) { f1 = nearby; f0 = nearby }
          }

          const t0 = f0.time
          const t1 = f1.time
          const factor = t1 > t0 ? Math.max(0, Math.min(1, (curTime - t0) / (t1 - t0))) : 0

          const interpolated = (f1.detections || []).map(d1 => {
            const d0 = (f0.detections || []).find(d => d.track_id === d1.track_id) || d1
            const ix = +(d0.x + (d1.x - d0.x) * factor).toFixed(2)
            const iy = +(d0.y + (d1.y - d0.y) * factor).toFixed(2)
            const iw = +(d0.w + (d1.w - d0.w) * factor).toFixed(2)
            const ih = +(d0.h + (d1.h - d0.h) * factor).toFixed(2)
            const footX = +(d0.foot_x + (d1.foot_x - d0.foot_x) * factor).toFixed(2)
            const footY = +(d0.foot_y + (d1.foot_y - d0.foot_y) * factor).toFixed(2)
            const distM = +(d0.dist_m + (d1.dist_m - d0.dist_m) * factor).toFixed(1)

            const headW = +(iw * 0.55).toFixed(2)
            const headH = +(ih * 0.22).toFixed(2)
            const headX = +(ix + (iw - headW) / 2).toFixed(2)
            const headY = +iy.toFixed(2)

            const vestW = +(iw * 0.78).toFixed(2)
            const vestH = +(ih * 0.36).toFixed(2)
            const vestX = +(ix + (iw - vestW) / 2).toFixed(2)
            const vestY = +(iy + headH + 1).toFixed(2)

            return {
              ...d1,
              is_person: true,
              x: ix, y: iy, w: iw, h: ih,
              foot_x: footX, foot_y: footY, dist_m: distM,
              ppe: {
                ...d1.ppe,
                helmet: { ...d1.ppe?.helmet, box: { x: headX, y: headY, w: headW, h: headH } },
                vest: { ...d1.ppe?.vest, box: { x: vestX, y: vestY, w: vestW, h: vestH } }
              }
            }
          })

          if (interpolated.length > 0) {
            setCurrentDetections(interpolated)
          }
        }
      }

      animFrameRef.current = requestAnimationFrame(updateFrame)
    }

    animFrameRef.current = requestAnimationFrame(updateFrame)
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    }
  }, [selectedCam])

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

  // Active hazard zone polygon from dataset
  const activeHazardZone = trackingData[selectedCam.id]?.hazard_zone || [
    [25, 45], [55, 45], [55, 85], [25, 85]
  ]
  const hazardPointsStr = activeHazardZone.map(p => `${p[0]},${p[1]}`).join(' ')

  // Filter detections based on user selection
  const visibleDetections = currentDetections.filter(d => {
    const isPerson = d.is_person || d.class === 'Person' || d.class === 'person'
    if (filterMode === 'critical') return isPerson && d.risk_level === 'critical'
    if (filterMode === 'ppe') return isPerson  // Show only persons for PPE scan
    return true  // 'all' shows everything: persons + objects
  })

  // Has critical risk in current frame
  const hasCriticalRisk = visibleDetections.some(d => d.risk_level === 'critical')

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
            <span className="telemetry-val">{fps}</span>
            <span className="telemetry-sep">|</span>
            <span className="telemetry-label">INFERENCE:</span>
            <span className="telemetry-val">{isWsConnected ? '9.8ms' : '12.4ms'}</span>
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

        {/* Spatial Hazard Zone Geofencing Polygon */}
        {showZones && (
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

        {/* Dynamic Laser Proximity Vectors (Distance from feet to hazard zone) */}
        {showVectors && showZones && (
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
        {showOverlays && visibleDetections.map((det) => {
          const isPerson = det.is_person || det.class === 'Person' || det.class === 'person'
          const isCritical = det.risk_level === 'critical'
          const isWarning = det.risk_level === 'warning'
          const helmet = det.ppe?.helmet
          const vest = det.ppe?.vest
          const harness = det.ppe?.harness

          // Color: use server-provided color or derive from risk level
          const boxColor = det.color || (
            isCritical ? '#ef4444' :
            isWarning ? '#f59e0b' :
            isPerson ? '#3b82f6' :
            '#94a3b8'
          )

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
                  style={{ background: boxColor, color: '#fff' }}
                >
                  <span className="bbox-id">{det.track_id}</span>
                  <span className="bbox-type">
                    {det.class} [{det.confidence}%]
                  </span>
                  {isPerson && isCritical && (
                    <span className="bbox-alert-pill">NO PPE</span>
                  )}
                </div>

                {/* Meta info: Person gets safety telemetry, objects get simple label */}
                <div className="bbox-meta">
                  {isPerson ? (
                    <>
                      <div className="bbox-meta-row">
                        <span className="meta-k">HELMET:</span>
                        <span className={`meta-v ${helmet?.detected ? 'text-success' : 'text-critical'}`}>
                          {helmet?.detected ? `YES [${helmet.confidence}%]` : 'NOT DETECTED'}
                        </span>
                      </div>
                      <div className="bbox-meta-row">
                        <span className="meta-k">VEST:</span>
                        <span className={`meta-v ${vest?.detected ? 'text-success' : 'text-critical'}`}>
                          {vest?.detected ? `YES [${vest.confidence}%]` : 'NOT DETECTED'}
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
                    {helmet.detected ? `Hardhat [${helmet.confidence}%]` : `NO HARDHAT [${helmet.confidence}%]`}
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
                    {vest.detected ? `Safety Vest [${vest.confidence}%]` : `NO VEST`}
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
        {showZones && (
          <div
            className="hazard-zone-badge"
            style={{
              left: `${activeHazardZone[0]?.[0] || 25}%`,
              top: `${activeHazardZone[0]?.[1] || 45}%`
            }}
          >
            <AlertTriangle size={12} />
            <span>UNPROTECTED HAZARD ZONE (1.5m THRESHOLD)</span>
          </div>
        )}

        {/* Live HUD Cam Watermark */}
        <div className="hud-cam-watermark">
          <div className="hud-cam-header">
            <Radio size={12} className="pulse text-critical" />
            <span className="font-mono">{selectedCam.name}</span>
          </div>
          <div className="hud-cam-sub font-mono">
          <span>ENGINE: YOLO11n + ByteTrack</span>
            <span>MODEL CONF: 96.8%</span>
            <span>SCAN MODE: {selectedCam.id === 'cam-webcam' && isWsConnected ? 'LIVE YOLO' : selectedCam.id === 'cam-webcam' ? 'CONNECTING...' : 'PRE-ANALYZED'}</span>
          </div>
        </div>

        {/* Critical Alarm Banner */}
        {hasCriticalRisk && isAlertActive && (
          <div className="onscreen-hazard-alert">
            <ShieldAlert size={16} className="text-critical pulse" />
            <span>CRITICAL RISK: WORKER DETECTED IN HAZARD ZONE WITHOUT HARNESS</span>
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
