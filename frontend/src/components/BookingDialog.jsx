import { useEffect, useState } from 'react'
import { api } from '../api/client.js'
import { fmtTime } from '../utils/time.js'
import Modal from './Modal.jsx'
import PatientForm from './PatientForm.jsx'

export default function BookingDialog({ doctor, slot, onClose, onBooked }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [patientId, setPatientId] = useState(null)
  const [creating, setCreating] = useState(false)
  const [reason, setReason] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const id = setTimeout(() => {
      api.patients.search(q).then(setResults).catch(() => setResults([]))
    }, 200)
    return () => clearTimeout(id)
  }, [q])

  const book = async (pid) => {
    setSaving(true)
    setError(null)
    try {
      await api.appointments.book({
        patient_id: pid,
        doctor_id: doctor.id,
        starts_at: slot.starts_at,
        reason,
      })
      onBooked()
    } catch (e) {
      // A 409 means someone else just took the slot: show it inline and refresh the grid.
      setError(
        e.code === 'SLOT_TAKEN'
          ? { message: 'Slot just taken — pick another time.', refresh: true }
          : e,
      )
      if (e.code === 'SLOT_TAKEN') onBooked({ keepOpen: true })
    } finally {
      setSaving(false)
    }
  }

  const createAndBook = async (body) => {
    setError(null)
    try {
      const p = await api.patients.create(body)
      await book(p.id)
    } catch (e) {
      setError(e)
    }
  }

  return (
    <Modal title={`Book ${doctor.full_name} · ${fmtTime(slot.starts_at)}`} onClose={onClose}>
      {error && (
        <div className="banner banner-error" role="alert">
          {error.message}
        </div>
      )}
      <label className="field">
        Reason for visit
        <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={255} />
      </label>

      {creating ? (
        <PatientForm
          submitLabel="Register & book"
          onSubmit={createAndBook}
          onCancel={() => setCreating(false)}
        />
      ) : (
        <>
          <label className="field">
            Find patient (name or phone)
            <input value={q} onChange={(e) => setQ(e.target.value)} autoFocus />
          </label>
          <ul className="picker">
            {results.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  className={`picker-item ${patientId === p.id ? 'picker-on' : ''}`}
                  onClick={() => setPatientId(p.id)}
                >
                  <strong>{p.full_name}</strong>
                  <span className="muted">{p.phone}</span>
                </button>
              </li>
            ))}
            {results.length === 0 && <li className="muted">No matching patients</li>}
          </ul>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={() => setCreating(true)}>
              New patient…
            </button>
            <button
              className="btn btn-primary"
              disabled={!patientId || saving}
              onClick={() => book(patientId)}
            >
              Book appointment
            </button>
          </div>
        </>
      )}
    </Modal>
  )
}
