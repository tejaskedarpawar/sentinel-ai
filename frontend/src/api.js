const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function request(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API error ${res.status}: ${path}`);
  }
  return res.json();
}

export const api = {
  health: () => request("/api/health"),
  stats: () => request("/api/stats"),
  employees: () => request("/api/employees"),
  employeeTimeline: (id) => request(`/api/employees/${id}/timeline`),
  alerts: (tier) => request(`/api/alerts${tier ? `?tier=${tier}` : ""}`),
  graph: () => request("/api/graph"),
};
