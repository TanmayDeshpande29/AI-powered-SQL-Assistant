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

// fetch() + Authorization header + one silent token refresh on 401. Returns the raw
// Response, so both JSON calls and event streams can build on it.
async function authFetch(path, { method = "GET", body, auth = true, retry = true, signal } = {}) {
  const headers = {}
  if (body !== undefined) headers["Content-Type"] = "application/json"
  if (auth && tokens.access) headers.Authorization = `Bearer ${tokens.access}`

  let res
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (err) {
    if (err.name === "AbortError") throw err // the caller cancelled on purpose
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
    return authFetch(path, { method, body, auth, retry: false, signal })
  }
  return res
}

async function toApiError(res, auth) {
  if (res.status === 401 && auth) endSession()
  const data = await res.json().catch(() => null)
  const err = data?.error ?? {}
  const message =
    err.code === "validation_error" && err.details?.length
      ? err.details.map((d) => `${d.field}: ${d.message}`).join("\n")
      : err.message ?? `Request failed (${res.status})`
  const apiError = new ApiError(res.status, err.code ?? "http_error", message, err.details)
  // 429 rate limit: how many seconds the server asked us to wait.
  apiError.retryAfter = Number(res.headers.get("Retry-After")) || err.details?.retry_after || null
  return apiError
}

async function request(path, options = {}) {
  const res = await authFetch(path, options)
  if (res.status === 204) return null
  if (!res.ok) throw await toApiError(res, options.auth ?? true)
  return res.json()
}

// --- Server-Sent Events ------------------------------------------------------
// The browser's EventSource can't send a POST body or an Authorization header,
// so we read the text/event-stream response ourselves. Wire format per event:
//   event: token
//   data: {"text": "Lists each"}
//   <blank line>
// Lines starting with ":" are comments (the server's keep-alive pings).

function parseSSEBlock(block) {
  let event = "message"
  const data = []
  for (const line of block.split("\n")) {
    if (line.startsWith(":")) continue
    if (line.startsWith("event:")) event = line.slice(6).trim()
    else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""))
  }
  return data.length ? { event, data: JSON.parse(data.join("\n")) } : null
}

async function streamEvents(path, body, { onEvent, signal }) {
  const res = await authFetch(path, { method: "POST", body, signal })
  if (!res.ok) throw await toApiError(res, true) // auth/validation errors arrive as JSON

  const reader = res.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ""
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value.replaceAll("\r\n", "\n")
    let boundary
    // Network chunks don't line up with events: only a blank line ends an event.
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const event = parseSSEBlock(buffer.slice(0, boundary))
      buffer = buffer.slice(boundary + 2)
      if (event) onEvent(event)
    }
  }
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

  // AI features. reasoningEffort: "low" | "medium" | "high" | null (null = server default)
  generateSql: ({ question, dialect, saveHistory = true, reasoningEffort = null }) =>
    request("/sql/generate", {
      method: "POST",
      body: { question, dialect, save_history: saveHistory, reasoning_effort: reasoningEffort },
    }),
  assistSql: ({ mode, sql, dialect, saveHistory = true, reasoningEffort = null }) =>
    request("/sql/assist", {
      method: "POST",
      body: { mode, sql, dialect, save_history: saveHistory, reasoning_effort: reasoningEffort },
    }),
  // Streams the explanation: onToken(text) runs for every piece as it arrives; the
  // promise resolves with the final result (usage, cost, history_id) or rejects.
  streamExplain: async (
    { sql, dialect, saveHistory = true, reasoningEffort = null },
    { onToken, signal } = {},
  ) => {
    let result = null
    await streamEvents(
      "/sql/explain/stream",
      { sql, dialect, save_history: saveHistory, reasoning_effort: reasoningEffort },
      {
        signal,
        onEvent: ({ event, data }) => {
          if (event === "token") onToken?.(data.text)
          else if (event === "done") result = data
          else if (event === "error") {
            const error = new ApiError(0, data.code, data.message, data.details)
            error.retryAfter = data.details?.retry_after ?? null
            throw error
          }
        },
      },
    )
    if (!result) throw new ApiError(0, "stream_incomplete", "The answer stream ended unexpectedly.")
    return result
  },

  // history
  listHistory: ({ limit = 20, offset = 0 } = {}) => request(`/history?limit=${limit}&offset=${offset}`),
  deleteHistory: (id) => request(`/history/${id}`, { method: "DELETE" }),
}
