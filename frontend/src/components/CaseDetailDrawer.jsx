import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { api } from "../api.js";
import TierBadge from "./TierBadge.jsx";
import AlertExplainability from "./AlertExplainability.jsx";

export default function CaseDetailDrawer({ targetCase, onClose, onCaseUpdated, currentUser }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Form states
  const [status, setStatus] = useState("New");
  const [assignee, setAssignee] = useState("");
  const [noteText, setNoteText] = useState("");
  const [noteAuthor, setNoteAuthor] = useState(currentUser?.username || "analyst");
  const [savingCase, setSavingCase] = useState(false);
  const [addingNote, setAddingNote] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const fetchCaseDetails = async () => {
    if (!targetCase) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.getCase(targetCase.employee_id, targetCase.date);
      setData(res);
      setStatus(res.case.status || "New");
      setAssignee(res.case.assignee || "");
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCaseDetails();
  }, [targetCase?.employee_id, targetCase?.date]);

  const handleUpdateCase = async (newStatus, newAssignee) => {
    if (!targetCase) return;
    setSavingCase(true);
    try {
      const body = {};
      if (newStatus !== undefined) body.status = newStatus;
      if (newAssignee !== undefined) body.assignee = newAssignee;
      const res = await api.updateCase(targetCase.employee_id, targetCase.date, body);
      setStatus(res.status);
      setAssignee(res.assignee || "");
      if (onCaseUpdated) onCaseUpdated();
    } catch (err) {
      setError(err.message);
    } finally {
      setSavingCase(false);
    }
  };

  const handleAddNote = async (e) => {
    e.preventDefault();
    if (!noteText.trim() || !targetCase) return;
    setAddingNote(true);
    try {
      const newNote = await api.addCaseNote(
        targetCase.employee_id,
        targetCase.date,
        noteText.trim(),
        noteAuthor.trim() || "analyst"
      );
      setData((prev) => ({
        ...prev,
        notes: [newNote, ...(prev?.notes || [])],
      }));
      setNoteText("");
    } catch (err) {
      setError(err.message);
    } finally {
      setAddingNote(false);
    }
  };

  const handleDownloadPdf = async () => {
    if (!targetCase) return;
    setDownloadingPdf(true);
    try {
      const url = api.getReportPdfUrl(targetCase.employee_id, targetCase.date);
      const link = document.createElement("a");
      link.href = url;
      link.download = `incident_report_${targetCase.employee_id}_${targetCase.date}.pdf`;
      link.target = "_blank";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (err) {
      setError(`Failed to download report: ${err.message}`);
    } finally {
      setDownloadingPdf(false);
    }
  };

  if (!targetCase) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
        className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs"
      />

      {/* Drawer */}
      <motion.div
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 25, stiffness: 220 }}
        className="relative z-10 w-full max-w-xl bg-white border-l border-slate-200 h-full flex flex-col shadow-2xl overflow-hidden text-slate-800"
      >
        {/* Header */}
        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50/80">
          <div>
            <div className="flex items-center gap-2.5">
              <span className="text-base font-semibold text-slate-900">
                Case: {targetCase.employee_id}
              </span>
              <span className="text-xs text-slate-500 font-mono">{targetCase.date}</span>
              {data?.alert && <TierBadge tier={data.alert.risk_tier} />}
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              {data?.alert?.employee_name || targetCase.employee_id} &bull;{" "}
              {data?.alert?.department || "General"}
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleDownloadPdf}
              disabled={downloadingPdf}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 hover:bg-slate-200 text-slate-700 ring-1 ring-slate-300 transition-all cursor-pointer shadow-2xs"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <span>{downloadingPdf ? "Generating..." : "Download Report"}</span>
            </button>

            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors cursor-pointer"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-5 bg-slate-50/30">
          {error && (
            <div className="p-3 rounded-lg bg-rose-50 ring-1 ring-rose-200 text-xs text-rose-800">
              {error}
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-16 text-slate-400 text-xs">
              Loading incident details...
            </div>
          ) : (
            <>
              {/* Status & Assignment Box */}
              <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs p-4 space-y-3">
                <div className="text-xs font-semibold uppercase tracking-wider text-slate-600">
                  Case Management
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-[11px] text-slate-500 mb-1 font-medium">Status</label>
                    <select
                      value={status}
                      disabled={savingCase}
                      onChange={(e) => {
                        const newStatus = e.target.value;
                        setStatus(newStatus);
                        handleUpdateCase(newStatus, undefined);
                      }}
                      className="w-full bg-slate-50 ring-1 ring-slate-300 text-slate-800 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-slate-500 focus:bg-white cursor-pointer"
                    >
                      <option value="New">New</option>
                      <option value="Investigating">Investigating</option>
                      <option value="Resolved">Resolved</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] text-slate-500 mb-1 font-medium">Assignee</label>
                    <input
                      type="text"
                      placeholder="e.g. jdoe@security"
                      value={assignee}
                      disabled={savingCase}
                      onChange={(e) => setAssignee(e.target.value)}
                      onBlur={() => handleUpdateCase(undefined, assignee)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") handleUpdateCase(undefined, assignee);
                      }}
                      className="w-full bg-slate-50 ring-1 ring-slate-300 text-slate-800 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-slate-500 focus:bg-white"
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-500 pt-1 border-t border-slate-100">
                  <span>Priority: <strong className="text-slate-800">{data?.case?.priority || data?.alert?.risk_tier || "High"}</strong></span>
                  <span>Risk Score: <strong className="text-slate-900 font-mono font-bold">{data?.alert?.risk_score || "N/A"}/100</strong></span>
                </div>
              </div>

              {/* AI Explanation Callout */}
              {data?.alert && (
                <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase tracking-wider text-slate-700">
                      AI Investigation Agent
                    </span>
                    <span className="text-[10px] text-slate-500 capitalize">
                      Source: {data.alert.agent_source}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 leading-relaxed">
                    {data.alert.explanation}
                  </p>
                  <div className="pt-2 flex flex-wrap gap-1.5">
                    {data.alert.rule_flags?.map((f) => (
                      <span
                        key={f}
                        className="text-[10px] px-2 py-0.5 rounded bg-slate-100 text-slate-700 ring-1 ring-slate-200 font-medium"
                      >
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Model Breakdown */}
              {data?.alert?.model_breakdown && (
                <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs p-4 space-y-2">
                  <div className="text-xs font-semibold uppercase tracking-wider text-slate-600">
                    Detection Ensemble Signals
                  </div>
                  <div className="grid grid-cols-4 gap-2 text-center pt-1">
                    <div className="p-2 rounded bg-slate-50 ring-1 ring-slate-200">
                      <div className="text-[10px] text-slate-500">IsoForest</div>
                      <div className="text-xs font-semibold text-slate-900 font-mono mt-0.5">
                        {data.alert.model_breakdown.isolation_forest}
                      </div>
                    </div>
                    <div className="p-2 rounded bg-slate-50 ring-1 ring-slate-200">
                      <div className="text-[10px] text-slate-500">Autoencoder</div>
                      <div className="text-xs font-semibold text-slate-900 font-mono mt-0.5">
                        {data.alert.model_breakdown.autoencoder}
                      </div>
                    </div>
                    <div className="p-2 rounded bg-slate-50 ring-1 ring-slate-200">
                      <div className="text-[10px] text-slate-500">LSTM Seq</div>
                      <div className="text-xs font-semibold text-slate-900 font-mono mt-0.5">
                        {data.alert.model_breakdown.lstm}
                      </div>
                    </div>
                    <div className="p-2 rounded bg-slate-50 ring-1 ring-slate-200">
                      <div className="text-[10px] text-slate-500">XGBoost</div>
                      <div className="text-xs font-semibold text-slate-900 font-mono mt-0.5">
                        {data.alert.model_breakdown.xgboost}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Explainability Section: TreeSHAP + 7-Day Baseline Deviation */}
              <AlertExplainability
                employeeId={targetCase.employee_id}
                date={targetCase.date}
              />

              {/* Notes Timeline */}
              <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wider text-slate-600">
                    Case Notes ({data?.notes?.length || 0})
                  </span>
                  {data?.feedback && (
                    <span className="text-[11px] text-emerald-700 font-medium">
                      Verdict: {data.feedback.label}
                    </span>
                  )}
                </div>

                <div className="space-y-2.5 max-h-56 overflow-y-auto pr-1">
                  {data?.notes?.map((n) => (
                    <div key={n.id} className="p-2.5 rounded-lg bg-slate-50 ring-1 ring-slate-200 text-xs">
                      <div className="flex items-center justify-between text-[11px] text-slate-500 mb-1">
                        <span className="font-semibold text-slate-900">{n.author}</span>
                        <span className="text-slate-400 font-mono">
                          {new Date(n.created_at).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-slate-700 leading-relaxed">{n.text}</p>
                    </div>
                  ))}

                  {(!data?.notes || data.notes.length === 0) && (
                    <div className="text-center py-4 text-xs text-slate-400 italic">
                      No investigative notes added yet.
                    </div>
                  )}
                </div>

                {/* Add Note Form */}
                <form onSubmit={handleAddNote} className="pt-2 border-t border-slate-100 space-y-2">
                  <textarea
                    rows={2}
                    placeholder="Add an investigative note, interview findings, or triage rationale..."
                    value={noteText}
                    onChange={(e) => setNoteText(e.target.value)}
                    className="w-full bg-slate-50 ring-1 ring-slate-300 text-slate-900 placeholder-slate-400 text-xs rounded-lg p-2.5 focus:outline-none focus:ring-slate-500 focus:bg-white leading-relaxed"
                  />
                  <div className="flex items-center justify-between gap-2">
                    <input
                      type="text"
                      placeholder="Author"
                      value={noteAuthor}
                      onChange={(e) => setNoteAuthor(e.target.value)}
                      className="w-28 bg-slate-50 ring-1 ring-slate-300 text-slate-900 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-slate-500 focus:bg-white"
                    />
                    <button
                      type="submit"
                      disabled={addingNote || !noteText.trim()}
                      className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-900 hover:bg-slate-800 text-white disabled:opacity-50 transition-all cursor-pointer shadow-xs"
                    >
                      {addingNote ? "Adding..." : "Add Note"}
                    </button>
                  </div>
                </form>
              </div>
            </>
          )}
        </div>
      </motion.div>
    </div>
  );
}
