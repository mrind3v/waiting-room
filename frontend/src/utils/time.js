let tz = 'Australia/Sydney'

export const setClinicTz = (z) => {
  tz = z
}

export const fmtTime = (iso) =>
  new Intl.DateTimeFormat('en-AU', {
    timeZone: tz,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(new Date(iso))

// YYYY-MM-DD for "today" in the clinic's timezone.
export const todayLocal = () =>
  new Intl.DateTimeFormat('en-CA', { timeZone: tz }).format(new Date())

export const minutesSince = (iso, now = Date.now()) =>
  Math.max(0, Math.floor((now - new Date(iso).getTime()) / 60000))

export const fmtClock = (d) =>
  new Intl.DateTimeFormat('en-AU', {
    timeZone: tz,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(d)
