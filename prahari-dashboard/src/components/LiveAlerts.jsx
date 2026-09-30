import { useState, useEffect } from 'react'
import { AlertTriangle, ChevronRight, MapPin } from 'lucide-react'
import './LiveAlerts.css'

const ALERTS_DATA = [
  {
    id: 1, severity: 'critical', time: '14:27:18',
    title: 'Worker near unprotected edge',
    detail: '(0.8 m for 6 sec)',
    location: 'Level 6 – East Wing'
  },
  {
    id: 2, severity: 'warning', time: '14:26:31',
    title: 'Scaffold overcrowded',
    detail: '5 workers (limit 3)',
    location: 'Level 6 – East Wing'
  },
  {
    id: 3, severity: 'critical', time: '14:25:10',
    title: 'Worker without helmet',
    detail: '',
    location: 'Level 6 – East Wing'
  },
  {
    id: 4, severity: 'warning', time: '14:23:04',
    title: 'Person under suspended load zone',
    detail: '',
    location: 'Level 4 – Crane 01'
  },
  {
    id: 5, severity: 'info', time: '14:20:45',
    title: 'PPE compliance check passed',
    detail: 'All workers compliant',
    location: 'Level 3 – West Wing'
  },
]

export default function LiveAlerts() {
  const [alerts, setAlerts] = useState(ALERTS_DATA)
  const [flashId, setFlashId] = useState(null)

  useEffect(() => {
    // Simulate new alerts arriving
    const interval = setInterval(() => {
      setFlashId(1)
      setTimeout(() => setFlashId(null), 1500)
    }, 8000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="card alerts-card">
      <div className="card-header">
        <span className="card-title">Live Safety Alerts</span>
        <button className="view-all-btn">
          View All <ChevronRight size={12} />
        </button>
      </div>

      <div className="alerts-list">
        {alerts.map((alert, i) => (
          <div
            key={alert.id}
            className={`alert-item alert-${alert.severity} ${flashId === alert.id ? 'flash' : ''}`}
            style={{ animationDelay: `${i * 0.08}s` }}
          >
            <div className="alert-severity-bar" />
            <div className="alert-content">
              <div className="alert-top">
                <span className={`badge badge-${alert.severity}`}>
                  {alert.severity}
                </span>
                <span className="alert-time">{alert.time}</span>
              </div>
              <div className="alert-title">{alert.title}</div>
              {alert.detail && <div className="alert-detail">{alert.detail}</div>}
              <div className="alert-location">
                <MapPin size={10} />
                {alert.location}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
