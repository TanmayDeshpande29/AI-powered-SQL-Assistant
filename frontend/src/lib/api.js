// The ONLY module that talks to the backend. Pages import `api` from here instead of
// calling fetch() themselves, so the base URL, auth header, token refresh and error
// handling live in one place.

const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "")

const ACCESS_KEY = "access_token"
const REFRESH_KEY = "refresh_token"

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY)
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY)
  },
  save({ access_token, refresh_token }) {
    localStorage.setItem(ACCESS_KEY, access_token)
    localStorage.setItem(REFRESH_KEY, refresh_token)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

export const isLoggedIn = () => Boolean(tokens.access)

// Mirrors the backend error envelope: {"error": {"code", "message", "details"}}
export class ApiError extends Error {
  constructor(status, code, message, details) {
    super(message)
    this.status = status
    this.code = code
    this.details = details
  }
}

function endSession() {
  tokens.clear()
  window.location.assign("/login")
}

// Several requests can get a 401 at the same moment (e.g. a page loading user + history).
// They all await the same refresh call instead of each sending their own.
let refreshInFlight = null

function refreshTokens() {
  refreshInFlight ??= fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: tokens.refresh }),
  })
    .then(async (res) => {
      if (!res.ok) throw new Error("refresh failed")
      tokens.save(await res.json())
    })
    .finally(() => {
      refreshInFlight = null
    })
  return refreshInFlight
}

async function request(path, { method = "GET", body, auth = true, retry = true } = {}) {
  const headers = {}
  if (body !== undefined) headers["Content-Type"] = "application/json"
  if (auth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`

  let res
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, "network_error", "Cannot reach the server. Is the backend running?")
  }

  // Access token expired -> get a new pair with the refresh token, then retry once.
  if (res.status === 401 && auth && retry && tokens.refresh) {
    try {
      await refreshTokens()
    } catch {
      endSession()
      throw new ApiError(401, "session_expired", "Your session has expired. Please log in again.")
    }
    return request(path, { method, body, auth, retry: false })
  }

  if (res.status === 204) return null
  const data = await res.json().catch(() => null)

  if (!res.ok) {
    if (res.status === 401 && auth) endSession()
    const err = data?.error ?? {}
    const message =
      err.code === "validation_error" && err.details?.length
        ? err.details.map((d) => `${d.field}: ${d.message}`).join("\n")
        : err.message ?? `Request failed (${res.status})`
    throw new ApiError(res.status, err.code ?? "http_error", message, err.details)
  }
  return data
}

export const api = {
  // auth
  signup: ({ name, email, password }) =>
    request("/auth/signup", { method: "POST", body: { name, email, password }, auth: false }),
  login: async (email, password) => {
    const pair = await request("/auth/login", { method: "POST", body: { email, password }, auth: false })
    tokens.save(pair)
    return pair
  },
  logout: endSession,

  // account
  me: () => request("/users/me"),
  updateMe: ({ name }) => request("/users/me", { method: "PATCH", body: { name } }),
  changePassword: (currentPassword, newPassword) =>
    request("/users/me/password", {
      method: "POST",
      body: { current_password: currentPassword, new_password: newPassword },
    }),
  deleteAccount: () => request("/users/me", { method: "DELETE" }),

  // AI features
  generateSql: ({ question, dialect, saveHistory = true }) =>
    request("/sql/generate", { method: "POST", body: { question, dialect, save_history: saveHistory } }),
  assistSql: ({ mode, sql, dialect, saveHistory = true }) =>
    request("/sql/assist", { method: "POST", body: { mode, sql, dialect, save_history: saveHistory } }),

  // history
  listHistory: ({ limit = 20, offset = 0 } = {}) => request(`/history?limit=${limit}&offset=${offset}`),
  deleteHistory: (id) => request(`/history/${id}`, { method: "DELETE" }),
}
