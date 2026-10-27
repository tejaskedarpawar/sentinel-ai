import { useState, useEffect } from "react";
import { api } from "../api.js";

export default function NotificationsCard() {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [error, setError] = useState(null);

  const fetchStatus = () => {
    setLoading(true);
    api.notificationsStatus()
      .then((data) => {
        setStatus(data);
        setError(null);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchStatus();
  }, []);

  const handleSendTest = async () => {
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      const res = await api.sendTestNotification();
      setTestResult(res);
      fetchStatus();
    } catch (err) {
      setError(err.message);
    } finally {
      setTesting(false);
    }
  };

  const channels = status?.channels || {
    slack: { name: "Slack Webhook", configured: false },
    telegram: { name: "Telegram Bot", configured: false },
    email: { name: "SMTP Email", configured: false },
  };

  return (
    <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-slate-600" />
          <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-700">
            Outbound Notifications
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {status?.min_tier && (
            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-mono">
              Min: {status.min_tier}
            </span>
          )}
          <button
            onClick={handleSendTest}
            disabled={testing || loading}
            className="text-[11px] px-2.5 py-1 rounded bg-slate-100 hover:bg-slate-200 text-slate-800 ring-1 ring-slate-300 transition-colors disabled:opacity-50 cursor-pointer font-medium shadow-2xs"
          >
            {testing ? "Testing..." : "Send test"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-2 text-[11px] text-rose-800 bg-rose-50 p-2 rounded ring-1 ring-rose-200">
          {error}
        </div>
      )}

      {/* Channel Badges Grid */}
      <div className="grid grid-cols-3 gap-2">
        {Object.entries(channels).map(([key, ch]) => {
          const isConfigured = ch.configured;
          return (
            <div
              key={key}
              className={`px-2.5 py-2 rounded-lg border text-xs flex flex-col justify-between ${
                isConfigured
                  ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                  : "bg-slate-50 border-slate-200 text-slate-500"
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="font-medium text-[11px]">{ch.name}</span>
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    isConfigured ? "bg-emerald-600 animate-pulse" : "bg-slate-400"
                  }`}
                />
              </div>
              <span className="text-[10px] text-slate-400">
                {isConfigured ? "Configured" : "Disabled"}
              </span>
            </div>
          );
        })}
      </div>

      {/* Test Results Output */}
      {testResult && (
        <div className="mt-3 p-2.5 rounded-lg bg-slate-50 ring-1 ring-slate-200 text-[11px] space-y-1">
          <div className="flex items-center justify-between text-slate-600 font-medium">
            <span>Test Dispatch Results:</span>
            <button
              onClick={() => setTestResult(null)}
              className="text-[10px] text-slate-400 hover:text-slate-600 cursor-pointer"
            >
              &times;
            </button>
          </div>
          <div className="grid grid-cols-3 gap-1 pt-1 text-[10px] font-mono">
            <div>
              <span className="text-slate-400">Slack: </span>
              <span className={testResult.results?.slack === "sent" ? "text-emerald-700 font-bold" : "text-slate-500"}>
                {testResult.results?.slack || "n/a"}
              </span>
            </div>
            <div>
              <span className="text-slate-400">Telegram: </span>
              <span className={testResult.results?.telegram === "sent" ? "text-emerald-700 font-bold" : "text-slate-500"}>
                {testResult.results?.telegram || "n/a"}
              </span>
            </div>
            <div>
              <span className="text-slate-400">SMTP: </span>
              <span className={testResult.results?.email === "sent" ? "text-emerald-700 font-bold" : "text-slate-500"}>
                {testResult.results?.email || "n/a"}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
