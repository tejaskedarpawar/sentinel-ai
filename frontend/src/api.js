const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export function getAuthToken() {
  return localStorage.getItem("sentinel_token") || null;
}

export function getAuthUser() {
  try {
    const raw = localStorage.getItem("sentinel_user");
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function setAuth(token, user) {
  if (token) {
    localStorage.setItem("sentinel_token", token);
  } else {
    localStorage.removeItem("sentinel_token");
  }
  if (user) {
    localStorage.setItem("sentinel_user", JSON.stringify(user));
  } else {
    localStorage.removeItem("sentinel_user");
  }
}

function authHeaders(extra = {}) {
  const token = getAuthToken();
  const headers = { ...extra };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

async function request(path, options = {}) {
  const headers = authHeaders(options.headers || {});
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401 && !path.includes("/api/auth/login")) {
    setAuth(null, null);
    window.dispatchEvent(new Event("sentinel:auth-invalid"));
  }

  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || errData.reason || `API error ${res.status}: ${path}`);
  }
  return res.json();
}

export const api = {
  // Authentication
  login: async (username, password) => {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      throw new Error(data.detail || "Authentication failed");
    }
    setAuth(data.access_token, data.user);
    return data;
  },

  getMe: async () => {
    return request("/api/auth/me");
  },

  logout: async () => {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: "POST",
        headers: authHeaders(),
      });
    } catch {
      // Ignore network errors on logout
    }
    setAuth(null, null);
  },

  getAuthToken,
  getAuthUser,
  setAuth,

  // Health and System Stats
  health: () => request("/api/health"),
  stats: () => request("/api/stats"),
  employees: () => request("/api/employees"),
  employeeTimeline: (id) => request(`/api/employees/${id}/timeline`),

  // Alerts & Explainability
  alerts: (tier, reviewed) => {
    const params = new URLSearchParams();
    if (tier) params.append("tier", tier);
    if (reviewed !== undefined && reviewed !== null) {
      params.append("reviewed", reviewed);
    }
    const qs = params.toString();
    return request(`/api/alerts${qs ? `?${qs}` : ""}`);
  },
  explainAlert: (employeeId, date) => request(`/api/alerts/${employeeId}/${date}/explain`),

  // Analyst Feedback Loop
  submitFeedback: async (employeeId, date, label, analyst = "analyst", note = "") => {
    return request(`/api/alerts/${employeeId}/${date}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label, analyst, note }),
    });
  },
  deleteFeedback: async (employeeId, date) => {
    return request(`/api/alerts/${employeeId}/${date}/feedback`, {
      method: "DELETE",
    });
  },
  feedbackStats: () => request("/api/feedback/stats"),

  // Model Retraining & Status
  modelStatus: () => request("/api/model/status"),
  retrainModel: async () => {
    return request("/api/model/retrain", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
  },

  // Threat Graph
  graph: () => request("/api/graph"),

  // Case Management
  cases: (filters = {}) => {
    const params = new URLSearchParams();
    if (filters.status) params.append("status", filters.status);
    if (filters.assignee) params.append("assignee", filters.assignee);
    if (filters.tier) params.append("tier", filters.tier);
    if (filters.limit) params.append("limit", filters.limit);
    if (filters.offset) params.append("offset", filters.offset);
    const qs = params.toString();
    return request(`/api/cases${qs ? `?${qs}` : ""}`);
  },
  caseDetail: (employeeId, date) => request(`/api/cases/${employeeId}/${date}`),
  getCase: (employeeId, date) => request(`/api/cases/${employeeId}/${date}`),
  updateCase: async (employeeId, date, data) => {
    return request(`/api/cases/${employeeId}/${date}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
  },
  addCaseNote: async (employeeId, date, note, author = "analyst") => {
    const payload = typeof note === "string" ? { text: note, author } : note;
    return request(`/api/cases/${employeeId}/${date}/notes`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  },
  getReportPdfUrl: (employeeId, date) => `${API_BASE}/api/cases/${employeeId}/${date}/report.pdf`,

  // Notifications
  notificationsStatus: () => request("/api/notifications/status"),
  sendTestNotification: async () => {
    return request("/api/notifications/test", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
  },

  // SSE Stream
  getAlertsStreamUrl: (minTier) => {
    const qs = minTier ? `?min_tier=${encodeURIComponent(minTier)}` : "";
    return `${API_BASE}/api/stream/alerts${qs}`;
  },

  // SOC Assistant Chat
  assistantChat: async (message, history = [], mode = null) => {
    const body = { message, history };
    if (mode) body.mode = mode;
    return request("/api/assistant/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  // Benchmark Evaluation
  evaluationLatest: () => request("/api/evaluation/latest"),
  evaluationRuns: () => request("/api/evaluation/runs"),
};
