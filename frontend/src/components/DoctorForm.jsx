import { useState } from 'react'

export default function DoctorForm({ initial, onSubmit, onCancel, error }) {
  const [form, setForm] = useState({
    full_name: initial?.full_name ?? '',
    specialty: initial?.specialty ?? '',
    room: initial?.room ?? '',
    slot_minutes: initial?.slot_minutes ?? 15,
    work_start: (initial?.work_start ?? '09:00').slice(0, 5),
    work_end: (initial?.work_end ?? '17:00').slice(0, 5),
    is_active: initial?.is_active ?? true,
  })
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const submit = (e) => {
    e.preventDefault()
    onSubmit({
      ...form,
      room: form.room || null,
      slot_minutes: Number(form.slot_minutes),
    })
  }
  return (
    <form onSubmit={submit} className="form">
      {error && <div className="banner banner-error">{error.message}</div>}
      <label className="field">
        Full name
        <input required value={form.full_name} onChange={set('full_name')} maxLength={120} />
      </label>
      <div className="field-row">
        <label className="field">
          Specialty
          <input required value={form.specialty} onChange={set('specialty')} maxLength={80} />
        </label>
        <label className="field">
          Room
          <input value={form.room} onChange={set('room')} maxLength={20} />
        </label>
      </div>
      <div className="field-row">
        <label className="field">
          Starts
          <input type="time" required value={form.work_start} onChange={set('work_start')} />
        </label>
        <label className="field">
          Ends
          <input type="time" required value={form.work_end} onChange={set('work_end')} />
        </label>
        <label className="field">
          Slot (min)
          <input
            type="number"
            min={5}
            max={120}
            step={5}
            value={form.slot_minutes}
            onChange={set('slot_minutes')}
          />
        </label>
      </div>
      <div className="modal-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          Cancel
        </button>
        <button className="btn btn-primary">Save doctor</button>
      </div>
    </form>
  )
}
