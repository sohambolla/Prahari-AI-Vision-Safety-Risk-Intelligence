import { useState } from 'react'
import { Camera, Cpu, Layers, Radio, Monitor, Zap, CheckCircle2, ArrowRight } from 'lucide-react'
import './SystemArchitecture.css'

export default function SystemArchitecture() {
  const [activeStep, setActiveStep] = useState(2)

  const steps = [
    {
      id: 0,
      title: 'RTSP Video Ingest',
      desc: '12x 1080p RTSP/CCTV IP Streams',
      metric: '30 FPS / Stream',
      icon: Camera,
      tag: 'Edge Ingest'
    },
    {
      id: 1,
      title: 'Frame Preprocessing',
      desc: 'Supervision & OpenCV Motion Keyframing',
      metric: '180 FPS Throughput',
      icon: Layers,
      tag: 'Pipeline'
    },
    {
      id: 2,
      title: 'YOLO11 & ByteTrack',
      desc: 'Worker Detection, PPE, Pose & Multi-Tracking',
      metric: '14.2ms Inference',
      icon: Cpu,
      tag: 'AI Core'
    },
    {
      id: 3,
      title: 'Spatial Risk Engine',
      desc: 'Polygon Zone Geofencing & Dwell-Time Check',
      metric: '0.8m Fall Threshold',
      icon: Zap,
      tag: 'Risk Logic'
    },
    {
      id: 4,
      title: 'Alert Broker & WS',
      desc: 'Sub-30ms Event Stream to Control Room',
      metric: '< 25ms Broadcast',
      icon: Radio,
      tag: 'Telemetry'
    },
    {
      id: 5,
      title: 'React Vision HUD',
      desc: 'Real-Time Mission Control & Audit Log',
      metric: 'Zero Latency Sync',
      icon: Monitor,
      tag: 'UI Client'
    }
  ]

  return (
    <div className="card arch-card">
      <div className="card-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Zap size={16} className="card-title-accent" />
          <span className="card-title">Real-Time AI Pipeline & Engine Architecture</span>
        </div>
        <div className="arch-live-chip">
          <span className="live-dot pulse" /> 6/6 Nodes Healthy
        </div>
      </div>

      <div className="arch-flow">
        {steps.map((step, idx) => {
          const Icon = step.icon
          const isActive = activeStep === step.id
          return (
            <div
              key={step.id}
              className={`arch-step ${isActive ? 'active' : ''}`}
              onClick={() => setActiveStep(step.id)}
            >
              <div className="arch-step-header">
                <span className="arch-tag">{step.tag}</span>
                <span className="arch-num">0{idx + 1}</span>
              </div>
              <div className="arch-icon-wrap">
                <Icon size={18} />
              </div>
              <div className="arch-step-title">{step.title}</div>
              <div className="arch-step-desc">{step.desc}</div>
              <div className="arch-step-metric">{step.metric}</div>

              {idx < steps.length - 1 && (
                <div className="arch-arrow">
                  <ArrowRight size={14} />
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
