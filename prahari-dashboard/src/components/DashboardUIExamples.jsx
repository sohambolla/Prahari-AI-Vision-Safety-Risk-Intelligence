import { useEffect, useId, useState } from 'react'
import {
  Activity, AlertTriangle, Bell, Camera, Check, ChevronRight,
  Download, LayoutDashboard, MapPin, Maximize2, ShieldCheck,
  Users, X,
} from 'lucide-react'
import './DashboardUIExamples.css'

const concepts = [
  {
    id: 'command',
    number: '01',
    name: 'Command Center',
    description: 'A live command surface for fast decisions, escalations, and camera health.',
    tags: ['Live control', 'Escalations', 'Camera health'],
  },
  {
    id: 'clean',
    number: '02',
    name: 'Clean Operations',
    description: 'A clean site overview with compliance trends, quick filters, and clear summaries.',
    tags: ['Site overview', 'Trend cards', 'Light theme'],
  },
  {
    id: 'site',
    number: '03',
    name: 'Site First',
    description: 'A video-first workbench with a worker detail drawer and direct incident actions.',
    tags: ['Video-first', 'Worker details', 'Fast actions'],
  },
  {
    id: 'wall',
    number: '04',
    name: 'Camera Wall',
    description: 'A scalable camera matrix with live badges, zone state, and a pinned alert queue.',
    tags: ['Camera matrix', 'Live filters', 'Control room'],
  },
  {
    id: 'executive',
    number: '05',
    name: 'Executive Overview',
    description: 'A management view centered on safety score, weekly movement, and exceptions.',
    tags: ['Safety score', 'Weekly trends', 'Management'],
  },
  {
    id: 'field',
    number: '06',
    name: 'Field Response',
    description: 'A field-friendly incident queue with large controls and fast worker follow-up.',
    tags: ['Field teams', 'Quick response', 'Mobile ready'],
  },
  {
    id: 'riskmap',
    number: '07',
    name: 'Live Risk Map',
    description: 'A site plan that pinpoints active PPE events and camera coverage by zone.',
    tags: ['Zone map', 'Risk levels', 'Camera coverage'],
  },
  {
    id: 'timeline',
    number: '08',
    name: 'Incident Timeline',
    description: 'A time-ordered feed for reviewing alerts, camera context, and resolution progress.',
    tags: ['Event stream', 'Review workflow', 'Evidence'],
  },
  {
    id: 'handover',
    number: '09',
    name: 'Shift Handover',
    description: 'A shift summary that turns unresolved safety events into clear handover actions.',
    tags: ['Shift notes', 'Action list', 'Team handoff'],
  },
  {
    id: 'audit',
    number: '10',
    name: 'Compliance Audit',
    description: 'A sortable worker and PPE matrix designed for audits and daily compliance checks.',
    tags: ['PPE matrix', 'Audit trail', 'Compliance'],
  },
  {
    id: 'equipment',
    number: '11',
    name: 'Equipment Watch',
    description: 'A combined view of camera uptime, site vehicles, and safety system readiness.',
    tags: ['Camera uptime', 'Equipment', 'Readiness'],
  },
  {
    id: 'investigation',
    number: '12',
    name: 'Incident Investigation',
    description: 'A focused evidence workspace for validating an event and recording its outcome.',
    tags: ['Evidence review', 'Incident detail', 'Resolution'],
  },
  {
    id: 'roster',
    number: '13',
    name: 'Worker Roster',
    description: 'A people-first live roster with work zones, PPE state, and supervisor follow-up.',
    tags: ['People view', 'Live status', 'Supervisors'],
  },
  {
    id: 'focus',
    number: '14',
    name: 'Alert Focus',
    description: 'A distraction-free response screen that keeps one urgent event and its camera in view.',
    tags: ['Priority alert', 'Single event', 'Fast triage'],
  },
  {
    id: 'portfolio',
    number: '15',
    name: 'Multi-Site Portfolio',
    description: 'A regional overview for comparing site health, active workers, and open incidents.',
    tags: ['Multi-site', 'Portfolio', 'Regional view'],
  },
]

function WorkerScene({ compact = false, state = 'safe' }) {
  const sceneId = useId().replace(/:/g, '')

  return (
    <div className={`ui-scene ${compact ? 'ui-scene-compact' : ''}`}>
      <svg viewBox="0 0 640 360" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
        <defs>
          <linearGradient id={`sceneSky-${sceneId}`} x2="0" y2="1">
            <stop stopColor="#6d9bac" />
            <stop offset="1" stopColor="#c0c9b4" />
          </linearGradient>
          <linearGradient id={`sceneGround-${sceneId}`} x2="0" y2="1">
            <stop stopColor="#97744c" />
            <stop offset="1" stopColor="#4b4235" />
          </linearGradient>
        </defs>
        <rect width="640" height="360" fill={`url(#sceneSky-${sceneId})`} />
        <circle cx="510" cy="72" r="42" fill="#f7d98b" opacity=".7" />
        <path d="M0 194 104 151 180 188 265 142 360 192 470 152 640 190V360H0Z" fill="#53645c" />
        <path d="M0 247 156 217 282 243 418 206 640 242V360H0Z" fill={`url(#sceneGround-${sceneId})`} />
        <path d="M67 226V96h31v130m-63-105h93M418 211V72h14v139m-34-111h82m-20 0v68" fill="none" stroke="#d4c2a0" strokeWidth="8" opacity=".78" />
        <path d="M0 274h640M58 244 271 360m200-130L371 360" stroke="#d8bf91" strokeWidth="4" opacity=".35" />
        <g transform="translate(328 108)">
          <path d="M-20 38q20-19 40 0l16 74h-72Z" fill="#f1a51b" />
          <path d="M-18 49h36l7 56h-50Z" fill="#e9f04b" />
          <path d="M-18 52 0 65l18-13M-17 89h34" fill="none" stroke="#f6fbff" strokeWidth="7" />
          <circle cy="22" r="17" fill="#be8668" />
          <path d="M-20 18q20-26 40 0v7h-40Z" fill="#f2c849" />
          <path d="M-23 112-34 208h22l16-74 10 74h22L22 112Z" fill="#37465a" />
          <path d="m-30 202-4 17h29l3-17m23 0 3 17h29l-5-17" fill="#1d2937" />
        </g>
      </svg>
      <div className={`ui-person-box ui-person-box-${state}`}>
        <span>{state === 'safe' ? 'H ✓  V ✓' : state === 'warning' ? 'H ✓  V ×' : 'H ×  V ×'}</span>
      </div>
      <span className="ui-scene-cam">CAM 07 · NORTH YARD</span>
      <span className="ui-scene-live"><i /> LIVE</span>
      {!compact && <span className="ui-scene-time">00:42:18</span>}
    </div>
  )
}

function MiniStats({ executive = false }) {
  const items = executive
    ? [['SITE HEALTH', '94%', '↑ 4% this week'], ['PEOPLE ON SITE', '28', 'across 6 cameras'], ['OPEN INCIDENTS', '03', '1 high priority']]
    : [['PEOPLE', '28', '↑ 5 active'], ['CAMERAS', '06', '100% online'], ['ALERTS', '03', '1 needs action'], ['PPE OK', '91%', '↑ 3.4% today']]

  return (
    <div className={`ui-mini-stats ${executive ? 'ui-mini-stats-exec' : ''}`}>
      {items.map(([label, value, note], index) => (
        <div className="ui-mini-stat" key={label}>
          <span>{label}</span>
          <strong className={index === 2 && !executive ? 'ui-stat-warn' : ''}>{value}</strong>
          <div className="ui-mini-stat-foot"><small>{note}</small><span className={`ui-sparkline ui-sparkline-${index}`}><i /><i /><i /><i /><i /></span></div>
        </div>
      ))}
    </div>
  )
}

function AlertRows({ compact = false }) {
  return (
    <div className={`ui-alert-rows ${compact ? 'ui-alert-rows-compact' : ''}`}>
      <div className="ui-alert-head"><span>RECENT ALERTS</span><span>View all <ChevronRight size={10} /></span></div>
      <div className="ui-alert-row ui-alert-red"><i /><div><b>Hardhat missing</b><small>CAM 07 · North yard · 2m ago</small></div><span>HIGH</span></div>
      <div className="ui-alert-row ui-alert-yellow"><i /><div><b>Vest not detected</b><small>CAM 03 · Assembly · 6m ago</small></div><span>MED</span></div>
      {!compact && <div className="ui-alert-row ui-alert-green"><i /><div><b>All clear</b><small>CAM 02 · Loading bay · 9m ago</small></div><span>OK</span></div>}
    </div>
  )
}

function AdvancedConceptLayout({ concept }) {
  switch (concept.id) {
    case 'field':
      return (
        <div className="ui-advanced-layout ui-advanced-field">
          <section className="ui-field-incident">
            <div className="ui-advanced-section-head"><span>PRIORITY RESPONSE</span><b className="ui-status-critical">HIGH PRIORITY</b></div>
            <WorkerScene compact state="critical" />
            <div className="ui-field-event"><b>Hardhat missing</b><small>Worker 014 · North Yard · detected 2m ago</small></div>
            <button className="ui-action-primary">Acknowledge incident <ChevronRight size={11} /></button>
          </section>
          <section className="ui-field-queue"><div className="ui-advanced-section-head"><span>RESPONSE QUEUE</span><b>3 OPEN</b></div><AlertRows compact /><div className="ui-field-supervisor"><span className="ui-worker-avatar">JD</span><span><b>Jordan Davis</b><small>Site supervisor · on duty</small></span><i className="ui-dot-green" /></div></section>
        </div>
      )
    case 'riskmap':
      return (
        <div className="ui-advanced-layout ui-advanced-riskmap">
          <section className="ui-risk-map">
            <div className="ui-advanced-section-head"><span>LIVE SITE ZONES</span><b><i className="ui-map-live-dot" /> 6 CAMERAS ACTIVE</b></div>
            <svg viewBox="0 0 600 240" role="img" aria-label="Site map showing three safety zones">
              <rect x="12" y="12" width="576" height="216" rx="10" className="ui-map-ground" />
              <path d="M45 175 155 96l95 65 105-98 187 108" className="ui-map-road" />
              <rect x="51" y="35" width="145" height="72" rx="7" className="ui-map-building" /><rect x="253" y="34" width="126" height="56" rx="7" className="ui-map-building" /><rect x="420" y="123" width="124" height="73" rx="7" className="ui-map-building" />
              <text x="78" y="76">ASSEMBLY</text><text x="280" y="68">STORAGE</text><text x="450" y="163">LOADING</text>
              <circle cx="219" cy="130" r="17" className="ui-map-risk ui-map-risk-red" /><text x="215" y="134">!</text>
              <circle cx="398" cy="105" r="15" className="ui-map-risk ui-map-risk-yellow" /><text x="394" y="109">2</text>
              <circle cx="115" cy="158" r="13" className="ui-map-camera-dot" /><circle cx="331" cy="127" r="13" className="ui-map-camera-dot" /><circle cx="483" cy="99" r="13" className="ui-map-camera-dot" />
              <text x="111" y="162" className="ui-map-cam-label">C</text><text x="327" y="131" className="ui-map-cam-label">C</text><text x="479" y="103" className="ui-map-cam-label">C</text>
            </svg>
            <div className="ui-map-legend"><span><i className="ui-legend-red" />High risk</span><span><i className="ui-legend-yellow" />Needs review</span><span><i className="ui-legend-camera" />Camera</span></div>
          </section>
          <section className="ui-zone-list"><div className="ui-advanced-section-head"><span>ZONE STATUS</span><b>3 ZONES</b></div>
            <div className="ui-zone-row"><i className="ui-zone-red" /><span><b>Assembly</b><small>1 hardhat alert · CAM 02</small></span><strong>HIGH</strong></div>
            <div className="ui-zone-row"><i className="ui-zone-yellow" /><span><b>Storage</b><small>2 people · all PPE clear</small></span><strong className="ui-zone-safe">CLEAR</strong></div>
            <div className="ui-zone-row"><i className="ui-zone-green" /><span><b>Loading bay</b><small>1 vest alert · CAM 06</small></span><strong className="ui-zone-medium">MED</strong></div>
          </section>
        </div>
      )
    case 'timeline':
      return (
        <div className="ui-advanced-layout ui-advanced-timeline">
          <section className="ui-timeline-list"><div className="ui-advanced-section-head"><span>EVENT STREAM</span><b>Today · 12 events</b></div>
            <div className="ui-timeline-event ui-timeline-active"><time>10:42</time><i /><span><b>Hardhat missing</b><small>North Yard · CAM 07 · Worker 014</small></span><em>OPEN</em></div>
            <div className="ui-timeline-event"><time>10:36</time><i /><span><b>Safety vest restored</b><small>Assembly · CAM 03 · Worker 009</small></span><em className="ui-event-resolved">DONE</em></div>
            <div className="ui-timeline-event"><time>10:18</time><i /><span><b>Camera connection restored</b><small>Loading bay · CAM 06</small></span><em className="ui-event-resolved">DONE</em></div>
          </section>
          <section className="ui-timeline-detail"><div className="ui-advanced-section-head"><span>SELECTED EVENT</span><b>EVT-0248</b></div><WorkerScene compact state="critical" /><div className="ui-timeline-meta"><b>Hardhat missing</b><small>First detected 10:40:12 · still active</small><button>Review event <ChevronRight size={10} /></button></div></section>
        </div>
      )
    case 'handover':
      return (
        <div className="ui-advanced-layout ui-advanced-handover">
          <section className="ui-handover-summary"><div className="ui-advanced-section-head"><span>SHIFT HANDOVER</span><b>SHIFT A → B</b></div><div className="ui-shift-transfer"><span className="ui-shift-avatar">A</span><ChevronRight size={14} /><span className="ui-shift-avatar ui-shift-avatar-next">B</span><div><b>Day shift to evening shift</b><small>Handover at 14:00 · North Yard</small></div></div><div className="ui-handover-metrics"><span><b>03</b><small>Open incidents</small></span><span><b>06</b><small>Cameras online</small></span><span><b>01</b><small>Needs follow-up</small></span></div></section>
          <section className="ui-handover-checks"><div className="ui-advanced-section-head"><span>HANDOVER CHECKLIST</span><b>2 / 3 COMPLETE</b></div><div className="ui-check-row"><i className="ui-check-done">✓</i><span><b>Review active alerts</b><small>3 incidents checked</small></span></div><div className="ui-check-row"><i className="ui-check-done">✓</i><span><b>Confirm camera status</b><small>All 6 streams available</small></span></div><div className="ui-check-row"><i className="ui-check-pending">•</i><span><b>Assign hardhat follow-up</b><small>Worker 014 · Assembly zone</small></span></div></section>
        </div>
      )
    case 'audit':
      return (
        <section className="ui-advanced-layout ui-advanced-audit"><div className="ui-advanced-section-head"><span>WORKER PPE COMPLIANCE</span><b>SHIFT A · 28 WORKERS</b></div>
          <div className="ui-audit-table"><div className="ui-audit-row ui-audit-header"><span>WORKER</span><span>ZONE</span><span>HARDHAT</span><span>VEST</span><span>STATUS</span></div>
            <div className="ui-audit-row"><b>Jordan Davis</b><span>North Yard</span><strong className="ui-cell-good">✓ Present</strong><strong className="ui-cell-good">✓ Present</strong><em className="ui-audit-good">COMPLIANT</em></div>
            <div className="ui-audit-row ui-audit-row-flag"><b>Worker 014</b><span>Assembly</span><strong className="ui-cell-bad">× Missing</strong><strong className="ui-cell-good">✓ Present</strong><em className="ui-audit-bad">REVIEW</em></div>
            <div className="ui-audit-row"><b>Worker 009</b><span>Loading</span><strong className="ui-cell-good">✓ Present</strong><strong className="ui-cell-good">✓ Present</strong><em className="ui-audit-good">COMPLIANT</em></div>
          </div><div className="ui-audit-footer"><span>93% compliant this shift</span><span>Last scan 10:42:18</span></div>
        </section>
      )
    case 'equipment':
      return (
        <div className="ui-advanced-layout ui-advanced-equipment"><section className="ui-equipment-grid"><div className="ui-advanced-section-head"><span>SITE READINESS</span><b>6 / 7 SYSTEMS ONLINE</b></div>
          <div className="ui-equipment-cards"><div className="ui-equipment-card"><span className="ui-equipment-symbol">CAM</span><span><b>Camera 07</b><small>North yard · live</small></span><em className="ui-equipment-live">ONLINE</em></div><div className="ui-equipment-card"><span className="ui-equipment-symbol">CAM</span><span><b>Camera 03</b><small>Assembly · live</small></span><em className="ui-equipment-live">ONLINE</em></div><div className="ui-equipment-card ui-equipment-alert"><span className="ui-equipment-symbol">TRK</span><span><b>Haul truck 02</b><small>Loading bay · idle</small></span><em className="ui-equipment-idle">IDLE</em></div><div className="ui-equipment-card"><span className="ui-equipment-symbol">NET</span><span><b>Vision gateway</b><small>Processing · 24 fps</small></span><em className="ui-equipment-live">HEALTHY</em></div></div>
        </section><section className="ui-equipment-health"><div className="ui-advanced-section-head"><span>UPTIME</span><b>LAST 24H</b></div><strong>99.2%</strong><div className="ui-uptime-bars">{Array.from({ length: 18 }, (_, i) => <i key={i} className={i === 12 ? 'ui-uptime-gap' : ''} />)}</div><small>1 short camera interruption · 10:18</small></section></div>
      )
    case 'investigation':
      return (
        <div className="ui-advanced-layout ui-advanced-investigation"><section className="ui-investigation-evidence"><div className="ui-advanced-section-head"><span>CAMERA EVIDENCE</span><b>CAM 07 · 10:42:18</b></div><WorkerScene state="critical" /><div className="ui-evidence-controls"><button>◀ 10s</button><span>10:42:08 <i /> 10:42:18 <i /> 10:42:28</span><button>10s ▶</button></div></section><section className="ui-investigation-record"><div className="ui-advanced-section-head"><span>INCIDENT RECORD</span><b className="ui-status-critical">OPEN</b></div><h4>Hardhat missing</h4><p>Worker 014 entered the assembly zone without a hardhat.</p><div className="ui-record-row"><span>Detected</span><b>Today, 10:42 AM</b></div><div className="ui-record-row"><span>Location</span><b>North Yard · CAM 07</b></div><div className="ui-record-row"><span>Confidence</span><b>96.4%</b></div><button className="ui-action-primary">Assign for review <ChevronRight size={11} /></button></section></div>
      )
    case 'roster':
      return (
        <section className="ui-advanced-layout ui-advanced-roster"><div className="ui-advanced-section-head"><span>PEOPLE CURRENTLY ON SITE</span><b>28 WORKERS · 6 CAMERAS</b></div>
          <div className="ui-roster-table"><div className="ui-roster-row ui-roster-header"><span>WORKER</span><span>WORK AREA</span><span>LAST SEEN</span><span>PPE STATUS</span></div>
            <div className="ui-roster-row"><b><i className="ui-roster-avatar">JD</i> Jordan Davis</b><span>North Yard</span><span>Now · CAM 07</span><em className="ui-roster-safe">H ✓ &nbsp; V ✓</em></div>
            <div className="ui-roster-row ui-roster-warning"><b><i className="ui-roster-avatar">14</i> Worker 014</b><span>Assembly</span><span>2m ago · CAM 02</span><em className="ui-roster-alert">H × &nbsp; V ✓</em></div>
            <div className="ui-roster-row"><b><i className="ui-roster-avatar">09</i> Worker 009</b><span>Loading Bay</span><span>6m ago · CAM 06</span><em className="ui-roster-safe">H ✓ &nbsp; V ✓</em></div>
          </div><div className="ui-roster-bottom"><span>Showing 3 of 28 workers</span><button>View all workers <ChevronRight size={10} /></button></div>
        </section>
      )
    case 'focus':
      return (
        <div className="ui-advanced-layout ui-advanced-focus"><section className="ui-focus-camera"><WorkerScene state="critical" /><div className="ui-focus-camera-caption"><span>CAM 07 · NORTH YARD</span><b><i /> LIVE DETECTION</b></div></section><section className="ui-focus-action"><span className="ui-focus-kicker"><i /> URGENT · OPEN 2 MIN</span><h4>Hardhat missing</h4><p>Worker detected in Assembly without required head protection.</p><div className="ui-focus-worker"><span className="ui-worker-avatar">14</span><span><b>Worker 014</b><small>Assembly · last seen now</small></span></div><div className="ui-focus-ppe"><span><i className="ui-ppe-missing">×</i> Hardhat missing</span><span><i className="ui-ppe-present">✓</i> Vest present</span></div><button className="ui-action-primary">Acknowledge and assign <ChevronRight size={11} /></button><small className="ui-focus-next">Next alert: Vest not detected · CAM 03</small></section></div>
      )
    case 'portfolio':
      return (
        <section className="ui-advanced-layout ui-advanced-portfolio"><div className="ui-advanced-section-head"><span>REGIONAL SITE HEALTH</span><b>3 SITES · 82 PEOPLE</b></div><div className="ui-portfolio-grid">
          <div className="ui-portfolio-site ui-portfolio-site-active"><div><b>North Yard</b><em>LIVE</em></div><span className="ui-portfolio-score">92<small>/100</small></span><div className="ui-portfolio-meta"><span>28 people</span><span>2 open alerts</span></div><div className="ui-portfolio-track"><i style={{ width: '92%' }} /></div><small>6 / 6 cameras online</small></div>
          <div className="ui-portfolio-site"><div><b>Riverside Build</b><em>LIVE</em></div><span className="ui-portfolio-score">97<small>/100</small></span><div className="ui-portfolio-meta"><span>34 people</span><span>0 open alerts</span></div><div className="ui-portfolio-track"><i style={{ width: '97%' }} /></div><small>8 / 8 cameras online</small></div>
          <div className="ui-portfolio-site"><div><b>West Annex</b><em className="ui-portfolio-maintenance">CHECK</em></div><span className="ui-portfolio-score">84<small>/100</small></span><div className="ui-portfolio-meta"><span>20 people</span><span>4 open alerts</span></div><div className="ui-portfolio-track"><i style={{ width: '84%' }} /></div><small>5 / 6 cameras online</small></div>
        </div></section>
      )
    default:
      return null
  }
}

function DashboardMockup({ concept, enlarged = false }) {
  const showSidebar = !['clean', 'executive', 'field', 'portfolio', 'focus'].includes(concept.id)
  const state = ['site', 'riskmap', 'timeline', 'audit', 'roster'].includes(concept.id) ? 'warning' : 'safe'

  return (
    <div className={`ui-mock ui-mock-${concept.id} ${enlarged ? 'ui-mock-large' : ''}`}>
      <header className="ui-mock-topbar">
        <div className="ui-mock-brand"><span className="ui-mock-brand-icon"><ShieldCheck size={13} /></span><b>PRAHARI</b><small>SAFETY INTELLIGENCE</small></div>
        <nav><span className="ui-nav-active">Overview</span><span>Cameras</span><span>Incidents</span></nav>
        <div className="ui-mock-top-actions"><span className="ui-online"><i /> SYSTEM LIVE</span><Bell size={13} /><span className="ui-avatar">S</span></div>
      </header>

      <div className="ui-mock-workspace">
        {showSidebar && (
          <aside className="ui-mock-sidebar">
            <span className="ui-side-active"><LayoutDashboard size={13} /></span>
            <span><Camera size={13} /></span>
            <span><AlertTriangle size={13} /></span>
            <span><Users size={13} /></span>
            <span><Activity size={13} /></span>
          </aside>
        )}

        <main className="ui-mock-main">
          <div className="ui-mock-title-row">
            <div><small>WEDNESDAY, OCTOBER 22</small><h3>{concept.id === 'executive' ? 'Site overview' : 'North Yard Site'}</h3></div>
            <div className="ui-mock-controls">
              <span className="ui-site-select"><MapPin size={11} /> North Yard <ChevronRight size={10} /></span>
              <span className="ui-filter-chip">Last 24 hours</span>
              <button className="ui-export-button"><Download size={9} /> Export</button>
            </div>
          </div>

          <MiniStats executive={concept.id === 'executive'} />

          {concept.id === 'wall' ? (
            <div className="ui-wall-layout">
              <div className="ui-camera-wall">
                <WorkerScene compact state="critical" />
                <WorkerScene compact state="safe" />
                <WorkerScene compact state="warning" />
                <div className="ui-wall-empty"><Camera size={17} /><b>CAM 04</b><span>Connecting…</span></div>
              </div>
              <AlertRows compact />
            </div>
          ) : concept.id === 'executive' ? (
            <div className="ui-exec-layout">
              <div className="ui-exec-health"><span>WEEKLY SAFETY SCORE</span><strong>94<span>/100</span></strong><div className="ui-health-track"><i /></div><small>↑ 4 points since last week</small></div>
              <div className="ui-exec-camera"><WorkerScene compact state="safe" /><small><b>Live snapshot</b><span>6 cameras online</span></small></div>
              <div className="ui-exec-trend"><span>INCIDENT TREND</span><div className="ui-chart-bars"><i /><i /><i /><i /><i /><i /><i /></div><small>Mon Tue Wed Thu Fri Sat Sun</small></div>
            </div>
          ) : Number(concept.number) >= 6 ? (
            <AdvancedConceptLayout concept={concept} />
          ) : (
            <div className={`ui-standard-layout ui-standard-${concept.id}`}>
              <section className="ui-camera-panel">
                <WorkerScene state={state} />
                <div className="ui-camera-foot"><span><b>CAM 07</b> · LIVE PPE SCAN</span><span>HARDHAT <b>{state === 'critical' ? '×' : '✓'}</b> &nbsp; VEST <b>{state === 'safe' ? '✓' : '×'}</b></span></div>
              </section>
              {concept.id === 'site' ? (
                <aside className="ui-ppe-panel">
                  <div className="ui-ppe-head"><span>WORKER STATUS</span><b>01 PERSON</b></div>
                  <div className="ui-worker-card"><span className="ui-worker-avatar">JD</span><div><b>Worker 014</b><small>CAM 07 · 00:42</small></div><i className="ui-dot-green" /></div>
                  <div className="ui-ppe-check"><span>Hardhat</span><b className="check-ok">DETECTED</b></div>
                  <div className="ui-ppe-check"><span>Safety vest</span><b className="check-warn">MISSING</b></div>
                  <div className="ui-ppe-callout"><AlertTriangle size={13} /><span>Worker needs a safety vest</span></div>
                  <button>Open camera view <ChevronRight size={11} /></button>
                </aside>
              ) : (
                <AlertRows compact={concept.id === 'command'} />
              )}
            </div>
          )}

          {concept.id === 'site' && <div className="ui-site-footer"><span>SHIFT A · 06:00–14:00</span><span>3 INCIDENTS TODAY</span><span>LAST SYNC 10:42:18</span></div>}
        </main>
      </div>
    </div>
  )
}

export default function DashboardUIExamples() {
  const [selected, setSelected] = useState(null)
  const [expanded, setExpanded] = useState(null)
  const [filter, setFilter] = useState('new')
  const expandedConcept = concepts.find(item => item.id === expanded)
  const visibleConcepts = concepts.filter(concept => {
    if (filter === 'new') return Number(concept.number) >= 6
    if (filter === 'original') return Number(concept.number) < 6
    return true
  })

  useEffect(() => {
    if (!expanded) return undefined
    const handleKeyDown = event => {
      if (event.key === 'Escape') setExpanded(null)
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [expanded])

  return (
    <main className="ui-gallery-page">
      <header className="ui-gallery-header">
        <a href="/" className="ui-gallery-brand"><span><ShieldCheck size={19} /></span><b>PRAHARI</b><small>DESIGN OPTIONS</small></a>
        <div className="ui-gallery-header-right"><span>Dashboard redesign</span><a href="/">Return to live dashboard <ChevronRight size={14} /></a></div>
      </header>

      <section className="ui-gallery-intro">
        <div>
          <span className="ui-gallery-eyebrow">10 NEW DASHBOARD DIRECTIONS</span>
          <h1>Explore ten more ways to run site safety.</h1>
          <p>These concepts add focused workflows for field response, risk mapping, audits, investigations, and multi-site oversight. Preview any option full size and choose a favorite.</p>
        </div>
        <div className="ui-gallery-note"><span>PREVIEW ONLY</span><p>These are visual concepts. The live dashboard stays as it is until you choose one.</p></div>
      </section>

      {selected && <div className="ui-selection-banner"><Check size={16} /><span><b>Option {concepts.find(item => item.id === selected)?.number} selected.</b> Tell me its name and I’ll apply that direction to the live dashboard.</span></div>}

      <nav className="ui-gallery-filters" aria-label="Filter dashboard concepts">
        <span>SHOW</span>
        {[['new', 'New 10'], ['all', 'All 15'], ['original', 'Original 5']].map(([value, label]) => (
          <button key={value} className={filter === value ? 'ui-gallery-filter-active' : ''} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>
        ))}
        <small>{visibleConcepts.length} concepts</small>
      </nav>

      <section className="ui-concept-grid" aria-label="Dashboard design options">
        {visibleConcepts.map(concept => (
          <article className={`ui-concept-card ${selected === concept.id ? 'ui-concept-selected' : ''}`} key={concept.id}>
            <div className="ui-concept-info">
              <div className="ui-concept-title"><span>{concept.number}</span><div><h2>{concept.name}</h2><p>{concept.description}</p></div></div>
              <div className="ui-concept-actions">
                <button className="ui-concept-expand" onClick={() => setExpanded(concept.id)} aria-label={`Expand ${concept.name} preview`}><Maximize2 size={13} /> Preview</button>
                <button className="ui-concept-pick" onClick={() => setSelected(concept.id)} aria-pressed={selected === concept.id}>
                  {selected === concept.id ? <><Check size={13} /> Selected</> : <>Choose <ChevronRight size={13} /> </>}
                </button>
              </div>
            </div>
            <DashboardMockup concept={concept} />
            <div className="ui-concept-tags">{concept.tags.map(tag => <span key={tag}>{tag}</span>)}</div>
          </article>
        ))}
      </section>
      {expandedConcept && (
        <div className="ui-preview-backdrop" onClick={() => setExpanded(null)}>
          <section className={`ui-preview-dialog ui-preview-dialog-${expandedConcept.id}`} role="dialog" aria-modal="true" aria-labelledby="ui-preview-title" onClick={event => event.stopPropagation()}>
            <header className="ui-preview-dialog-header">
              <div><span>FULL-SIZE DESIGN PREVIEW · OPTION {expandedConcept.number}</span><h2 id="ui-preview-title">{expandedConcept.name}</h2></div>
              <div>
                <button className="ui-preview-choose" onClick={() => { setSelected(expandedConcept.id); setExpanded(null) }}><Check size={14} /> Choose this design</button>
                <button className="ui-preview-close" onClick={() => setExpanded(null)} aria-label="Close preview"><X size={17} /></button>
              </div>
            </header>
            <div className="ui-preview-stage"><DashboardMockup concept={expandedConcept} enlarged /></div>
            <footer className="ui-preview-dialog-footer"><p>{expandedConcept.description}</p><div>{expandedConcept.tags.map(tag => <span key={tag}>{tag}</span>)}</div></footer>
          </section>
        </div>
      )}
      <footer className="ui-gallery-footer">PRAHARI · LIVE PERSON + PPE MONITORING · CONCEPT PREVIEWS</footer>
    </main>
  )
}
