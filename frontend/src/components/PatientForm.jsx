import { useState } from 'react'

export default function PatientForm({ initial, onSubmit, onCancel, submitLabel = 'Save', error }) {
  const [form, setForm] = useState({
    full_name: initial?.full_name ?? '',
    date_of_birth: initial?.date_of_birth ?? '',
    phone: initial?.phone ?? '',
    email: initial?.email ?? '',
    notes: initial?.notes ?? '',
  })
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const submit = (e) => {
    e.preventDefault()
    onSubmit({ ...form, email: form.email || null })
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
          Date of birth
          <input required type="date" value={form.date_of_birth} onChange={set('date_of_birth')} />
        </label>
        <label className="field">
          Phone
          <input required inputMode="tel" value={form.phone} onChange={set('phone')} />
        </label>
      </div>
      <label className="field">
        Email (optional)
        <input type="email" value={form.email} onChange={set('email')} />
      </label>
      <label className="field">
        Notes
        <textarea rows={2} value={form.notes} onChange={set('notes')} />
      </label>
      <div className="modal-actions">
        {onCancel && (
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            Cancel
          </button>
        )}
        <button className="btn btn-primary">{submitLabel}</button>
      </div>
    </form>
  )
}
