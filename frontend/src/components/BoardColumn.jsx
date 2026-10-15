import AppointmentCard from './AppointmentCard.jsx'

export default function BoardColumn({ title, tone, items, ...cardProps }) {
  return (
    <section className={`column column-${tone}`} aria-label={title}>
      <h2 className="column-head">
        {title} <span className="count">{items.length}</span>
      </h2>
      <div className="column-body">
        {items.length === 0 && <p className="column-empty">Nobody here</p>}
        {items.map((a) => (
          <AppointmentCard key={a.id} appt={a} {...cardProps} />
        ))}
      </div>
    </section>
  )
}
