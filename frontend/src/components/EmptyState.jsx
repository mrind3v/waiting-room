export default function EmptyState({ title, hint }) {
  return (
    <div className="empty">
      <strong>{title}</strong>
      {hint && <p>{hint}</p>}
    </div>
  )
}
