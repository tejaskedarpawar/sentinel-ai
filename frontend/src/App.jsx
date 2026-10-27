import { useEffect, useState, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "./api.js";
import { useAlertsStream } from "./hooks/useAlertsStream.js";
import StatsBar from "./components/StatsBar.jsx";
import EmployeeTable from "./components/EmployeeTable.jsx";
import RiskTimelineChart from "./components/RiskTimelineChart.jsx";
import IncidentQueue from "./components/IncidentQueue.jsx";
import ThreatGraph from "./components/ThreatGraph.jsx";
import ModelPanel from "./components/ModelPanel.jsx";
import CasesView from "./components/CasesView.jsx";
import CaseDetailDrawer from "./components/CaseDetailDrawer.jsx";
import NotificationsCard from "./components/NotificationsCard.jsx";
import SOCAssistantDrawer from "./components/SOCAssistantDrawer.jsx";
import EvaluationView from "./components/EvaluationView.jsx";
import LoginView from "./components/LoginView.jsx";

export default function App() {
  const [currentUser, setCurrentUser] = useState(() => api.getAuthUser());
  const [stats, setStats] = useState(null);
  const [employees, setEmployees] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const [graph, setGraph] = useState(null);
  const [modelStatus, setModelStatus] = useState(null);
  const [feedbackStats, setFeedbackStats] = useState(null);

  const [selectedId, setSelectedId] = useState(null);
  const [timeline, setTimeline] = useState([]);
  const [error, setError] = useState(null);
  const [view, setView] = useState("dashboard"); // "dashboard" | "cases" | "graph" | "model"
  const [activeCase, setActiveCase] = useState(null); // { employee_id, date }
  const [toasts, setToasts] = useState([]);
  const [liveAlertCount, setLiveAlertCount] = useState(0);
  const [isAssistantOpen, setIsAssistantOpen] = useState(false);


  const addToast = (alert) => {
    const toastId = `${alert.employee_id}-${alert.date}-${Date.now()}`;
    setToasts((prev) => [{ id: toastId, alert }, ...prev.slice(0, 3)]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== toastId));
    }, 6500);
  };

  const handleIncomingAlert = useCallback((newAlert) => {
    setAlerts((current) => {
      const exists = current.some(
        (a) => a.employee_id === newAlert.employee_id && a.date === newAlert.date
      );
      if (exists) {
        return current.map((a) =>
          a.employee_id === newAlert.employee_id && a.date === newAlert.date
            ? { ...a, ...newAlert, is_live: true }
            : a
        );
      }
      return [{ ...newAlert, is_live: true }, ...current];
    });

    setLiveAlertCount((c) => c + 1);
    addToast(newAlert);
  }, []);

  const { status: streamStatus } = useAlertsStream({
    onAlert: handleIncomingAlert,
    enabled: !!currentUser,
  });

  const refreshData = () => {
    if (!currentUser) return;
    Promise.all([
      api.stats(),
      api.employees(),
      api.alerts(),
      api.graph(),
      api.modelStatus(),
      api.feedbackStats(),
    ])
      .then(([s, e, a, g, ms, fs]) => {
        setStats(s);
        setEmployees(e);
        setAlerts(a);
        setGraph(g);
        setModelStatus(ms);
        setFeedbackStats(fs);
        if (e.length > 0 && !selectedId) setSelectedId(e[0].id);
      })
      .catch((err) => setError(err.message));
  };

  useEffect(() => {
    const token = api.getAuthToken();
    if (token) {
      api
        .getMe()
        .then((u) => {
          setCurrentUser(u);
          api.setAuth(token, u);
        })
        .catch(() => {
          api.setAuth(null, null);
          setCurrentUser(null);
        });
    }

    const handleAuthInvalid = () => {
      setCurrentUser(null);
    };
    window.addEventListener("sentinel:auth-invalid", handleAuthInvalid);
    return () => window.removeEventListener("sentinel:auth-invalid", handleAuthInvalid);
  }, []);

  useEffect(() => {
    if (currentUser) {
      refreshData();
    }
  }, [currentUser]);

  useEffect(() => {
    if (!selectedId || !currentUser) return;
    api.employeeTimeline(selectedId).then(setTimeline).catch((err) => setError(err.message));
  }, [selectedId, currentUser]);

  const handleLogout = async () => {
    await api.logout();
    setCurrentUser(null);
    setStats(null);
    setEmployees([]);
    setAlerts([]);
  };

  const handleFeedbackChange = async (employeeId, date, label) => {
    const prevAlerts = [...alerts];
    const analystName = currentUser?.username || "analyst";

    // Optimistic UI update
    setAlerts((current) =>
      current.map((a) => {
        if (a.employee_id === employeeId && a.date === date) {
          const updatedCaseStatus = label === "false_positive" ? "Resolved" : "Investigating";
          return {
            ...a,
            feedback: label
              ? {
                  label,
                  analyst: analystName,
                  created_at: new Date().toISOString(),
                }
              : null,
            case_status: label ? updatedCaseStatus : a.case_status,
          };
        }
        return a;
      })
    );

    try {
      if (label) {
        await api.submitFeedback(employeeId, date, label, analystName);
      } else {
        await api.deleteFeedback(employeeId, date);
      }
      const [fs, ms, updatedAlerts] = await Promise.all([
        api.feedbackStats(),
        api.modelStatus(),
        api.alerts(),
      ]);
      setFeedbackStats(fs);
      setModelStatus(ms);
      setAlerts(updatedAlerts);
    } catch (err) {
      setAlerts(prevAlerts);
      setError(`Feedback update failed: ${err.message}`);
    }
  };

  const handleRetrainSuccess = async () => {
    const res = await api.retrainModel();
    const [s, e, a, ms, fs] = await Promise.all([
      api.stats(),
      api.employees(),
      api.alerts(),
      api.modelStatus(),
      api.feedbackStats(),
    ]);
    setStats(s);
    setEmployees(e);
    setAlerts(a);
    setModelStatus(ms);
    setFeedbackStats(fs);
    if (selectedId) {
      api.employeeTimeline(selectedId).then(setTimeline).catch(() => {});
    }
    return res;
  };

  if (!currentUser) {
    return <LoginView onLoginSuccess={(u) => setCurrentUser(u)} />;
  }

  return (
    <div className="min-h-screen bg-[#f8fafc] text-slate-800 px-6 py-6 font-sans">
      <header className="flex items-center justify-between mb-6 flex-wrap gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-slate-900">
            Sentinel <span className="text-slate-900 font-bold">AI</span>
          </h1>
          <p className="text-xs text-slate-500">
            Privacy-preserving insider data exfiltration detection — SOC Dashboard &amp; Case Management
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Real-time SSE Stream Connection Indicator */}
          <div
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ring-1 transition-colors ${
              streamStatus === "Live"
                ? "bg-emerald-50 text-emerald-800 ring-emerald-200"
                : streamStatus === "Reconnecting"
                ? "bg-amber-50 text-amber-800 ring-amber-200 animate-pulse"
                : "bg-slate-100 text-slate-600 ring-slate-200"
            }`}
          >
            <span
              className={`w-1.5 h-1.5 rounded-full ${
                streamStatus === "Live"
                  ? "bg-emerald-600 animate-pulse"
                  : streamStatus === "Reconnecting"
                  ? "bg-amber-500 animate-ping"
                  : "bg-slate-400"
              }`}
            />
            <span className="font-mono text-[11px]">{streamStatus}</span>
          </div>

          {/* Real-time Alert Counter Badge */}
          {liveAlertCount > 0 && (
            <button
              onClick={() => setLiveAlertCount(0)}
              title="Click to clear live alert counter"
              className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 ring-1 ring-rose-200 hover:bg-rose-100 transition-colors cursor-pointer"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 animate-ping" />
              <span>+{liveAlertCount} new</span>
            </button>
          )}

          <nav className="flex gap-1 rounded-lg bg-slate-200/70 ring-1 ring-slate-300/80 p-1">
            {[
              { id: "dashboard", label: "Dashboard" },
              { id: "cases", label: "Cases & Reports" },
              { id: "graph", label: "Threat Graph" },
              {
                id: "model",
                label: "Model Retraining",
                badge: modelStatus?.mode === "supervised" ? "Supervised" : null,
              },
              { id: "evaluation", label: "Evaluation" },
            ].map((item) => (
              <button
                key={item.id}
                onClick={() => setView(item.id)}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md capitalize transition-all cursor-pointer ${
                  view === item.id
                    ? "bg-white text-slate-900 font-semibold shadow-xs ring-1 ring-slate-200/60"
                    : "text-slate-600 hover:text-slate-900 font-medium"
                }`}
              >
                <span>{item.label}</span>
                {item.badge && (
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-600 inline-block" />
                )}
              </button>
            ))}
          </nav>

          {/* Operator Profile Badge & Sign Out Button */}
          <div className="flex items-center gap-2.5 pl-3 border-l border-slate-200">
            <div className="flex items-center gap-2">
              <div className="w-7 h-7 rounded-full bg-slate-900 text-white flex items-center justify-center text-xs font-semibold uppercase ring-2 ring-slate-200">
                {currentUser?.username ? currentUser.username.slice(0, 2) : "OP"}
              </div>
              <div className="hidden sm:block text-left">
                <div className="text-xs font-semibold text-slate-900 leading-tight flex items-center gap-1.5">
                  <span>{currentUser?.full_name || currentUser?.username}</span>
                  <span
                    className={`text-[9px] font-bold uppercase px-1.5 py-0.5 rounded tracking-wider ${
                      currentUser?.role === "admin"
                        ? "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-200"
                        : "bg-slate-100 text-slate-700 ring-1 ring-slate-200"
                    }`}
                  >
                    {currentUser?.role || "analyst"}
                  </span>
                </div>
                <div className="text-[10px] text-slate-400 font-mono">@{currentUser?.username}</div>
              </div>
            </div>

            <button
              onClick={handleLogout}
              id="logout-button"
              title="Sign out of SOC Console"
              className="p-1.5 text-slate-400 hover:text-rose-600 hover:bg-rose-50 rounded-lg transition cursor-pointer"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-lg bg-rose-50 ring-1 ring-rose-200 px-4 py-3 text-sm text-rose-800 flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={() => setError(null)}
            className="text-xs text-red-400 hover:text-red-200 underline ml-4 cursor-pointer"
          >
            Dismiss
          </button>
        </div>
      )}

      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mb-6">
        <StatsBar stats={stats} />
      </motion.div>

      {view === "dashboard" && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          <div className="lg:col-span-1 space-y-5">
            <EmployeeTable employees={employees} selectedId={selectedId} onSelect={setSelectedId} />
            <NotificationsCard />
          </div>
          <div className="lg:col-span-2 space-y-5">
            <RiskTimelineChart timeline={timeline} employeeId={selectedId} />
            <IncidentQueue
              alerts={alerts}
              onSelect={setSelectedId}
              onFeedbackChange={handleFeedbackChange}
              onOpenCase={(alert) => setActiveCase({ employee_id: alert.employee_id, date: alert.date })}
            />
          </div>
        </div>
      )}

      {view === "cases" && (
        <CasesView
          onSelectCase={(c) => setActiveCase({ employee_id: c.employee_id, date: c.date })}
        />
      )}

      {view === "graph" && <ThreatGraph graph={graph} />}

      {view === "model" && (
        <ModelPanel
          modelStatus={modelStatus}
          feedbackStats={feedbackStats}
          onRetrainSuccess={handleRetrainSuccess}
        />
      )}

      {view === "evaluation" && <EvaluationView />}

      {/* Right-side Case & Report Drawer */}
      <AnimatePresence>
        {activeCase && (
          <CaseDetailDrawer
            targetCase={activeCase}
            currentUser={currentUser}
            onClose={() => setActiveCase(null)}
            onCaseUpdated={() => {
              api.alerts().then(setAlerts).catch(() => {});
            }}
          />
        )}
      </AnimatePresence>

      {/* Real-time Alert Toast Notifications (Offset to not block assistant button) */}
      <div className="fixed bottom-20 right-6 z-40 flex flex-col gap-2.5 max-w-sm pointer-events-none">
        <AnimatePresence>
          {toasts.map(({ id, alert }) => {
            const isCritical = alert.risk_tier === "Critical";
            return (
              <motion.div
                key={id}
                initial={{ opacity: 0, x: 40, scale: 0.95 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: 40, scale: 0.9 }}
                transition={{ duration: 0.25 }}
                className={`pointer-events-auto p-3.5 rounded-xl shadow-lg ring-1 backdrop-blur-md flex items-start justify-between gap-3 ${
                  isCritical
                    ? "bg-white ring-rose-200 border-l-4 border-l-rose-500 text-slate-800"
                    : "bg-white ring-amber-200 border-l-4 border-l-amber-500 text-slate-800"
                }`}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span
                      className={`text-[10px] font-bold px-1.5 py-0.5 rounded uppercase tracking-wider ${
                        isCritical
                          ? "bg-rose-50 text-rose-700 ring-1 ring-rose-200"
                          : "bg-amber-50 text-amber-700 ring-1 ring-amber-200"
                      }`}
                    >
                      {alert.risk_tier} Alert
                    </span>
                    <span className="text-xs font-mono font-bold text-slate-900">
                      {alert.employee_id}
                    </span>
                    <span className="text-[10px] text-slate-400 font-mono">{alert.date}</span>
                  </div>
                  <p className="text-xs text-slate-600 line-clamp-2 leading-snug">
                    {alert.explanation || `Risk score ${alert.risk_score?.toFixed(1)} detected.`}
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    <button
                      onClick={() => {
                        setSelectedId(alert.employee_id);
                        setActiveCase({ employee_id: alert.employee_id, date: alert.date });
                        setToasts((prev) => prev.filter((t) => t.id !== id));
                      }}
                      className="text-[11px] text-slate-900 hover:text-slate-700 font-semibold underline cursor-pointer"
                    >
                      Inspect Case &rarr;
                    </button>
                  </div>
                </div>
                <button
                  onClick={() => setToasts((prev) => prev.filter((t) => t.id !== id))}
                  className="text-slate-400 hover:text-slate-600 text-base leading-none p-1 cursor-pointer"
                >
                  &times;
                </button>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      {/* Floating SOC Assistant Button */}
      <button
        onClick={() => setIsAssistantOpen(true)}
        title="Open SOC Security Assistant"
        className="fixed bottom-6 right-6 z-40 flex items-center gap-2.5 px-4 py-2.5 rounded-full bg-slate-900 hover:bg-slate-800 text-white font-medium text-xs shadow-lg ring-1 ring-slate-900/10 hover:scale-105 active:scale-95 transition-all cursor-pointer select-none"
      >
        <div className="relative">
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
          <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
        </div>
        <span>SOC Assistant</span>
      </button>

      {/* Slide-over SOC Assistant Drawer */}
      <SOCAssistantDrawer
        isOpen={isAssistantOpen}
        onClose={() => setIsAssistantOpen(false)}
      />
    </div>
  );
}


