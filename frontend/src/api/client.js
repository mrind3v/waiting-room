export class ApiError extends Error {
  constructor(status, code, detail) {
    super(detail)
    this.status = status
    this.code = code
  }
}

async function request(path, { method = 'GET', body, params } = {}) {
  const qs = params
    ? '?' + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== '' && v != null))
    : ''
  let res
  try {
    res = await fetch(`/api${path}${qs}`, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'NETWORK', 'Cannot reach the server')
  }
  if (res.status === 204) return null
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new ApiError(res.status, data.code ?? 'ERROR', data.detail ?? res.statusText)
  return data
}

export const api = {
  config: () => request('/config'),
  doctors: {
    list: (active) => request('/doctors', { params: { active } }),
    create: (body) => request('/doctors', { method: 'POST', body }),
    update: (id, body) => request(`/doctors/${id}`, { method: 'PUT', body }),
    availability: (id, date) => request(`/doctors/${id}/availability`, { params: { date } }),
  },
  patients: {
    search: (q) => request('/patients', { params: { q } }),
    create: (body) => request('/patients', { method: 'POST', body }),
    update: (id, body) => request(`/patients/${id}`, { method: 'PUT', body }),
    remove: (id) => request(`/patients/${id}`, { method: 'DELETE' }),
  },
  appointments: {
    list: (params) => request('/appointments', { params }),
    book: (body) => request('/appointments', { method: 'POST', body }),
    setStatus: (id, status, cancel_reason) =>
      request(`/appointments/${id}/status`, { method: 'POST', body: { status, cancel_reason } }),
  },
  dashboard: (doctor_id) => request('/dashboard/today', { params: { doctor_id } }),
}
