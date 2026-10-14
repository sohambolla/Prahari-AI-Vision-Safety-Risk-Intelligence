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

function App() {
  const [currentTime, setCurrentTime] = useState(new Date())
  const [safetyAlerts, setSafetyAlerts] = useState([])
  const [alertRefreshSignal, setAlertRefreshSignal] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000)
    return () => clearInterval(timer)
  }, [])

  const formatTime = (d) =>
    d.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })

  const formatDate = (d) =>
    d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })

  const handleSafetyAlert = useCallback((alert) => {
    const createdAt = new Date()
    setSafetyAlerts(previous => [{
      ...alert,
      id: `${alert.cameraId}-${alert.type}-${createdAt.getTime()}`,
      time: createdAt.toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }),
    }, ...previous].slice(0, 20))
  }, [])

  const refreshSafetyAlerts = useCallback(() => {
    setSafetyAlerts([])
    setAlertRefreshSignal(signal => signal + 1)
  }, [])

  return (
    <>
      <Header time={formatTime(currentTime)} date={formatDate(currentTime)} />

      {/* Row 1: Live Vision + Alerts + Replay */}
      <div className="dashboard-grid">
        <div className="col-5" style={{ animationDelay: '0.1s' }}>
          <LiveVisionPanel
            time={formatTime(currentTime)}
            onSafetyAlert={handleSafetyAlert}
            alertRefreshSignal={alertRefreshSignal}
          />
        </div>
        <div className="col-3" style={{ animationDelay: '0.2s' }}>
          <LiveAlerts alerts={safetyAlerts} onRefresh={refreshSafetyAlerts} />
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
    </>
  )
}

export default App
