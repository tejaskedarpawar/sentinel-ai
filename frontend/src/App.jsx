import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { api } from "./api.js";
import StatsBar from "./components/StatsBar.jsx";
import EmployeeTable from "./components/EmployeeTable.jsx";
import RiskTimelineChart from "./components/RiskTimelineChart.jsx";
import IncidentQueue from "./components/IncidentQueue.jsx";
import ThreatGraph from "./components/ThreatGraph.jsx";

export default function App() {
  const [stats, setStats] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [graph, setGraph] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [error, setError] = useState(null);
  const [view, setView] = useState("dashboard"); // "dashboard" | "graph"

  useEffect(() => {
    Promise.all([api.stats(), api.employees(), api.alerts(), api.graph()])
      .then(([s, e, a, g]) => {
        setStats(s);
        setEmployees(e);
        setAlerts(a);
        setGraph(g);
        if (e.length > 0) setSelectedId(e[0].id);
      })
      .catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!selectedId) return;
    api.employeeTimeline(selectedId).then(setTimeline).catch((err) => setError(err.message));
  }, [selectedId]);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 px-6 py-6">
      <header className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">
            Sentinel <span className="text-sky-400">AI</span>
          </h1>
          <p className="text-xs text-slate-500">
            Privacy-preserving insider data exfiltration detection — SOC Dashboard
          </p>
        </div>
        <nav className="flex gap-1 rounded-lg bg-slate-900 ring-1 ring-slate-800 p-1">
          {["dashboard", "graph"].map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`px-3 py-1.5 text-xs rounded-md capitalize transition-colors ${
                view === v ? "bg-sky-500/20 text-sky-300" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {v === "graph" ? "Threat Graph" : "Dashboard"}
            </button>
          ))}
        </nav>
      </header>

      {error && (
        <div className="mb-4 rounded-lg bg-red-500/10 ring-1 ring-red-500/30 px-4 py-3 text-sm text-red-300">
          Couldn't reach the API — is the backend running on :8000? ({error})
        </div>
      )}

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-6">
        <StatsBar stats={stats} />
      </motion.div>

      {view === "dashboard" ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-1">
            <EmployeeTable employees={employees} selectedId={selectedId} onSelect={setSelectedId} />
          </div>
          <div className="lg:col-span-2 space-y-5">
            <RiskTimelineChart timeline={timeline} employeeId={selectedId} />
            <IncidentQueue alerts={alerts} onSelect={setSelectedId} />
          </div>
        </div>
      ) : (
        <ThreatGraph graph={graph} />
      )}
    </div>
  );
}
