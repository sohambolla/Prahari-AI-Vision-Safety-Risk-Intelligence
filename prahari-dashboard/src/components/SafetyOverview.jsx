import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts'
import './SafetyOverview.css'

const data = [
  { name: 'Critical', value: 12, color: '#ef4444' },
  { name: 'Warning', value: 28, color: '#f59e0b' },
  { name: 'Info', value: 47, color: '#3b82f6' },
]

const total = data.reduce((s, d) => s + d.value, 0)

export default function SafetyOverview() {
  return (
    <div className="card safety-overview-card">
      <div className="card-header">
        <span className="card-title">Safety Overview (Today)</span>
      </div>

      <div className="overview-content">
        {/* Donut Chart */}
        <div className="donut-wrapper">
          <ResponsiveContainer width="100%" height={160}>
            <PieChart>
              <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={45}
                outerRadius={65}
                paddingAngle={3}
                dataKey="value"
                stroke="none"
              >
                {data.map((entry, i) => (
                  <Cell key={i} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                contentStyle={{
                  background: '#1a1f35',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: '8px',
                  fontSize: '0.75rem',
                  color: '#f1f5f9'
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="donut-center">
            <span className="donut-total">{total}</span>
            <span className="donut-label">Total Events</span>
          </div>
        </div>

        {/* Legend */}
        <div className="overview-legend">
          {data.map((d, i) => (
            <div key={i} className="legend-item">
              <div className="legend-dot" style={{ background: d.color }} />
              <span className="legend-name">{d.name}</span>
              <span className="legend-value" style={{ color: d.color }}>{d.value}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
