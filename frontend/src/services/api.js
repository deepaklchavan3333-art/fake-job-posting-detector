async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    credentials: 'include',
    headers: { ...(options.body ? { 'Content-Type': 'application/json' } : {}), ...options.headers },
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`)
  return data
}

export const predictJob = (listing) => request('/api/predict', { method: 'POST', body: JSON.stringify(listing) })
export const analyzeJobUrl = (url) => request('/api/analyze-url', { method: 'POST', body: JSON.stringify({ url }) })
export const getJobs = (query = '') => request(`/api/jobs${query ? `?${query}` : ''}`)
export const getHistory = () => request('/api/history')
export const getHistoryItem = (id) => request(`/api/history/${id}`)
export const getDashboardStats = () => request('/api/dashboard/stats')
export const getSession = () => request('/api/auth/session')
export const login = (credentials) => request('/api/auth/login', { method: 'POST', body: JSON.stringify(credentials) })
export const register = (credentials) => request('/api/auth/register', { method: 'POST', body: JSON.stringify(credentials) })
export const logout = () => request('/api/auth/logout', { method: 'POST' })
