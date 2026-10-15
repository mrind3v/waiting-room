const LABEL = {
  BOOKED: 'Booked',
  CHECKED_IN: 'Waiting',
  IN_CONSULTATION: 'With doctor',
  DONE: 'Done',
  CANCELLED: 'Cancelled',
}

export default function StatusBadge({ status }) {
  return <span className={`badge badge-${status.toLowerCase()}`}>{LABEL[status] ?? status}</span>
}
