import { Users, HardHat, Truck, Cctv, ShieldCheck, Activity } from 'lucide-react'
import './ResourceMonitoring.css'

export default function ResourceMonitoring() {
  const stats = [
    {
      icon: Users,
      label: 'Active Workers',
      value: '142',
      sub: '138 Compliant • 4 Flagged',
      color: '#3b82f6',
      bg: 'rgba(59, 130, 246, 0.12)'
    },
    {
      icon: ShieldCheck,
      label: 'PPE Compliance',
      value: '94.2%',
      sub: '+2.1% from yesterday',
      color: '#10b981',
      bg: 'rgba(16, 185, 129, 0.12)'
    },
    {
      icon: Truck,
      label: 'Machinery Active',
      value: '6 Units',
      sub: '2 Cranes • 3 Hoists • 1 Excavator',
      color: '#f59e0b',
      bg: 'rgba(245, 158, 11, 0.12)'
    },
    {
      icon: Cctv,
      label: 'Vision Streams',
      value: '12 / 12',
      sub: '0 Drops • Latency 18ms',
      color: '#06b6d4',
      bg: 'rgba(6, 182, 212, 0.12)'
    }
  ]

  return (
    <div className="card resource-card">
      <div className="card-header">
        <span className="card-title">Workforce & Resource Intel</span>
        <span className="resource-status-badge">
          <Activity size={12} className="pulse" /> Real-Time
        </span>
      </div>

      <div className="resource-grid">
        {stats.map((item, idx) => {
          const Icon = item.icon
          return (
            <div key={idx} className="resource-stat-card">
              <div className="resource-stat-header">
                <div className="resource-icon-wrap" style={{ background: item.bg, color: item.color }}>
                  <Icon size={16} />
                </div>
                <span className="resource-stat-label">{item.label}</span>
              </div>
              <div className="resource-stat-value" style={{ color: item.color }}>
                {item.value}
              </div>
              <div className="resource-stat-sub">{item.sub}</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
