import { useState, useRef, useEffect } from 'react'
import { Play, Pause, SkipBack, SkipForward, Volume2, Video, AlertCircle } from 'lucide-react'
import './EventReplay.css'

export default function EventReplay() {
  const [playing, setPlaying] = useState(false)
  const [progress, setProgress] = useState(30)
  const [currentTimeText, setCurrentTimeText] = useState('00:03')
  const [durationText, setDurationText] = useState('00:10')
  const videoRef = useRef(null)

  const metadata = [
    { label: 'Event ID', value: 'EV-904 (Critical Flag)' },
    { label: 'Event Type', value: 'Edge Zone Intrusion' },
    { label: 'Location', value: 'Level 6 – East Wing (CAM-01)' },
    { label: 'PPE Status', value: 'Missing Safety Harness', highlight: true },
    { label: 'Distance to Fall Edge', value: '0.8 m (Threshold: 1.5m)', critical: true },
    { label: 'Inference Model', value: 'YOLO11n + ByteTrack (96.8%)' },
    { label: 'Automated Action', value: 'Siren Activated & SMS Alert Sent' },
  ]

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const cur = videoRef.current.currentTime
      const dur = videoRef.current.duration || 10
      const pct = (cur / dur) * 100
      setProgress(pct)
      
      const mins = Math.floor(cur / 60)
      const secs = Math.floor(cur % 60)
      setCurrentTimeText(`00:${secs < 10 ? '0' : ''}${secs}`)
    }
  }

  const handleLoadedMetadata = () => {
    if (videoRef.current) {
      const dur = videoRef.current.duration || 10
      const secs = Math.floor(dur % 60)
      setDurationText(`00:${secs < 10 ? '0' : ''}${secs}`)
    }
  }

  const togglePlay = () => {
    if (videoRef.current) {
      if (playing) {
        videoRef.current.pause()
      } else {
        videoRef.current.play()
      }
      setPlaying(!playing)
    }
  }

  const handleSeek = (e) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const pos = (e.clientX - rect.left) / rect.width
    if (videoRef.current && videoRef.current.duration) {
      videoRef.current.currentTime = pos * videoRef.current.duration
      setProgress(pos * 100)
    }
  }

  return (
    <div className="card replay-card">
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <AlertCircle size={14} className="text-critical" />
          <span className="card-title">Incident Event Replay</span>
        </div>
        <span className="replay-timestamp">TODAY • 14:27:18 IST</span>
      </div>

      {/* Video Preview Area */}
      <div className="replay-viewport">
        <video
          ref={videoRef}
          className="replay-video-element"
          src="/videos/video_3.mp4"
          muted
          loop
          playsInline
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
        />

        {/* HUD Overlay Annotation */}
        <div className="replay-annotation">
          <span className="ann-label">PROXIMITY: 0.8m</span>
          <span className="ann-value">Dwell: 6.2s • Fall Risk</span>
        </div>

        {/* Playback Controls */}
        <div className="replay-controls">
          <div className="replay-progress-bar" onClick={handleSeek}>
            <div className="replay-progress-fill" style={{ width: `${progress}%` }} />
            <div className="replay-progress-thumb" style={{ left: `${progress}%` }} />
          </div>
          <div className="replay-buttons">
            <span className="replay-time-label">{currentTimeText} / {durationText}</span>
            <div className="replay-btn-group">
              <button className="replay-btn" onClick={() => { if (videoRef.current) videoRef.current.currentTime -= 2 }}>
                <SkipBack size={12} />
              </button>
              <button className="replay-btn play-btn" onClick={togglePlay}>
                {playing ? <Pause size={14} /> : <Play size={14} />}
              </button>
              <button className="replay-btn" onClick={() => { if (videoRef.current) videoRef.current.currentTime += 2 }}>
                <SkipForward size={12} />
              </button>
            </div>
            <div className="replay-speed">
              <span>HD 1080p</span>
            </div>
          </div>
        </div>
      </div>

      {/* Metadata Table */}
      <div className="replay-meta">
        {metadata.map((m, i) => (
          <div key={i} className="meta-row">
            {m.label && <span className="meta-label">{m.label}</span>}
            <span className={`meta-value ${m.critical ? 'meta-critical' : ''} ${m.highlight ? 'meta-highlight' : ''}`}>
              {m.value}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
