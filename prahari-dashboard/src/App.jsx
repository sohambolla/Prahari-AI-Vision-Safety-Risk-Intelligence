import { useState, useEffect, useCallback } from 'react'
import './index.css'
import Header from './components/Header'
import LiveVisionPanel from './components/LiveVisionPanel'
import LiveAlerts from './components/LiveAlerts'
import EventReplay from './components/EventReplay'
import SafetyOverview from './components/SafetyOverview'
import TopRiskCategories from './components/TopRiskCategories'
import RiskHeatmap from './components/RiskHeatmap'
import ResourceMonitoring from './components/ResourceMonitoring'
import SystemArchitecture from './components/SystemArchitecture'
import MVPTimeline from './components/MVPTimeline'
import MachineRegistry from './components/MachineRegistry'

function App() {
  const [currentTime, setCurrentTime] = useState(new Date())
  const [safetyAlerts, setSafetyAlerts] = useState([])
  const apiBase = (import.meta.env.VITE_VISION_API_URL ||
    `${window.location.protocol}//${window.location.hostname || 'localhost'}:8000`).replace(/\/$/, '')

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const formatTime = (d) =>
    d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })

  const formatDate = (d) =>
    d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })

  const handleSafetyAlert = useCallback((event) => {
    const timestamp = Number(event.timestamp)
    const eventTime = Number.isFinite(timestamp) && timestamp > 0 ? new Date(timestamp * 1000) : new Date()
    const eventId = event.event_id || event.id || `${event.camera_id || event.cameraId}-${event.event_type || event.type}-${eventTime.getTime()}`
    const cameraId = event.camera_id || event.cameraId || ''
    const location = event.location || [cameraId, event.zone_id].filter(Boolean).join(' · ') || 'Site location unavailable'
    const normalized = {
      ...event,
      id: eventId,
      event_id: event.event_id || eventId,
      cameraId,
      type: event.event_type || event.type || 'safety-event',
      severity: String(event.severity || 'warning').toLowerCase(),
      title: event.title || 'Safety incident',
      detail: event.detail || '',
      location,
      time: eventTime.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }),
    }
    setSafetyAlerts(previous => [normalized, ...previous.filter(item => item.id !== eventId)].slice(0, 200))
  }, [])

  useEffect(() => {
    let disposed = false
    let retryTimer
    let socket
    let retryDelay = 1000

    fetch(`${apiBase}/api/safety/events?limit=20`)
      .then(response => response.ok ? response.json() : Promise.reject(new Error('Incident history unavailable')))
      .then(payload => { if (!disposed) (payload.events || []).slice().reverse().forEach(handleSafetyAlert) })
      .catch(() => {})

    const connect = () => {
      if (disposed) return
      const wsBase = apiBase.replace(/^http/, 'ws')
      try {
        socket = new WebSocket(`${wsBase}/ws/safety-alerts`)
        socket.onopen = () => { retryDelay = 1000 }
        socket.onmessage = message => {
          try {
            const payload = JSON.parse(message.data)
            if (payload.incident) handleSafetyAlert(payload.incident)
          } catch {}
        }
        socket.onclose = () => {
          if (disposed) return
          retryTimer = window.setTimeout(connect, retryDelay)
          retryDelay = Math.min(10000, retryDelay * 2)
        }
        socket.onerror = () => socket.close()
      } catch {
        retryTimer = window.setTimeout(connect, retryDelay)
        retryDelay = Math.min(10000, retryDelay * 2)
      }
    }
    connect()

    return () => {
      disposed = true
      window.clearTimeout(retryTimer)
      socket?.close()
    }
  }, [apiBase, handleSafetyAlert])

  const refreshSafetyAlerts = useCallback(async () => {
    try {
      const response = await fetch(`${apiBase}/api/safety/events?limit=200`)
      if (!response.ok) return
      const payload = await response.json()
      setSafetyAlerts([])
      ;(payload.events || []).slice().reverse().forEach(handleSafetyAlert)
    } catch {}
  }, [apiBase, handleSafetyAlert])

  const handleAlertAction = useCallback(async (alert, action) => {
    if (!alert.event_id) return
    try {
      const response = await fetch(`${apiBase}/api/safety/events/${encodeURIComponent(alert.event_id)}/actions/${action}`, { method: 'POST' })
      if (response.ok) handleSafetyAlert(await response.json())
    } catch {}
  }, [apiBase, handleSafetyAlert])

  return (
    <>
      <Header time={formatTime(currentTime)} date={formatDate(currentTime)} />

      {/* Row 1: Live Vision + Alerts + Replay */}
      <div className="dashboard-grid">
        <div className="col-5" style={{ animationDelay: '0.1s' }}>
          <LiveVisionPanel
            time={formatTime(currentTime)}
          />
        </div>
        <div className="col-3" style={{ animationDelay: '0.2s' }}>
          <LiveAlerts alerts={safetyAlerts} onRefresh={refreshSafetyAlerts} onAction={handleAlertAction} />
        </div>
        <div className="col-4" style={{ animationDelay: '0.3s' }}>
          <EventReplay />
        </div>
      </div>

      {/* Row 2: Safety Overview + Risk Categories + Heatmap + Resources */}
      <div className="dashboard-grid" style={{ paddingTop: 0 }}>
        <div className="col-3" style={{ animationDelay: '0.35s' }}>
          <SafetyOverview />
        </div>
        <div className="col-3" style={{ animationDelay: '0.4s' }}>
          <TopRiskCategories />
        </div>
        <div className="col-3" style={{ animationDelay: '0.45s' }}>
          <RiskHeatmap />
        </div>
        <div className="col-3" style={{ animationDelay: '0.5s' }}>
          <ResourceMonitoring />
        </div>
      </div>

      {/* Row 3: Architecture + MVP Plan */}
      <div className="dashboard-grid" style={{ paddingTop: 0 }}>
        <div className="col-6" style={{ animationDelay: '0.55s' }}>
          <SystemArchitecture />
        </div>
        <div className="col-6" style={{ animationDelay: '0.6s' }}>
          <MVPTimeline />
        </div>
      </div>

      <div className="dashboard-grid" style={{ paddingTop: 0 }}>
        <div className="col-12" style={{ animationDelay: '0.65s' }}>
          <MachineRegistry />
        </div>
      </div>
    </>
  )
}

export default App
