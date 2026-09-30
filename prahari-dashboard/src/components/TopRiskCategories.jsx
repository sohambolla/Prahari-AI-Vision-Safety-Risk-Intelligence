import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from 'recharts'
import './TopRiskCategories.css'

const data = [
  { name: 'Work at Height', count: 32, color: '#ef4444' },
  { name: 'PPE Compliance', count: 18, color: '#f59e0b' },
  { name: 'Scaffold Integrity', count: 14, color: '#f97316' },
  { name: 'People-Vehicle', count: 11, color: '#3b82f6' },
  { name: 'Suspended Load', count: 7, color: '#8b5cf6' },
  { name: 'Access & Egress', count: 5, color: '#06b6d4' },
]

export default function TopRiskCategories() {
  return (
    <div className="card risk-cat-card">
      <div className="card-header">
        <span className="card-title">Top Risk Categories</span>
      </div>

      <div className="risk-bars">
        {data.map((d, i) => (
          <div key={i} className="risk-bar-item">
            <div className="risk-bar-label">
              <span className="risk-bar-name">{d.name}</span>
              <span className="risk-bar-count" style={{ color: d.color }}>{d.count}</span>
            </div>
            <div className="risk-bar-track">
              <div
                className="risk-bar-fill"
                style={{
                  width: `${(d.count / 32) * 100}%`,
                  background: `linear-gradient(90deg, ${d.color}, ${d.color}88)`,
                  animationDelay: `${0.3 + i * 0.1}s`
                }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
