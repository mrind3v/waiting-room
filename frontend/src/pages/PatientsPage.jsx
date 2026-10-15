import { useState } from 'react'
import EmptyState from '../components/EmptyState.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import Modal from '../components/Modal.jsx'
import PatientForm from '../components/PatientForm.jsx'
import { api } from '../api/client.js'
import { usePolling } from '../hooks/usePolling.js'

export default function PatientsPage() {
  const [q, setQ] = useState('')
  const [editing, setEditing] = useState(null) // patient | {} (new) | null
  const [deleting, setDeleting] = useState(null)
  const [formError, setFormError] = useState(null)
  const [notice, setNotice] = useState(null)

  const { data, error, loading, refresh } = usePolling(() => api.patients.search(q), 60000, [q])

  const save = async (body) => {
    setFormError(null)
    try {
      if (editing.id) await api.patients.update(editing.id, body)
      else await api.patients.create(body)
      setEditing(null)
      refresh()
    } catch (e) {
      setFormError(e)
    }
  }

  const remove = async () => {
    try {
      await api.patients.remove(deleting.id)
      setDeleting(null)
      refresh()
    } catch (e) {
      setDeleting(null)
      setNotice(e.code === 'HAS_APPOINTMENTS' ? 'This patient has appointments and cannot be deleted.' : e.message)
    }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Patients</h1>
          <p className="muted">Register, search and update patient records.</p>
        </div>
        <button
          className="btn btn-primary"
          onClick={() => {
            setFormError(null)
            setEditing({})
          }}
        >
          + New patient
        </button>
      </div>

      <input
        className="search"
        placeholder="Search by name or phone…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        aria-label="Search patients"
      />
      <ErrorBanner error={error} onRetry={refresh} />
      {notice && (
        <div className="banner banner-warn" role="status">
          {notice}
          <button className="btn btn-ghost" onClick={() => setNotice(null)}>
            Dismiss
          </button>
        </div>
      )}
      {loading && !data && <div className="skeleton tall" />}
      {data && data.length === 0 && (
        <EmptyState title="No patients found" hint="Try a different search or add a new patient." />
      )}

      {data && data.length > 0 && (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Phone</th>
              <th>Date of birth</th>
              <th>Email</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {data.map((p) => (
              <tr key={p.id}>
                <td data-label="Name">
                  <strong>{p.full_name}</strong>
                </td>
                <td data-label="Phone">{p.phone}</td>
                <td data-label="Date of birth">{p.date_of_birth}</td>
                <td data-label="Email">{p.email ?? '—'}</td>
                <td className="row-actions">
                  <button
                    className="btn btn-ghost"
                    onClick={() => {
                      setFormError(null)
                      setEditing(p)
                    }}
                  >
                    Edit
                  </button>
                  <button className="btn btn-ghost" onClick={() => setDeleting(p)}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {editing && (
        <Modal title={editing.id ? 'Edit patient' : 'New patient'} onClose={() => setEditing(null)}>
          <PatientForm
            initial={editing.id ? editing : undefined}
            onSubmit={save}
            onCancel={() => setEditing(null)}
            error={formError}
          />
        </Modal>
      )}
      {deleting && (
        <Modal title="Delete patient" onClose={() => setDeleting(null)}>
          <p>
            Delete <strong>{deleting.full_name}</strong>? This cannot be undone.
          </p>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={() => setDeleting(null)}>
              Keep
            </button>
            <button className="btn btn-danger" onClick={remove}>
              Delete
            </button>
          </div>
        </Modal>
      )}
    </>
  )
}
