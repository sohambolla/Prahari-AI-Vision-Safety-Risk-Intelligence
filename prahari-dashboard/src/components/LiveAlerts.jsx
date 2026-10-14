import { AlertTriangle, ChevronRight, MapPin, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import './LiveAlerts.css'

const API_BASE = (import.meta.env.VITE_VISION_API_URL ||
  `${window.location.protocol}//${window.location.hostname || 'localhost'}:8000`).replace(/\/$/, '')

export default function LiveAlerts({ alerts = [], onRefresh, onAction }) {
  const [showAll, setShowAll] = useState(false)
  const visibleAlerts = showAll ? alerts : alerts.slice(0, 8)
  return (
    <div className="card alerts-card">
      <div className="card-header">
        <span className="card-title">Live Safety Alerts</span>
        <div className="alerts-header-actions">
          <button className="refresh-alerts-btn" onClick={onRefresh} title="Reload recent alerts from the safety server">
            <RefreshCw size={11} /> Refresh
          </button>
          <button className="view-all-btn" onClick={() => {
            if (!showAll) onRefresh?.()
            setShowAll(!showAll)
          }}>
            {showAll ? 'Show Less' : 'View All'} <ChevronRight size={12} />
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
        {visibleAlerts.map((alert, i) => (
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
              {(alert.clip_url || alert.snapshot_url) && (
                <div className="alert-media-links">
                  {alert.clip_url && <a href={alert.clip_url.startsWith('http') ? alert.clip_url : `${API_BASE}${alert.clip_url}`} target="_blank" rel="noreferrer">Replay clip</a>}
                  {alert.snapshot_url && <a href={alert.snapshot_url.startsWith('http') ? alert.snapshot_url : `${API_BASE}${alert.snapshot_url}`} target="_blank" rel="noreferrer">Snapshot</a>}
                </div>
              )}
              {alert.event_id && (
                <div className="alert-actions">
                  {alert.status === 'new' && <button onClick={() => onAction?.(alert, 'acknowledge')}>Acknowledge</button>}
                  {alert.status !== 'false_alarm' && alert.status !== 'escalated' && <button onClick={() => onAction?.(alert, 'escalate')}>Escalate</button>}
                  {alert.status !== 'false_alarm' && <button onClick={() => onAction?.(alert, 'false-alarm')}>False alarm</button>}
                  {alert.status && alert.status !== 'new' && <span className="alert-status">{alert.status.replace('_', ' ')}</span>}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
