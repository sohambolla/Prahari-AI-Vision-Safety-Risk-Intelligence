import { AlertTriangle, ChevronRight, MapPin, RefreshCw } from 'lucide-react'
import './LiveAlerts.css'

export default function LiveAlerts({ alerts = [], onRefresh }) {
  return (
    <div className="card alerts-card">
      <div className="card-header">
        <span className="card-title">Live Safety Alerts</span>
        <div className="alerts-header-actions">
          <button className="refresh-alerts-btn" onClick={onRefresh} title="Clear alert history and load the current live alert">
            <RefreshCw size={11} /> Refresh
          </button>
          <button className="view-all-btn">
            View All <ChevronRight size={12} />
          </button>
        </div>
      </div>

      <div className="alerts-list" aria-live="polite">
        {alerts.length === 0 && (
          <div className="alerts-empty">
            <AlertTriangle size={16} />
            <span>No live safety alerts. Alerts appear here when the camera raises one.</span>
          </div>
        )}
        {alerts.map((alert, i) => (
          <div
            key={alert.id}
            className={`alert-item alert-${alert.severity}`}
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
