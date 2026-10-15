export default function ErrorBanner({ error, onRetry }) {
  if (!error) return null
  return (
    <div className="banner banner-error" role="alert">
      <span>
        {error.status === 0
          ? 'Cannot reach the server. Retrying automatically…'
          : error.message}
      </span>
      {onRetry && (
        <button className="btn btn-ghost" onClick={onRetry}>
          Retry
        </button>
      )}
    </div>
  )
}
