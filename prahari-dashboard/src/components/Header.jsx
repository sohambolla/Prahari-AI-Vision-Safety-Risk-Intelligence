import {
  Shield, Camera, AlertTriangle, Activity, Users, HardHat,
  Truck, Gauge, Eye, Clock, Radio, Zap, MapPin, Box,
  ChevronRight, Play, Pause, SkipForward, SkipBack, Volume2,
  TrendingUp, BarChart3, Layers, Cpu, Bell, Settings, Search,
  RefreshCw, Maximize2, ArrowUpRight, CircleDot, Construction,
  Cctv, MonitorPlay, LayoutDashboard
} from 'lucide-react'
import './Header.css'

export default function Header({ time, date }) {
  return (
    <header className="prahari-header">
      {/* Logo Section */}
      <div className="header-logo">
        <div className="logo-icon">
          <Shield size={28} strokeWidth={2.5} />
        </div>
        <div className="logo-text">
          <h1>PRAHARI</h1>
          <span className="logo-subtitle">AI Vision Safety & Risk Intelligence</span>
        </div>
      </div>

      {/* Tagline */}
      <div className="header-tagline">
        <span>See Risks Early.</span>
        <span>Keep People Safe.</span>
        <span>Build Smarter.</span>
      </div>

      {/* Feature Badges */}
      <div className="header-features">
        <div className="feature-badge">
          <Camera size={14} />
          <span>Multi-Camera Vision AI</span>
          <span className="feature-sub">On-prem | Offline</span>
        </div>
        <div className="feature-badge">
          <Eye size={14} />
          <span>Proactive Risk Detection</span>
          <span className="feature-sub">Not just compliance</span>
        </div>
        <div className="feature-badge">
          <Users size={14} />
          <span>Safer People. Smarter Ops</span>
          <span className="feature-sub">Safety + Resource Intel</span>
        </div>
      </div>

      {/* Right side: Time + Controls */}
      <div className="header-right">
        <div className="header-actions">
          <a className="header-btn" href="/ui-examples" title="Compare dashboard UI options" aria-label="Compare dashboard UI options">
            <LayoutDashboard size={16} />
          </a>
          <button className="header-btn" title="Search"><Search size={16} /></button>
          <button className="header-btn notification-btn" title="Notifications">
            <Bell size={16} />
            <span className="notif-dot"></span>
          </button>
          <button className="header-btn" title="Settings"><Settings size={16} /></button>
        </div>
        <div className="header-motto">
          <span>PEOPLE</span>
          <span>SITES</span>
          <span>PROGRESS</span>
          <span className="motto-highlight">SAFER TOGETHER</span>
        </div>
      </div>
    </header>
  )
}
