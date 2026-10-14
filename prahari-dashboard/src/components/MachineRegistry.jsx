import { useCallback, useEffect, useState } from 'react'
import { Factory, KeyRound, ShieldCheck, Wrench } from 'lucide-react'
import './MachineRegistry.css'

const API_BASE = (import.meta.env.VITE_VISION_API_URL ||
  `${window.location.protocol}//${window.location.hostname || 'localhost'}:8000`).replace(/\/$/, '')

export default function MachineRegistry() {
  const [machines, setMachines] = useState([])
  const [token, setToken] = useState('')
  const [error, setError] = useState('')
  const [saved, setSaved] = useState('')
  const [interlockResult, setInterlockResult] = useState(null)
  const [form, setForm] = useState({
    machine_id: '', camera_id: 'cam-01', detection_labels: 'machine, conveyor, forklift',
    authorized_person_ids: '', qr_value: '',
  })
  const [operatorId, setOperatorId] = useState('')
  const [ppe, setPpe] = useState({ helmet: false, vest: false, gloves: false })

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/api/machines`)
      if (!response.ok) throw new Error('Machine registry is unavailable.')
      const payload = await response.json()
      setMachines(payload.machines || [])
      setError('')
    } catch {
      setError('Connect the PRAHARI vision server to view the machine registry.')
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const adminRequest = async (path, body) => {
    if (!token.trim()) throw new Error('Enter the configured PRAHARI_ADMIN_TOKEN to edit machine settings.')
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token.trim()}` },
      body: JSON.stringify(body),
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({}))
      throw new Error(payload.detail || 'Machine registry update failed.')
    }
    return response.json()
  }

  const saveMachine = async (event) => {
    event.preventDefault()
    setError('')
    setSaved('')
    try {
      await adminRequest(`/api/machines/${encodeURIComponent(form.machine_id)}`, {
        camera_id: form.camera_id,
        detection_labels: form.detection_labels.split(',').map(value => value.trim()).filter(Boolean),
        authorized_person_ids: form.authorized_person_ids.split(',').map(value => value.trim()).filter(Boolean),
        qr_value: form.qr_value || `PRAHARI:MACHINE:${form.machine_id}`,
      })
      setSaved(`Saved ${form.machine_id}.`)
      await refresh()
    } catch (reason) { setError(reason.message) }
  }

  const toggleMaintenance = async (machine) => {
    setError('')
    try {
      await adminRequest(`/api/machines/${encodeURIComponent(machine.machine_id)}/maintenance`, { enabled: !machine.maintenance_mode })
      await refresh()
    } catch (reason) { setError(reason.message) }
  }

  const calibrate = async (machine, event) => {
    event.preventDefault()
    const values = new FormData(event.currentTarget)
    setError('')
    try {
      await adminRequest(`/api/machines/${encodeURIComponent(machine.machine_id)}/calibrate`, {
        camera_id: machine.camera_id,
        x_percent: Number(values.get('x_percent')),
        y_percent: Number(values.get('y_percent')),
      })
      setSaved(`Calibrated ${machine.machine_id}.`)
      await refresh()
    } catch (reason) { setError(reason.message) }
  }

  const checkInterlock = async (event) => {
    event.preventDefault()
    const machineId = event.currentTarget.elements.machine_id.value
    try {
      const response = await fetch(`${API_BASE}/api/machines/${encodeURIComponent(machineId)}/interlock`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ person_id: operatorId, ppe }),
      })
      const result = await response.json()
      setInterlockResult(result)
    } catch { setError('Could not run the local interlock simulation.') }
  }

  return (
    <section className="card machine-registry-card">
      <div className="card-header">
        <span className="card-title"><Factory size={15} /> Machine Registry & PPE Interlock</span>
        <span className="machine-dry-run"><ShieldCheck size={12} /> DRY-RUN ONLY</span>
      </div>
      <p className="machine-registry-note">Machine shifts use QR markers and saved home coordinates. Registry edits require the server’s admin token. Interlock checks never signal a physical relay.</p>

      <label className="machine-token-field">
        <KeyRound size={13} />
        <span>Admin token</span>
        <input type="password" autoComplete="off" value={token} onChange={event => setToken(event.target.value)} placeholder="PRAHARI_ADMIN_TOKEN" />
      </label>

      <form className="machine-edit-form" onSubmit={saveMachine}>
        <input required value={form.machine_id} onChange={event => setForm({ ...form, machine_id: event.target.value })} placeholder="Machine ID (e.g. CNC-01)" />
        <input required value={form.camera_id} onChange={event => setForm({ ...form, camera_id: event.target.value })} placeholder="Camera ID" />
        <input value={form.detection_labels} onChange={event => setForm({ ...form, detection_labels: event.target.value })} placeholder="Detection labels, comma separated" />
        <input value={form.authorized_person_ids} onChange={event => setForm({ ...form, authorized_person_ids: event.target.value })} placeholder="Authorized IDs, comma separated" />
        <input value={form.qr_value} onChange={event => setForm({ ...form, qr_value: event.target.value })} placeholder="QR payload (optional)" />
        <button type="submit">Save machine</button>
      </form>

      {error && <div className="machine-form-message is-error">{error}</div>}
      {saved && <div className="machine-form-message">{saved}</div>}

      <div className="machine-list">
        {machines.length === 0 && <div className="machine-empty">No machines registered. Add a machine ID, camera, detection labels and authorized IDs above.</div>}
        {machines.map(machine => (
          <article className="machine-row" key={machine.machine_id}>
            <div className="machine-row-heading">
              <div><strong>{machine.machine_id}</strong><span>{machine.camera_id} · {machine.detection_labels?.join(', ') || 'no labels'}</span></div>
              <button type="button" className={machine.maintenance_mode ? 'maintenance-active' : ''} onClick={() => toggleMaintenance(machine)}>
                <Wrench size={12} /> {machine.maintenance_mode ? 'Maintenance ON' : 'Maintenance OFF'}
              </button>
            </div>
            <div className="machine-authorized"><b>Authorized IDs:</b> {machine.authorized_person_ids?.join(', ') || 'none'}</div>
            <div className="machine-home">Home: {machine.home_position ? `${machine.home_position.x_percent.toFixed(1)}%, ${machine.home_position.y_percent.toFixed(1)}%` : 'not calibrated'}</div>
            <form className="machine-calibration-form" onSubmit={event => calibrate(machine, event)}>
              <span>Calibrate QR center (%)</span>
              <input name="x_percent" type="number" min="0" max="100" step="0.1" defaultValue={machine.home_position?.x_percent ?? 50} aria-label="Machine home X percent" />
              <input name="y_percent" type="number" min="0" max="100" step="0.1" defaultValue={machine.home_position?.y_percent ?? 50} aria-label="Machine home Y percent" />
              <button type="submit">Save home</button>
            </form>
          </article>
        ))}
      </div>

      <form className="interlock-check-form" onSubmit={checkInterlock}>
        <strong>Simulate machine start</strong>
        <select name="machine_id" required defaultValue="">
          <option value="" disabled>Select machine</option>
          {machines.map(machine => <option key={machine.machine_id} value={machine.machine_id}>{machine.machine_id}</option>)}
        </select>
        <input value={operatorId} onChange={event => setOperatorId(event.target.value)} placeholder="Verified operator ID" />
        <div className="interlock-ppe-options">
          {Object.keys(ppe).map(item => <label key={item}><input type="checkbox" checked={ppe[item]} onChange={event => setPpe({ ...ppe, [item]: event.target.checked })} /> {item}</label>)}
        </div>
        <button type="submit" disabled={!machines.length}>Check only</button>
        {interlockResult && <div className={`interlock-result ${interlockResult.start_allowed ? 'is-allowed' : 'is-blocked'}`}>
          {interlockResult.start_allowed ? 'Would allow start' : 'Would block start'} · no hardware action
          {interlockResult.reasons?.length > 0 && <ul>{interlockResult.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>}
        </div>}
      </form>
    </section>
  )
}
