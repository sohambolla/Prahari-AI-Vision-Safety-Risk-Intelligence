import { useState } from 'react'
import { AlertOctagon, CheckCircle2, Clock, ShieldAlert, Sparkles, TrendingUp } from 'lucide-react'
import './MVPTimeline.css'

export default function MVPTimeline() {
  const [tab, setTab] = useState('events') // 'events' | 'roadmap'

  const events = [
    { id: 'EV-904', time: '14:27:18', zone: 'East Wing - L6', type: 'Edge Zone Intrusion', conf: '96.8%', status: 'Escalated', level: 'critical' },
    { id: 'EV-903', time: '14:25:10', zone: 'East Wing - L6', type: 'Missing Safety Helmet', conf: '94.2%', status: 'Auto-Alerted', level: 'warning' },
    { id: 'EV-902', time: '14:23:04', zone: 'Crane 01 - L4', type: 'Suspended Load Proximity', conf: '98.1%', status: 'Resolved', level: 'critical' },
    { id: 'EV-901', time: '14:20:45', zone: 'West Wing - L3', type: 'Scaffold Capacity OK', conf: '99.0%', status: 'Cleared', level: 'success' },
  ]

  const roadmap = [
    { phase: 'Sprint 1', title: 'Core RTSP & PPE Vision', desc: 'YOLO11 hardhat, vest, and harness real-time detection', status: 'done' },
    { phase: 'Sprint 2', title: 'Spatial Hazard & Dwell-Time', desc: 'Polygon geofencing and proximity meters with ByteTrack', status: 'active' },
    { phase: 'Sprint 3', title: 'Audio Alarms & Edge NVR', desc: 'On-site smart sirens, Telegram / WhatsApp supervisor alerts', status: 'next' },
    { phase: 'Sprint 4', title: 'Multi-Site Enterprise Cloud', desc: 'Cross-site risk intelligence, PDF report generator & analytics', status: 'next' },
  ]

  return (
    <div className="card mvp-card">
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span className="card-title">
            {tab === 'events' ? 'Live Risk Audit & Incident Log' : 'PRAHARI MVP & Intelligence Roadmap'}
          </span>
        </div>
        <div className="tab-switcher">
          <button
            className={`tab-btn ${tab === 'events' ? 'active' : ''}`}
            onClick={() => setTab('events')}
          >
            Live Events
          </button>
          <button
            className={`tab-btn ${tab === 'roadmap' ? 'active' : ''}`}
            onClick={() => setTab('roadmap')}
          >
            MVP Milestones
          </button>
        </div>
      </div>

      <div className="mvp-content">
        {tab === 'events' ? (
          <div className="events-table-wrap">
            <table className="events-table">
              <thead>
                <tr>
                  <th>Event ID</th>
                  <th>Timestamp</th>
                  <th>Zone / Cam</th>
                  <th>Incident Type</th>
                  <th>Confidence</th>
                  <th>Action / Status</th>
                </tr>
              </thead>
              <tbody>
                {events.map(ev => (
                  <tr key={ev.id}>
                    <td className="font-mono text-accent">{ev.id}</td>
                    <td className="font-mono">{ev.time}</td>
                    <td>{ev.zone}</td>
                    <td>
                      <span className={`event-type-tag event-${ev.level}`}>
                        {ev.type}
                      </span>
                    </td>
                    <td className="font-mono">{ev.conf}</td>
                    <td>
                      <span className={`badge badge-${ev.level === 'critical' ? 'critical' : ev.level === 'warning' ? 'warning' : 'success'}`}>
                        {ev.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="roadmap-grid">
            {roadmap.map((item, idx) => (
              <div key={idx} className={`roadmap-step step-${item.status}`}>
                <div className="roadmap-phase">
                  {item.phase}
                  {item.status === 'done' && <CheckCircle2 size={13} className="text-success" />}
                  {item.status === 'active' && <Clock size={13} className="text-warning pulse" />}
                </div>
                <div className="roadmap-title">{item.title}</div>
                <div className="roadmap-desc">{item.desc}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
