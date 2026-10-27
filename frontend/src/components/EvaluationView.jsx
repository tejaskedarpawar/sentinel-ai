import { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import { api } from "../api.js";

function CurveTooltip({ active, payload, labelType }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded-lg bg-white ring-1 ring-slate-200 px-3 py-2 text-xs text-slate-800 shadow-md">
      {labelType === "roc" ? (
        <>
          <div className="text-slate-900 font-semibold mb-1">ROC Point</div>
          <div>FPR: <span className="font-mono text-slate-600">{(point.fpr * 100).toFixed(1)}%</span></div>
          <div>TPR (Recall): <span className="font-mono font-medium text-emerald-700">{(point.tpr * 100).toFixed(1)}%</span></div>
        </>
      ) : (
        <>
          <div className="text-slate-900 font-semibold mb-1">PR Point</div>
          <div>Recall: <span className="font-mono text-slate-600">{(point.recall * 100).toFixed(1)}%</span></div>
          <div>Precision: <span className="font-mono font-medium text-indigo-700">{(point.precision * 100).toFixed(1)}%</span></div>
        </>
      )}
    </div>
  );
}

export default function EvaluationView() {
  const [latestRun, setLatestRun] = useState(null);
  const [runs, setRuns] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchRuns = async () => {
    try {
      setLoading(true);
      const [latest, allRuns] = await Promise.all([
        api.evaluationLatest().catch(() => null),
        api.evaluationRuns().catch(() => []),
      ]);
      setLatestRun(latest);
      setRuns(allRuns);
      if (latest) {
        setSelectedRunId(latest.id);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRuns();
  }, []);

  if (loading && !latestRun) {
    return (
      <div className="flex items-center justify-center py-24 text-slate-500 text-sm">
        <div className="w-5 h-5 border-2 border-slate-600 border-t-transparent rounded-full animate-spin mr-3" />
        Loading benchmark evaluation results...
      </div>
    );
  }

  if (error || !latestRun) {
    return (
      <div className="rounded-xl bg-white ring-1 ring-slate-200 p-8 text-center shadow-xs">
        <div className="text-amber-700 font-medium mb-2">No Evaluation Runs Found</div>
        <p className="text-slate-500 text-sm max-w-md mx-auto mb-4">
          {error || "Run the evaluation benchmark CLI to generate benchmark performance results:"}
        </p>
        <code className="inline-block bg-slate-100 px-3 py-1.5 rounded text-xs font-mono text-slate-800 ring-1 ring-slate-200">
          python -m app.evaluation --dataset cert --path data/cert_r4.2 --users 100
        </code>
      </div>
    );
  }

  const currentRun = latestRun;
  const config = currentRun.config || {};
  const metrics = currentRun.metrics || {};
  const models = metrics.models || {};
  const ensemble = models["Sentinel AI Ensemble"] || {};
  const confusion = metrics.confusion_matrix || { tp: 0, fp: 0, tn: 0, fn: 0, threshold: 70.0 };
  const curves = currentRun.curves || { roc: [], pr: [] };

  const totalEvaluated = confusion.tp + confusion.fp + confusion.tn + confusion.fn;
  const accuracy = totalEvaluated > 0 ? (((confusion.tp + confusion.tn) / totalEvaluated) * 100).toFixed(1) : 0;
  const specificity = (confusion.tn + confusion.fp) > 0 ? ((confusion.tn / (confusion.tn + confusion.fp)) * 100).toFixed(1) : 0;

  return (
    <div className="space-y-6">
      {/* Top Banner & Run Selector */}
      <div className="flex items-center justify-between flex-wrap gap-4 bg-white ring-1 ring-slate-200/90 rounded-xl p-5 shadow-xs">
        <div>
          <div className="flex items-center gap-3 mb-1.5 flex-wrap">
            <h2 className="text-base font-semibold text-slate-900">
              Model Evaluation &amp; Benchmark Report
            </h2>
            <span className="inline-flex items-center gap-1.5 px-3 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-800 ring-1 ring-emerald-200">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
              CERT r4.2 subset: {currentRun.n_users} users, 5 malicious
            </span>
            <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-mono bg-slate-100 text-slate-700 ring-1 ring-slate-200">
              Zero Test Leakage (Time-Split)
            </span>
          </div>
          <p className="text-xs text-slate-500">
            Strict chronological split &bull; Train: {config.train_start || "Start"} &rarr; {config.train_end || "Mid"} ({config.train_days} days) &bull; Test: {config.test_start || "Mid"} &rarr; {config.test_end || "End"} ({config.test_days} days)
          </p>
        </div>

        <div className="flex items-center gap-2">
          {runs.length > 1 && (
            <div className="flex items-center gap-1.5 text-xs text-slate-600 bg-slate-50 px-2 py-1 rounded-lg ring-1 ring-slate-200">
              <span className="font-medium text-slate-500">Runs:</span>
              {runs.map((r) => (
                <span
                  key={r.id}
                  className={`px-2 py-0.5 rounded text-[11px] font-mono ${
                    r.id === currentRun.id
                      ? "bg-white text-slate-900 ring-1 ring-slate-300 font-bold shadow-2xs"
                      : "text-slate-500"
                  }`}
                >
                  #{r.id} ({r.n_users}u)
                </span>
              ))}
            </div>
          )}
          <button
            onClick={fetchRuns}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-white hover:bg-slate-50 text-slate-700 ring-1 ring-slate-300 shadow-2xs transition-colors cursor-pointer"
          >
            Refresh
          </button>
        </div>
      </div>

      {/* KPI Stat Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <div className="bg-white ring-1 ring-slate-200/90 rounded-xl p-4 shadow-xs">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">ROC-AUC</div>
          <div className="text-2xl font-bold font-mono text-slate-900 mt-1">
            {ensemble.roc_auc != null ? ensemble.roc_auc.toFixed(4) : "—"}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Ensemble discrimination</div>
        </div>

        <div className="bg-white ring-1 ring-slate-200/90 rounded-xl p-4 shadow-xs">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">PR-AUC</div>
          <div className="text-2xl font-bold font-mono text-slate-900 mt-1">
            {ensemble.pr_auc != null ? ensemble.pr_auc.toFixed(4) : "—"}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Imbalanced precision-recall</div>
        </div>

        <div className="bg-white ring-1 ring-slate-200/90 rounded-xl p-4 shadow-xs">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Precision (High)</div>
          <div className="text-2xl font-bold font-mono text-emerald-700 mt-1">
            {ensemble.precision != null ? `${(ensemble.precision * 100).toFixed(1)}%` : "—"}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Score &ge; 70 fidelity</div>
        </div>

        <div className="bg-white ring-1 ring-slate-200/90 rounded-xl p-4 shadow-xs">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Recall (High)</div>
          <div className="text-2xl font-bold font-mono text-amber-700 mt-1">
            {ensemble.recall != null ? `${(ensemble.recall * 100).toFixed(1)}%` : "—"}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Threat-days captured</div>
        </div>

        <div className="bg-white ring-1 ring-slate-200/90 rounded-xl p-4 shadow-xs">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Alert Rate</div>
          <div className="text-2xl font-bold font-mono text-slate-800 mt-1">
            {metrics.alerts_per_analyst_day != null ? metrics.alerts_per_analyst_day : "—"}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Alerts / analyst-day</div>
        </div>

        <div className="bg-white ring-1 ring-slate-200/90 rounded-xl p-4 shadow-xs">
          <div className="text-[11px] uppercase tracking-wider text-slate-500 font-semibold">Mean MTTD</div>
          <div className="text-2xl font-bold font-mono text-rose-700 mt-1">
            {metrics.mean_days_to_detection != null ? `${metrics.mean_days_to_detection}d` : "—"}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Days to first detection</div>
        </div>
      </div>

      {/* Curves Section: ROC and PR Curves */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* ROC Curve */}
        <div className="bg-white ring-1 ring-slate-200/90 rounded-xl p-5 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-sm font-semibold text-slate-800">ROC Curve (Receiver Operating Characteristic)</div>
              <div className="text-[11px] text-slate-500">True Positive Rate vs False Positive Rate (AUC: {ensemble.roc_auc})</div>
            </div>
            <span className="text-xs font-mono text-slate-700 font-semibold bg-slate-100 px-2.5 py-0.5 rounded ring-1 ring-slate-200">
              AUC {ensemble.roc_auc}
            </span>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={curves.roc} margin={{ top: 10, right: 20, left: -10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis
                  dataKey="fpr"
                  stroke="#94a3b8"
                  fontSize={11}
                  domain={[0, 1]}
                  type="number"
                  tickFormatter={(v) => v.toFixed(1)}
                  label={{ value: "False Positive Rate (FPR)", position: "insideBottom", offset: -5, fill: "#64748b", fontSize: 10 }}
                />
                <YAxis
                  dataKey="tpr"
                  stroke="#94a3b8"
                  fontSize={11}
                  domain={[0, 1]}
                  type="number"
                  tickFormatter={(v) => v.toFixed(1)}
                  label={{ value: "True Positive Rate (TPR)", angle: -90, position: "insideLeft", offset: 15, fill: "#64748b", fontSize: 10 }}
                />
                <Tooltip content={<CurveTooltip labelType="roc" />} />
                <ReferenceLine
                  stroke="#cbd5e1"
                  strokeDasharray="4 4"
                  segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]}
                />
                <Line
                  type="monotone"
                  dataKey="tpr"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={{ r: 2, fill: "#2563eb" }}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* PR Curve */}
        <div className="bg-white ring-1 ring-slate-200/90 rounded-xl p-5 shadow-xs">
          <div className="flex items-center justify-between mb-3">
            <div>
              <div className="text-sm font-semibold text-slate-800">Precision-Recall Curve</div>
              <div className="text-[11px] text-slate-500">Precision vs Recall across risk score thresholds (PR-AUC: {ensemble.pr_auc})</div>
            </div>
            <span className="text-xs font-mono text-slate-700 font-semibold bg-slate-100 px-2.5 py-0.5 rounded ring-1 ring-slate-200">
              PR-AUC {ensemble.pr_auc}
            </span>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={curves.pr} margin={{ top: 10, right: 20, left: -10, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis
                  dataKey="recall"
                  stroke="#94a3b8"
                  fontSize={11}
                  domain={[0, 1]}
                  type="number"
                  tickFormatter={(v) => v.toFixed(1)}
                  label={{ value: "Recall", position: "insideBottom", offset: -5, fill: "#64748b", fontSize: 10 }}
                />
                <YAxis
                  dataKey="precision"
                  stroke="#94a3b8"
                  fontSize={11}
                  domain={[0, 1.05]}
                  type="number"
                  tickFormatter={(v) => v.toFixed(1)}
                  label={{ value: "Precision", angle: -90, position: "insideLeft", offset: 15, fill: "#64748b", fontSize: 10 }}
                />
                <Tooltip content={<CurveTooltip labelType="pr" />} />
                <Line
                  type="monotone"
                  dataKey="precision"
                  stroke="#7c3aed"
                  strokeWidth={2}
                  dot={{ r: 2, fill: "#7c3aed" }}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Model Comparison Table */}
      <div className="bg-white ring-1 ring-slate-200/90 rounded-xl p-5 shadow-xs overflow-hidden">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <div>
            <div className="text-sm font-semibold text-slate-900">Model Performance Comparison (Test Period)</div>
            <div className="text-[11px] text-slate-500">
              Evaluated strictly on held-out post-split time period. Unbiased comparison against individual models &amp; naive baseline.
            </div>
          </div>
          <span className="text-xs text-slate-500 font-mono">
            {metrics.test_records_count || 0} user-days ({metrics.test_positives_count || 0} positive, {metrics.test_negatives_count || 0} negative)
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-xs text-left">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50/70 text-slate-500 font-semibold">
                <th className="py-2.5 px-3">Model Architecture</th>
                <th className="py-2.5 px-3 text-right">ROC-AUC</th>
                <th className="py-2.5 px-3 text-right">PR-AUC</th>
                <th className="py-2.5 px-3 text-right">Precision</th>
                <th className="py-2.5 px-3 text-right">Recall</th>
                <th className="py-2.5 px-3 text-right">F1-Score</th>
                <th className="py-2.5 px-3 text-right">Precision@10</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 font-mono">
              {Object.entries(models).map(([name, m]) => {
                const isEnsemble = name.includes("Ensemble");
                return (
                  <tr
                    key={name}
                    className={`transition-colors ${
                      isEnsemble
                        ? "bg-slate-50 text-slate-900 font-semibold"
                        : "hover:bg-slate-50/60 text-slate-700"
                    }`}
                  >
                    <td className="py-3 px-3 font-sans flex items-center gap-2">
                      {isEnsemble && (
                        <span className="text-amber-500">★</span>
                      )}
                      <span className={isEnsemble ? "font-semibold text-slate-900" : ""}>{name}</span>
                      {isEnsemble && (
                        <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-slate-200 text-slate-700 font-medium">
                          Production
                        </span>
                      )}
                    </td>
                    <td className="py-3 px-3 text-right text-slate-800">{m.roc_auc != null ? m.roc_auc.toFixed(4) : "—"}</td>
                    <td className="py-3 px-3 text-right text-slate-800">{m.pr_auc != null ? m.pr_auc.toFixed(4) : "—"}</td>
                    <td className="py-3 px-3 text-right text-slate-800">{m.precision != null ? m.precision.toFixed(4) : "—"}</td>
                    <td className="py-3 px-3 text-right text-slate-800">{m.recall != null ? m.recall.toFixed(4) : "—"}</td>
                    <td className="py-3 px-3 text-right font-bold text-slate-900">{m.f1 != null ? m.f1.toFixed(4) : "—"}</td>
                    <td className="py-3 px-3 text-right text-slate-700">{m.precision_at_10 != null ? m.precision_at_10.toFixed(4) : "—"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Confusion Matrix & Limitations Note */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Confusion Matrix Card */}
        <div className="bg-white ring-1 ring-slate-200/90 rounded-xl p-5 shadow-xs">
          <div className="text-sm font-semibold text-slate-900 mb-1">
            Confusion Matrix
          </div>
          <div className="text-[11px] text-slate-500 mb-4">
            Production High-Tier Threshold (Score &ge; {confusion.threshold})
          </div>

          <div className="grid grid-cols-2 gap-2 text-center font-mono">
            <div className="bg-emerald-50 ring-1 ring-emerald-200 rounded-lg p-3">
              <div className="text-xs text-emerald-800 font-sans font-medium">True Positives</div>
              <div className="text-2xl font-bold text-emerald-900 mt-1">{confusion.tp}</div>
              <div className="text-[10px] text-emerald-700/80 font-sans mt-0.5">Threat days flagged</div>
            </div>

            <div className="bg-rose-50 ring-1 ring-rose-200 rounded-lg p-3">
              <div className="text-xs text-rose-800 font-sans font-medium">False Positives</div>
              <div className="text-2xl font-bold text-rose-900 mt-1">{confusion.fp}</div>
              <div className="text-[10px] text-rose-700/80 font-sans mt-0.5">Benign days alerted</div>
            </div>

            <div className="bg-amber-50 ring-1 ring-amber-200 rounded-lg p-3">
              <div className="text-xs text-amber-800 font-sans font-medium">False Negatives</div>
              <div className="text-2xl font-bold text-amber-900 mt-1">{confusion.fn}</div>
              <div className="text-[10px] text-amber-700/80 font-sans mt-0.5">Threat days missed</div>
            </div>

            <div className="bg-slate-50 ring-1 ring-slate-200 rounded-lg p-3">
              <div className="text-xs text-slate-700 font-sans font-medium">True Negatives</div>
              <div className="text-2xl font-bold text-slate-900 mt-1">{confusion.tn}</div>
              <div className="text-[10px] text-slate-500 font-sans mt-0.5">Normal days passed</div>
            </div>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-100 text-[11px] text-slate-500 flex justify-between">
            <span>Accuracy: <strong className="text-slate-800 font-mono">{accuracy}%</strong></span>
            <span>Specificity: <strong className="text-slate-800 font-mono">{specificity}%</strong></span>
          </div>
        </div>

        {/* Limitations & Methodology Note */}
        <div className="lg:col-span-2 bg-slate-50/70 ring-1 ring-slate-200/90 rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-slate-900 font-semibold text-sm">Methodology &amp; Evaluation Limitations</span>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-white text-slate-600 ring-1 ring-slate-200 font-medium">
                Academic &amp; Operational Context
              </span>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed mb-3">
              The detection engine was evaluated under a strict temporal split where historical days train baseline profiles and all subsequent testing days remain unseen until inference time.
            </p>
            <ul className="text-xs text-slate-600 space-y-2 list-disc list-inside">
              <li>
                <strong className="text-slate-800">Synthetic CERT r4.2 Benchmark:</strong> The CERT dataset uses synthetically injected insider exfiltration scenarios. In real enterprise environments, benign behavioral noise and organizational drift can exhibit higher entropy.
              </li>
              <li>
                <strong className="text-slate-800">Evaluated on User Subset:</strong> To allow rapid, memory-safe, and reproducible continuous evaluation, runs evaluate a sample (e.g. 100 users) containing all ground-truth malicious actors alongside random benign employees.
              </li>
              <li>
                <strong className="text-slate-800">Threshold Generalization:</strong> The production High-tier threshold (score &ge; 70.0) is fixed globally according to SOC triage workload capacity (~1–2 alerts per analyst-day) rather than post-hoc tuning on test data.
              </li>
            </ul>
          </div>

          <div className="mt-4 pt-3 border-t border-slate-200 flex items-center justify-between text-[11px] text-slate-500">
            <span>Privacy Rule: Content columns permanently dropped at load time</span>
            <span className="font-mono text-slate-400">Sentinel AI v0.2.0</span>
          </div>
        </div>
      </div>
    </div>
  );
}
