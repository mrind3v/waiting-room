import { useState } from 'react'
import BoardColumn from '../components/BoardColumn.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import KpiStrip from '../components/KpiStrip.jsx'
import Modal from '../components/Modal.jsx'
import { api } from '../api/client.js'
import { useNow, usePolling } from '../hooks/usePolling.js'
import { fmtClock } from '../utils/time.js'

const COLUMNS = [
  ['Booked', 'booked', 'BOOKED'],
  ['Waiting', 'waiting', 'CHECKED_IN'],
  ['With doctor', 'consult', 'IN_CONSULTATION'],
  ['Done', 'done', 'DONE'],
]

export default function BoardPage() {
  const [doctorId, setDoctorId] = useState('')
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState(null)
  const [cancelling, setCancelling] = useState(null)
  const [reason, setReason] = useState('')
  const now = useNow()

  const doctors = usePolling(() => api.doctors.list(true), 60000)
  const board = usePolling(
    async () => {
      const params = doctorId ? { doctor_id: doctorId } : {}
      const [appointments, stats] = await Promise.all([
        api.appointments.list(params),
        api.dashboard(doctorId || undefined),
      ])
      return { appointments, stats }
    },
    15000,
    [doctorId],
  )

  const run = async (fn) => {
    setBusy(true)
    setActionError(null)
    try {
      await fn()
      await board.refresh()
    } catch (e) {
      setActionError(e)
      await board.refresh()
    } finally {
      setBusy(false)
    }
  }

  const advance = (appt, status) => run(() => api.appointments.setStatus(appt.id, status))
  const confirmCancel = () =>
    run(async () => {
      await api.appointments.setStatus(cancelling.id, 'CANCELLED', reason || undefined)
      setCancelling(null)
      setReason('')
    })

  const appointments = board.data?.appointments ?? []

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Waiting room</h1>
          <p className="muted">
            Today’s queue
            {board.updatedAt && <> · updated {fmtClock(board.updatedAt)}</>}
          </p>
        </div>
        <div className="chips" role="group" aria-label="Filter by doctor">
          <button
            className={`chip ${doctorId === '' ? 'chip-on' : ''}`}
            onClick={() => setDoctorId('')}
          >
            All doctors
          </button>
          {(doctors.data ?? []).map((d) => (
            <button
              key={d.id}
              className={`chip ${String(d.id) === String(doctorId) ? 'chip-on' : ''}`}
              onClick={() => setDoctorId(String(d.id))}
            >
              {d.full_name}
            </button>
          ))}
        </div>
      </div>

      <ErrorBanner error={board.error} onRetry={board.refresh} />
      <ErrorBanner error={actionError} />
      <KpiStrip stats={board.data?.stats} />

      {board.loading && !board.data ? (
        <div className="skeleton-row">
          {COLUMNS.map(([t]) => (
            <div key={t} className="skeleton" />
          ))}
        </div>
      ) : (
        <div className="board">
          {COLUMNS.map(([title, tone, status]) => (
            <BoardColumn
              key={status}
              title={title}
              tone={tone}
              items={appointments.filter((a) => a.status === status)}
              now={now}
              busy={busy}
              onAdvance={advance}
              onCancel={(a) => setCancelling(a)}
            />
          ))}
        </div>
      )}

      {cancelling && (
        <Modal title="Cancel appointment" onClose={() => setCancelling(null)}>
          <p>
            Cancel <strong>{cancelling.patient_name}</strong>’s appointment with{' '}
            {cancelling.doctor_name}? The slot becomes free again.
          </p>
          <label className="field">
            Reason (optional)
            <input value={reason} onChange={(e) => setReason(e.target.value)} maxLength={255} />
          </label>
          <div className="modal-actions">
            <button className="btn btn-ghost" onClick={() => setCancelling(null)}>
              Keep it
            </button>
            <button className="btn btn-danger" disabled={busy} onClick={confirmCancel}>
              Cancel appointment
            </button>
          </div>
        </Modal>
      )}
    </>
  )
}
