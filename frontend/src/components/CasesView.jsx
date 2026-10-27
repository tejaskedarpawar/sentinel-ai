import { useState, useEffect } from "react";
import { motion } from "framer-motion";
import { api } from "../api.js";
import TierBadge from "./TierBadge.jsx";

const STATUS_BADGES = {
  New: "bg-blue-50 text-blue-700 ring-blue-200",
  Investigating: "bg-amber-50 text-amber-700 ring-amber-200",
  Resolved: "bg-emerald-50 text-emerald-700 ring-emerald-200",
};

export default function CasesView({ onSelectCase }) {
  const [cases, setCases] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const [statusFilter, setStatusFilter] = useState("");
  const [tierFilter, setTierFilter] = useState("");
  const [assigneeSearch, setAssigneeSearch] = useState("");
  const [viewMode, setViewMode] = useState("table"); // "table" | "board"

  const fetchCases = () => {
    setLoading(true);
    setError(null);
    api
      .cases({
        status: statusFilter || undefined,
        tier: tierFilter || undefined,
        assignee: assigneeSearch ? assigneeSearch.trim() : undefined,
        limit: 100,
      })
      .then((res) => {
        setCases(Array.isArray(res) ? res : res.items || []);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchCases();
  }, [statusFilter, tierFilter, assigneeSearch]);

  const newCases = cases.filter((c) => c.status === "New");
  const investigatingCases = cases.filter((c) => c.status === "Investigating");
  const resolvedCases = cases.filter((c) => c.status === "Resolved");

  return (
    <div className="space-y-5">
      {/* Filters Bar & View Switcher */}
      <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex flex-wrap items-center gap-3">
          {/* Status Tabs */}
          <div className="flex rounded-lg bg-slate-100 p-1 ring-1 ring-slate-200">
            {["", "New", "Investigating", "Resolved"].map((st) => (
              <button
                key={st || "all"}
                onClick={() => setStatusFilter(st)}
                className={`px-3 py-1 text-xs rounded-md capitalize transition-all cursor-pointer ${
                  statusFilter === st
                    ? "bg-white text-slate-900 font-semibold shadow-2xs ring-1 ring-slate-200/60"
                    : "text-slate-600 hover:text-slate-900 font-medium"
                }`}
              >
                {st || "All Statuses"}
              </button>
            ))}
          </div>

          {/* Tier Filter */}
          <select
            value={tierFilter}
            onChange={(e) => setTierFilter(e.target.value)}
            className="bg-slate-50 ring-1 ring-slate-300 text-slate-800 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-slate-500 focus:bg-white cursor-pointer"
          >
            <option value="">All Tiers</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
          </select>

          {/* Assignee Search */}
          <input
            type="text"
            placeholder="Filter assignee..."
            value={assigneeSearch}
            onChange={(e) => setAssigneeSearch(e.target.value)}
            className="bg-slate-50 ring-1 ring-slate-300 text-slate-800 placeholder-slate-400 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:ring-slate-500 focus:bg-white w-36"
          />
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-500 mr-1 font-medium">{cases.length} incidents</span>
          <div className="flex rounded-lg bg-slate-100 p-1 ring-1 ring-slate-200">
            <button
              onClick={() => setViewMode("table")}
              className={`px-2.5 py-1 text-xs rounded-md transition-all cursor-pointer ${
                viewMode === "table"
                  ? "bg-white text-slate-900 font-semibold shadow-2xs"
                  : "text-slate-600 hover:text-slate-900 font-medium"
              }`}
            >
              Table View
            </button>
            <button
              onClick={() => setViewMode("board")}
              className={`px-2.5 py-1 text-xs rounded-md transition-all cursor-pointer ${
                viewMode === "board"
                  ? "bg-white text-slate-900 font-semibold shadow-2xs"
                  : "text-slate-600 hover:text-slate-900 font-medium"
              }`}
            >
              Board View
            </button>
          </div>
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-lg bg-rose-50 ring-1 ring-rose-200 text-xs text-rose-800">
          {error}
        </div>
      )}

      {loading ? (
        <div className="py-20 text-center text-slate-400 text-xs">Loading incident cases...</div>
      ) : viewMode === "table" ? (
        /* Table View */
        <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs overflow-hidden">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-50/80 border-b border-slate-200 text-slate-500 uppercase text-[10px] tracking-wider font-semibold">
              <tr>
                <th className="px-5 py-3">Employee</th>
                <th className="px-5 py-3">Date</th>
                <th className="px-5 py-3">Risk Level</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Assignee</th>
                <th className="px-5 py-3">Feedback</th>
                <th className="px-5 py-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {cases.map((c) => {
                const statusStyle = STATUS_BADGES[c.status] || STATUS_BADGES.New;
                return (
                  <tr
                    key={`${c.employee_id}-${c.date}`}
                    onClick={() => onSelectCase(c)}
                    className="hover:bg-slate-50/70 cursor-pointer transition-colors"
                  >
                    <td className="px-5 py-3.5">
                      <div className="font-semibold text-slate-900">{c.employee_id}</div>
                      <div className="text-[11px] text-slate-500">
                        {c.employee_name} &bull; {c.department}
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-slate-500 font-mono">{c.date}</td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <TierBadge tier={c.risk_tier} />
                        <span className="font-mono text-slate-600">{c.risk_score}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-medium ring-1 ${statusStyle}`}>
                        {c.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-slate-700">
                      {c.assignee || <span className="text-slate-400 italic">Unassigned</span>}
                    </td>
                    <td className="px-5 py-3.5">
                      {c.has_feedback ? (
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                            c.feedback_label === "threat"
                              ? "bg-rose-50 text-rose-700 ring-1 ring-rose-200"
                              : "bg-slate-100 text-slate-700 ring-1 ring-slate-200"
                          }`}
                        >
                          {c.feedback_label === "threat" ? "Threat" : "False Positive"}
                        </span>
                      ) : (
                        <span className="text-slate-400 text-[10px]">None</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectCase(c);
                        }}
                        className="px-2.5 py-1 rounded text-xs font-semibold text-slate-800 hover:text-slate-950 hover:bg-slate-100 transition-colors"
                      >
                        Inspect &rarr;
                      </button>
                    </td>
                  </tr>
                );
              })}
              {cases.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-5 py-12 text-center text-slate-400">
                    No cases match the selected filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      ) : (
        /* Board View (Kanban) */
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {[
            { id: "New", title: "New Alerts", list: newCases, color: "text-blue-800 border-blue-200" },
            { id: "Investigating", title: "Under Investigation", list: investigatingCases, color: "text-amber-800 border-amber-200" },
            { id: "Resolved", title: "Resolved / Dismissed", list: resolvedCases, color: "text-emerald-800 border-emerald-200" },
          ].map((col) => (
            <div key={col.id} className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs p-4 flex flex-col h-[600px]">
              <div className="flex items-center justify-between pb-3 border-b border-slate-100 mb-3">
                <span className={`text-xs font-semibold uppercase tracking-wider ${col.color.split(" ")[0]}`}>
                  {col.title}
                </span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium">
                  {col.list.length}
                </span>
              </div>

              <div className="flex-1 overflow-y-auto space-y-3 pr-1">
                {col.list.map((c) => (
                  <motion.div
                    key={`${c.employee_id}-${c.date}`}
                    whileHover={{ scale: 1.01 }}
                    onClick={() => onSelectCase(c)}
                    className="p-3.5 rounded-lg bg-slate-50/70 ring-1 ring-slate-200 hover:ring-slate-300 hover:bg-slate-50 cursor-pointer transition-all space-y-2 shadow-2xs"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-900 text-xs">{c.employee_id}</span>
                      <TierBadge tier={c.risk_tier} />
                    </div>
                    <div className="text-[11px] text-slate-500">
                      {c.employee_name} &bull; <span className="font-mono">{c.date}</span>
                    </div>
                    <div className="flex items-center justify-between text-[11px] pt-1 border-t border-slate-200/60">
                      <span className="text-slate-500">
                        {c.assignee ? c.assignee : "Unassigned"}
                      </span>
                      <span className="font-mono font-medium text-slate-800">{c.risk_score}</span>
                    </div>
                  </motion.div>
                ))}
                {col.list.length === 0 && (
                  <div className="py-12 text-center text-slate-400 text-xs italic">
                    No cases in this stage
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
