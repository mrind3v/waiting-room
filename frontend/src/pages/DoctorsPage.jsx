import { useState } from 'react'
import DoctorForm from '../components/DoctorForm.jsx'
import EmptyState from '../components/EmptyState.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import Modal from '../components/Modal.jsx'
import { api } from '../api/client.js'
import { usePolling } from '../hooks/usePolling.js'

export default function DoctorsPage() {
  const [editing, setEditing] = useState(null)
  const [formError, setFormError] = useState(null)
  const { data, error, loading, refresh } = usePolling(() => api.doctors.list(), 60000)

  const save = async (body) => {
    setFormError(null)
    try {
      if (editing.id) await api.doctors.update(editing.id, { ...body, is_active: editing.is_active })
      else await api.doctors.create(body)
      setEditing(null)
      refresh()
    } catch (e) {
      setFormError(e)
    }
  }

  const toggle = async (d) => {
    try {
      await api.doctors.update(d.id, { ...d, is_active: !d.is_active })
    } finally {
      refresh()
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Doctors</h1>
          <p className="muted">Working hours and slot length drive the schedule.</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => {
            setFormError(null)
            setEditing({})
          }}
        >
          + New doctor
        </button>
      </div>
      <ErrorBanner error={error} onRetry={refresh} />
      {loading && !data && <div className="skeleton tall" />}
      {data && data.length === 0 && <EmptyState title="No doctors yet" hint="Add the first doctor." />}
      <div className="doctor-grid">
        {data?.map((d) => (
          <article key={d.id} className={`doctor-card ${d.is_active ? '' : 'doctor-off'}`}>
            <h2>{d.full_name}</h2>
            <p className="muted">
              {d.specialty}
              {d.room ? ` · ${d.room}` : ''}
            </p>
            <p>
              {d.work_start.slice(0, 5)}–{d.work_end.slice(0, 5)} · {d.slot_minutes} min slots
            </p>
            <div className="card-actions">
              <button
                className="btn btn-ghost"
                onClick={() => {
                  setFormError(null)
                  setEditing(d)
                }}
              >
                Edit
              </button>
              <button className="btn btn-ghost" onClick={() => toggle(d)}>
                {d.is_active ? 'Set inactive' : 'Set active'}
              </button>
            </div>
          </article>
        ))}
      </div>
      {editing && (
        <Modal title={editing.id ? 'Edit doctor' : 'New doctor'} onClose={() => setEditing(null)}>
          <DoctorForm
            initial={editing.id ? editing : undefined}
            onSubmit={save}
            onCancel={() => setEditing(null)}
            error={formError}
          />
        </Modal>
      )}
    </>
  )
}
