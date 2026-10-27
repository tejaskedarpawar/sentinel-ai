import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import TierBadge from "./TierBadge.jsx";

const STATUS_BADGES = {
  New: "bg-blue-50 text-blue-700 ring-blue-200",
  Investigating: "bg-amber-50 text-amber-700 ring-amber-200",
  Resolved: "bg-emerald-50 text-emerald-700 ring-emerald-200",
};

export default function IncidentQueue({ alerts, onSelect, onFeedbackChange, onOpenCase }) {
  const [showReviewed, setShowReviewed] = useState(false);
  const [loadingAlertId, setLoadingAlertId] = useState(null);

  const reviewedCount = alerts.filter((a) => a.feedback).length;
  const pendingCount = alerts.length - reviewedCount;

  const visibleAlerts = alerts.filter((a) => {
    if (showReviewed) return true;
    return !a.feedback;
  });

  const handleAction = async (e, alert, label) => {
    e.stopPropagation();
    const alertKey = `${alert.employee_id}-${alert.date}`;
    setLoadingAlertId(alertKey);
    try {
      await onFeedbackChange(alert.employee_id, alert.date, label);
    } finally {
      setLoadingAlertId(null);
    }
  };

  const handleUndo = async (e, alert) => {
    e.stopPropagation();
    const alertKey = `${alert.employee_id}-${alert.date}`;
    setLoadingAlertId(alertKey);
    try {
      await onFeedbackChange(alert.employee_id, alert.date, null);
    } finally {
      setLoadingAlertId(null);
    }
  };

  const handleCardClick = (a) => {
    if (onSelect) onSelect(a.employee_id);
    if (onOpenCase) onOpenCase(a);
  };

  return (
    <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs overflow-hidden">
      {/* Header with Title and Show Reviewed Toggle */}
      <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between flex-wrap gap-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-800">
            Incident Timeline &mdash; AI Investigation Agent
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium">
            {pendingCount} pending
          </span>
        </div>

        {/* Show reviewed toggle */}
        <label className="flex items-center gap-2 cursor-pointer select-none text-xs text-slate-500 hover:text-slate-800 transition-colors">
          <span>Show reviewed ({reviewedCount})</span>
          <div
            onClick={() => setShowReviewed(!showReviewed)}
            className={`w-9 h-5 flex items-center rounded-full p-0.5 transition-colors cursor-pointer ${
              showReviewed ? "bg-slate-800" : "bg-slate-300"
            }`}
          >
            <div
              className={`bg-white w-4 h-4 rounded-full shadow-xs transform transition-transform ${
                showReviewed ? "translate-x-4" : "translate-x-0"
              }`}
            />
          </div>
        </label>
      </div>

      {/* Alert Cards Container */}
      <div className="max-h-[540px] overflow-y-auto divide-y divide-slate-100">
        <AnimatePresence mode="popLayout">
          {visibleAlerts.map((a) => {
            const alertKey = `${a.employee_id}-${a.date}`;
            const isLoading = loadingAlertId === alertKey;
            const caseStatus = a.case_status || "New";
            const statusStyle = STATUS_BADGES[caseStatus] || STATUS_BADGES.New;

            const isCritical = a.risk_tier === "Critical";

            return (
              <motion.div
                key={a.id || alertKey}
                layout
                initial={{ opacity: 0, y: -20, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.3, ease: "easeOut" }}
                onClick={() => handleCardClick(a)}
                className={`px-5 py-3.5 hover:bg-slate-50/80 cursor-pointer transition-all ${
                  isCritical
                    ? "bg-rose-50/40 border-l-4 border-l-rose-500"
                    : a.feedback
                    ? "bg-slate-50/50"
                    : ""
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`font-semibold text-sm ${isCritical ? "text-rose-900 font-mono font-bold" : "text-slate-900"}`}>
                      {a.employee_id}
                    </span>
                    <span className="text-xs text-slate-400 font-mono">{a.date}</span>
                    {a.is_live && (
                      <span className="inline-flex items-center gap-1 px-1.5 py-0.2 rounded text-[9px] font-bold tracking-wider uppercase bg-rose-100 text-rose-700 ring-1 ring-rose-200">
                        LIVE
                      </span>
                    )}
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium ring-1 ${statusStyle}`}>
                      {caseStatus}
                    </span>

                    {a.assignee && (
                      <span className="text-[10px] text-slate-500 bg-slate-100 px-1.5 py-0.5 rounded">
                        @{a.assignee}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <TierBadge tier={a.risk_tier} />
                    <span className="text-xs text-slate-500 font-mono w-9 text-right">{a.risk_score}</span>
                  </div>
                </div>

                <p className="mt-1.5 text-xs text-slate-600 leading-relaxed">{a.explanation}</p>

                {/* Flags */}
                <div className="mt-2 flex gap-1.5 flex-wrap items-center">
                  {a.rule_flags?.map((f) => (
                    <span
                      key={f}
                      className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 font-medium"
                    >
                      {f}
                    </span>
                  ))}
                </div>

                {/* Feedback Action / Labeled State Bar */}
                <div className="mt-3 pt-2.5 border-t border-slate-100 flex items-center justify-between flex-wrap gap-2">
                  <div className="flex items-center gap-3 text-[11px] text-slate-500">
                    <span>
                      XGBoost score:{" "}
                      <span className="text-slate-700 font-mono font-medium">
                        {a.model_breakdown?.xgboost ?? "N/A"}
                      </span>
                    </span>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (onOpenCase) onOpenCase(a);
                      }}
                      className="text-slate-900 hover:underline font-semibold cursor-pointer"
                    >
                      Case File &amp; PDF &rarr;
                    </button>
                  </div>

                  {a.feedback ? (
                    <div className="flex items-center gap-2.5">
                      {a.feedback.label === "threat" ? (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-50 text-rose-700 ring-1 ring-rose-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                          Confirmed Threat
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 ring-1 ring-slate-200">
                          <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
                          False Positive
                        </span>
                      )}
                      <button
                        onClick={(e) => handleUndo(e, a)}
                        disabled={isLoading}
                        className="text-[11px] text-slate-500 hover:text-slate-800 underline disabled:opacity-50 transition-colors cursor-pointer"
                      >
                        Undo
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={(e) => handleAction(e, a, "threat")}
                        disabled={isLoading}
                        className="px-2.5 py-1 rounded text-xs font-medium bg-rose-50 text-rose-700 hover:bg-rose-100 ring-1 ring-rose-200 active:scale-95 disabled:opacity-50 transition-all cursor-pointer"
                      >
                        Confirm threat
                      </button>
                      <button
                        onClick={(e) => handleAction(e, a, "false_positive")}
                        disabled={isLoading}
                        className="px-2.5 py-1 rounded text-xs font-medium bg-slate-100 text-slate-700 hover:bg-slate-200 ring-1 ring-slate-200 active:scale-95 disabled:opacity-50 transition-all cursor-pointer"
                      >
                        False positive
                      </button>
                    </div>
                  )}
                </div>
              </motion.div>
            );
          })}
        </AnimatePresence>

        {visibleAlerts.length === 0 && (
          <div className="px-5 py-10 text-center text-slate-400 text-xs">
            {showReviewed
              ? "No alerts found."
              : pendingCount === 0 && reviewedCount > 0
              ? `All ${reviewedCount} alerts reviewed! Toggle "Show reviewed" to inspect or undo.`
              : "No High/Critical alerts in queue."}
          </div>
        )}
      </div>
    </div>
  );
}
