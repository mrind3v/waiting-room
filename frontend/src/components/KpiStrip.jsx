export default function KpiStrip({ stats }) {
  const items = [
    ['Booked', stats?.booked, 'booked'],
    ['Waiting', stats?.checked_in, 'waiting'],
    ['With doctor', stats?.in_consultation, 'consult'],
    ['Done', stats?.done, 'done'],
    ['Avg wait', stats?.avg_wait_minutes == null ? '—' : `${stats.avg_wait_minutes} min`, 'wait'],
  ]
  return (
    <section className="kpis" aria-label="Today at a glance">
      {items.map(([label, value, tone]) => (
        <div key={label} className={`kpi kpi-${tone}`}>
          <span className="kpi-value">{value ?? '–'}</span>
          <span className="kpi-label">{label}</span>
        </div>
      ))}
    </section>
  )
}
