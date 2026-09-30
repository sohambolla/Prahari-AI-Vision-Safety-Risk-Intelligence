import { useEffect, useRef } from 'react'
import './RiskHeatmap.css'

// Generate synthetic heatmap data points
function generateHeatData() {
  const points = []
  // Cluster 1: Edge zone (high risk)
  for (let i = 0; i < 30; i++) {
    points.push({
      x: 15 + Math.random() * 25,
      y: 60 + Math.random() * 25,
      intensity: 0.7 + Math.random() * 0.3,
    })
  }
  // Cluster 2: Scaffold area (medium risk)
  for (let i = 0; i < 20; i++) {
    points.push({
      x: 55 + Math.random() * 20,
      y: 15 + Math.random() * 20,
      intensity: 0.4 + Math.random() * 0.3,
    })
  }
  // Cluster 3: Crane zone
  for (let i = 0; i < 12; i++) {
    points.push({
      x: 70 + Math.random() * 15,
      y: 50 + Math.random() * 20,
      intensity: 0.3 + Math.random() * 0.3,
    })
  }
  // Scattered low risk
  for (let i = 0; i < 15; i++) {
    points.push({
      x: 10 + Math.random() * 80,
      y: 10 + Math.random() * 80,
      intensity: 0.1 + Math.random() * 0.2,
    })
  }
  return points
}

export default function RiskHeatmap() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const w = canvas.width = canvas.offsetWidth * 2
    const h = canvas.height = canvas.offsetHeight * 2
    ctx.scale(2, 2)
    const dw = canvas.offsetWidth
    const dh = canvas.offsetHeight

    // Draw dark background
    ctx.fillStyle = '#0d1117'
    ctx.fillRect(0, 0, dw, dh)

    // Draw grid
    ctx.strokeStyle = 'rgba(255,255,255,0.04)'
    ctx.lineWidth = 0.5
    for (let x = 0; x < dw; x += 20) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, dh); ctx.stroke()
    }
    for (let y = 0; y < dh; y += 20) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(dw, y); ctx.stroke()
    }

    // Draw heatmap points
    const points = generateHeatData()
    points.forEach(p => {
      const px = (p.x / 100) * dw
      const py = (p.y / 100) * dh
      const radius = 15 + p.intensity * 20

      const gradient = ctx.createRadialGradient(px, py, 0, px, py, radius)
      if (p.intensity > 0.6) {
        gradient.addColorStop(0, `rgba(239, 68, 68, ${p.intensity * 0.6})`)
        gradient.addColorStop(0.5, `rgba(245, 158, 11, ${p.intensity * 0.3})`)
        gradient.addColorStop(1, 'rgba(245, 158, 11, 0)')
      } else if (p.intensity > 0.3) {
        gradient.addColorStop(0, `rgba(245, 158, 11, ${p.intensity * 0.5})`)
        gradient.addColorStop(0.5, `rgba(234, 179, 8, ${p.intensity * 0.2})`)
        gradient.addColorStop(1, 'rgba(234, 179, 8, 0)')
      } else {
        gradient.addColorStop(0, `rgba(59, 130, 246, ${p.intensity * 0.4})`)
        gradient.addColorStop(1, 'rgba(59, 130, 246, 0)')
      }

      ctx.fillStyle = gradient
      ctx.beginPath()
      ctx.arc(px, py, radius, 0, Math.PI * 2)
      ctx.fill()
    })
  }, [])

  return (
    <div className="card heatmap-card">
      <div className="card-header">
        <span className="card-title">Risk Heatmap (Last 24h)</span>
      </div>
      <div className="heatmap-container">
        <canvas ref={canvasRef} className="heatmap-canvas" />
        <div className="heatmap-legend">
          <div className="heat-legend-item">
            <div className="heat-dot heat-high" />
            <span>High</span>
          </div>
          <div className="heat-legend-item">
            <div className="heat-dot heat-med" />
            <span>Medium</span>
          </div>
          <div className="heat-legend-item">
            <div className="heat-dot heat-low" />
            <span>Low</span>
          </div>
        </div>
      </div>
    </div>
  )
}
