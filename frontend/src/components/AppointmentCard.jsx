import { fmtTime, minutesSince } from '../utils/time.js'

const ACTION = {
  BOOKED: ['Check in', 'CHECKED_IN'],
  CHECKED_IN: ['Call in', 'IN_CONSULTATION'],
  IN_CONSULTATION: ['Complete', 'DONE'],
}

export default function AppointmentCard({ appt, now, busy, onAdvance, onCancel }) {
  const action = ACTION[appt.status]
  const canCancel = appt.status === 'BOOKED' || appt.status === 'CHECKED_IN'
  return (
    <article className={`card card-${appt.status.toLowerCase()}`}>
      <div className="card-top">
        <span className="card-time">{fmtTime(appt.starts_at)}</span>
        {appt.status === 'CHECKED_IN' && (
          <span className="wait-chip">waiting {minutesSince(appt.checked_in_at, now)} min</span>
        )}
        {appt.status === 'IN_CONSULTATION' && (
          <span className="wait-chip wait-chip-consult">
            in room {minutesSince(appt.consultation_started_at, now)} min
          </span>
        )}
      </div>
      <strong className="card-patient">{appt.patient_name}</strong>
      <span className="card-doctor">
        {appt.doctor_name}
        {appt.room ? ` · ${appt.room}` : ''}
      </span>
      {appt.reason && <span className="card-reason">{appt.reason}</span>}
      {(action || canCancel) && (
        <div className="card-actions">
          {action && (
            <button
              className="btn btn-primary"
              disabled={busy}
              onClick={() => onAdvance(appt, action[1])}
            >
              {action[0]}
            </button>
          )}
          {canCancel && (
            <button className="btn btn-ghost" disabled={busy} onClick={() => onCancel(appt)}>
              Cancel…
            </button>
          )}
        </div>
      )}
    </article>
  )
}
