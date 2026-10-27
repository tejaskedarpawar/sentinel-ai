import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  ErrorBar,
} from "recharts";
import { api } from "../api.js";

export default function AlertExplainability({ employeeId, date }) {
  const [explainData, setExplainData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!employeeId || !date) return;
    setLoading(true);
    setError(null);
    api
      .explainAlert(employeeId, date)
      .then((res) => {
        setExplainData(res);
      })
      .catch((err) => {
        setError(err.message);
      })
      .finally(() => setLoading(false));
  }, [employeeId, date]);

  if (loading) {
    return (
      <div className="rounded-xl bg-white ring-1 ring-slate-200 p-4 space-y-3 shadow-xs">
        <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wider text-slate-600">
          <svg className="animate-spin h-3.5 w-3.5 text-slate-600" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
          </svg>
          <span>Computing TreeSHAP Feature Attributions...</span>
        </div>
        <div className="h-44 bg-slate-50 animate-pulse rounded-lg" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-xl bg-white ring-1 ring-slate-200 p-4 shadow-xs">
        <div className="text-xs text-amber-700 font-medium">Why was this flagged?</div>
        <div className="text-xs text-slate-500 mt-1">
          Unable to generate detailed feature attributions ({error}).
        </div>
      </div>
    );
  }

  if (!explainData) return null;

  const shapData = explainData.shap || [];
  const baselineData = (explainData.baseline || []).map((b) => ({
    ...b,
    errorY: [b.std, b.std],
  }));

  return (
    <div className="rounded-xl bg-white ring-1 ring-slate-200/90 p-4 space-y-4 shadow-xs">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-800">
            Why was this flagged?
          </span>
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 font-medium ring-1 ring-slate-200">
            TreeSHAP + 7-Day Baseline
          </span>
        </div>
        {!explainData.model_available && (
          <span className="text-[10px] text-amber-700 italic">
            Model explainer artifact not found
          </span>
        )}
      </div>

      {/* Dynamic Plain-Language Synthesis Summary */}
      {explainData.summary && (
        <div className="p-3 rounded-lg bg-slate-50 ring-1 ring-slate-200 text-xs text-slate-700 leading-relaxed border-l-3 border-slate-700">
          {explainData.summary}
        </div>
      )}

      {/* Chart 1: TreeSHAP Contributions */}
      {shapData.length > 0 ? (
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center justify-between text-[11px] text-slate-500">
            <span className="font-semibold text-slate-700">SHAP Feature Contributions (Log-Odds Impact)</span>
            <div className="flex items-center gap-3 text-[10px]">
              <span className="flex items-center gap-1 font-medium text-slate-600">
                <span className="w-2 h-2 rounded-full bg-rose-500 inline-block" /> Raises Risk
              </span>
              <span className="flex items-center gap-1 font-medium text-slate-600">
                <span className="w-2 h-2 rounded-full bg-emerald-600 inline-block" /> Lowers Risk
              </span>
            </div>
          </div>

          <div className="w-full h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                layout="vertical"
                data={shapData}
                margin={{ top: 5, right: 20, left: 20, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis
                  type="number"
                  tick={{ fill: "#64748b", fontSize: 10 }}
                  axisLine={{ stroke: "#cbd5e1" }}
                />
                <YAxis
                  type="category"
                  dataKey="human_label"
                  width={140}
                  tick={{ fill: "#475569", fontSize: 9 }}
                  axisLine={{ stroke: "#cbd5e1" }}
                />
                <ReferenceLine x={0} stroke="#cbd5e1" strokeWidth={1} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const d = payload[0].payload;
                      const isRisk = d.direction === "raises_risk";
                      return (
                        <div className="rounded-lg bg-white ring-1 ring-slate-200 p-2.5 text-xs shadow-md space-y-1 text-slate-800">
                          <div className="font-semibold text-slate-900">{d.human_label}</div>
                          <div className="text-[11px] text-slate-600">
                            Actual Today: <strong className="text-slate-900 font-mono">{d.value}</strong>
                          </div>
                          <div
                            className={`text-[11px] font-semibold ${
                              isRisk ? "text-rose-700" : "text-emerald-700"
                            }`}
                          >
                            SHAP Impact: {d.contribution > 0 ? `+${d.contribution}` : d.contribution} (
                            {isRisk ? "Raises Risk" : "Lowers Risk"})
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar dataKey="contribution" radius={[2, 2, 2, 2]}>
                  {shapData.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={entry.direction === "raises_risk" ? "#e11d48" : "#16a34a"}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : (
        <div className="text-center py-4 text-xs text-slate-400 italic">
          SHAP attributions available once model artifact is fitted.
        </div>
      )}

      {/* Chart 2: Today vs 7-Day Baseline */}
      {baselineData.length > 0 && (
        <div className="space-y-1.5 pt-3 border-t border-slate-100">
          <div className="flex items-center justify-between text-[11px] text-slate-500">
            <span className="font-semibold text-slate-700">Today vs Trailing 7-Day Baseline (&plusmn;1&sigma;)</span>
            <div className="flex items-center gap-3 text-[10px]">
              <span className="flex items-center gap-1 font-medium text-slate-600">
                <span className="w-2 h-2 rounded-full bg-blue-600 inline-block" /> Today
              </span>
              <span className="flex items-center gap-1 font-medium text-slate-600">
                <span className="w-2 h-2 rounded-full bg-slate-400 inline-block" /> 7-Day Mean
              </span>
            </div>
          </div>

          <div className="w-full h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={baselineData}
                margin={{ top: 10, right: 15, left: 0, bottom: 20 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                <XAxis
                  dataKey="human_label"
                  tick={{ fill: "#64748b", fontSize: 9 }}
                  interval={0}
                  angle={-15}
                  textAnchor="end"
                  axisLine={{ stroke: "#cbd5e1" }}
                />
                <YAxis tick={{ fill: "#64748b", fontSize: 10 }} axisLine={{ stroke: "#cbd5e1" }} />
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload.length) {
                      const d = payload[0].payload;
                      return (
                        <div className="rounded-lg bg-white ring-1 ring-slate-200 p-2.5 text-xs shadow-md space-y-1 text-slate-800">
                          <div className="font-semibold text-slate-900">{d.human_label}</div>
                          <div className="text-[11px] text-slate-700">
                            Today: <strong className="text-slate-900 font-mono">{d.today_value}</strong>
                          </div>
                          <div className="text-[11px] text-slate-600">
                            7-Day Baseline: <strong className="text-slate-800 font-mono">{d.mean} &plusmn; {d.std}</strong>
                          </div>
                          <div className="text-[11px] text-amber-700 font-mono">
                            Deviation z-score: <strong>{d.z_score > 0 ? `+${d.z_score}` : d.z_score}&sigma;</strong>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Bar dataKey="today_value" fill="#2563eb" radius={[2, 2, 0, 0]} name="Today" />
                <Bar dataKey="mean" fill="#94a3b8" radius={[2, 2, 0, 0]} name="7-Day Mean">
                  <ErrorBar dataKey="errorY" width={4} strokeWidth={1.5} stroke="#64748b" />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </div>
  );
}
