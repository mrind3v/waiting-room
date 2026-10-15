import { useState } from 'react'
import BookingDialog from '../components/BookingDialog.jsx'
import EmptyState from '../components/EmptyState.jsx'
import ErrorBanner from '../components/ErrorBanner.jsx'
import StatusBadge from '../components/StatusBadge.jsx'
import { api } from '../api/client.js'
import { usePolling } from '../hooks/usePolling.js'
import { fmtTime, todayLocal } from '../utils/time.js'

export default function SchedulePage() {
  const [date, setDate] = useState(todayLocal())
  const [booking, setBooking] = useState(null)

  const { data, error, loading, refresh } = usePolling(
    async () => {
      const doctors = await api.doctors.list(true)
      const [availability, appointments] = await Promise.all([
        Promise.all(doctors.map((d) => api.doctors.availability(d.id, date))),
        api.appointments.list({ date }),
      ])
      return { doctors, availability, appointments }
    },
    20000,
    [date],
  )

  const appointmentAt = (doctorId, slot) =>
    (data?.appointments ?? []).find(
      (a) =>
        a.doctor_id === doctorId &&
        a.status !== 'CANCELLED' &&
        a.starts_at <= slot.starts_at &&
        a.ends_at > slot.starts_at,
    )

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Schedule</h1>
          <p className="muted">Pick a free slot to book an appointment.</p>
        </div>
        <label className="field field-inline">
          Date
          <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
        </label>
      </div>

      <ErrorBanner error={error} onRetry={refresh} />
      {loading && !data && <div className="skeleton tall" />}
      {data && data.doctors.length === 0 && (
        <EmptyState title="No active doctors" hint="Add a doctor on the Doctors page first." />
      )}

      <div className="timelines">
        {data?.doctors.map((doc, i) => (
          <section key={doc.id} className="timeline">
            <h2>
              {doc.full_name}
              <small>
                {doc.specialty}
                {doc.room ? ` · ${doc.room}` : ''}
              </small>
            </h2>
            <ul>
              {data.availability[i].slots.map((slot) => {
                const appt = appointmentAt(doc.id, slot)
                return (
                  <li key={slot.starts_at}>
                    <span className="slot-time">{fmtTime(slot.starts_at)}</span>
                    {slot.available ? (
                      <button className="slot slot-free" onClick={() => setBooking({ doc, slot })}>
                        Free — book
                      </button>
                    ) : appt ? (
                      <span className="slot slot-busy">
                        {appt.patient_name} <StatusBadge status={appt.status} />
                      </span>
                    ) : (
                      <span className="slot slot-past">Unavailable</span>
                    )}
                  </li>
                )
              })}
            </ul>
          </section>
        ))}
      </div>

      {booking && (
        <BookingDialog
          doctor={booking.doc}
          slot={booking.slot}
          onClose={() => setBooking(null)}
          onBooked={(opts) => {
            if (!opts?.keepOpen) setBooking(null)
            refresh()
          }}
        />
      )}
    </>
  )
}
