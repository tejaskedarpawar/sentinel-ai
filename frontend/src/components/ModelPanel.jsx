import { useState } from "react";
import { motion } from "framer-motion";

export default function ModelPanel({
  modelStatus,
  feedbackStats,
  onRetrainSuccess,
}) {
  const [loading, setLoading] = useState(false);
  const [retrainResult, setRetrainResult] = useState(null);
  const [error, setError] = useState(null);

  const isSupervised = modelStatus?.mode === "supervised";
  const totalLabels = feedbackStats?.total_labeled || modelStatus?.n_labels || 0;
  const threatCount = feedbackStats?.counts?.threat || 0;
  const fpCount = feedbackStats?.counts?.false_positive || 0;
  const cvMetrics = modelStatus?.cv_metrics;
  const canRetrain = totalLabels >= 20 && threatCount >= 5 && fpCount >= 5;

  const handleRetrain = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await onRetrainSuccess();
      setRetrainResult(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner / Status Overview */}
      <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs p-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-lg font-semibold text-slate-900">
                AI Detection Engine & Retraining
              </h2>
              <span
                className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ring-1 ${
                  isSupervised
                    ? "bg-emerald-50 text-emerald-800 ring-emerald-200"
                    : "bg-amber-50 text-amber-800 ring-amber-200"
                }`}
              >
                {isSupervised ? "Supervised (Human Feedback)" : "Weakly Supervised (Pseudo-Labels)"}
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-500 max-w-2xl leading-relaxed">
              The detection ensemble blends Isolation Forest, deep Autoencoder, and LSTM sequence signals
              with an XGBoost classifier. When analyst labels accumulate, XGBoost is retrained with supervised
              weights to suppress false positives and elevate confirmed insider threat vectors.
            </p>
          </div>

          <div className="flex flex-col items-start sm:items-end gap-2">
            <button
              onClick={handleRetrain}
              disabled={loading || (!canRetrain && !isSupervised)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg text-xs font-medium tracking-wide transition-all ${
                loading
                  ? "bg-slate-200 text-slate-500 cursor-wait"
                  : canRetrain || isSupervised
                  ? "bg-slate-900 hover:bg-slate-800 text-white font-semibold shadow-xs active:scale-95 cursor-pointer"
                  : "bg-slate-100 text-slate-400 cursor-not-allowed"
              }`}
            >
              {loading && (
                <svg className="animate-spin h-3.5 w-3.5 text-current" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
              )}
              {loading ? "Retraining XGBoost..." : "Retrain Model Now"}
            </button>
            {!canRetrain && !isSupervised && (
              <span className="text-[11px] text-amber-700">
                Requires &ge; 20 labels with &ge; 5 threats &amp; 5 false positives (have: {totalLabels})
              </span>
            )}
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 rounded-lg bg-rose-50 ring-1 ring-rose-200 text-xs text-rose-800">
            {error}
          </div>
        )}

        {retrainResult && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 p-4 rounded-lg bg-emerald-50 ring-1 ring-emerald-200 text-xs text-emerald-900 space-y-2"
          >
            <div className="font-semibold text-emerald-800 flex items-center gap-2">
              <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              {retrainResult.message || "Model retrained and risk records re-scored successfully!"}
            </div>
            {retrainResult.rescore && (
              <div className="flex flex-wrap gap-4 text-[11px] text-emerald-800 pt-1 border-t border-emerald-200">
                <span>
                  High/Critical Alerts:{" "}
                  <strong>
                    {retrainResult.rescore.high_critical_before} &rarr; {retrainResult.rescore.high_critical_after}
                  </strong>
                </span>
                <span>
                  Baseline False Positives:{" "}
                  <strong>
                    {retrainResult.rescore.false_positives_before} &rarr;{" "}
                    {retrainResult.rescore.false_positives_after}
                  </strong>{" "}
                  (
                  {retrainResult.rescore.false_positives_before > 0
                    ? `-${Math.round(
                        ((retrainResult.rescore.false_positives_before -
                          retrainResult.rescore.false_positives_after) /
                          retrainResult.rescore.false_positives_before) *
                          100
                      )}% reduction`
                    : "0"}
                  )
                </span>
                <span>Records updated: {retrainResult.rescore.updated}</span>
              </div>
            )}
          </motion.div>
        )}
      </div>

      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Card 1: Labels & Triaged Dataset */}
        <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs p-5 flex flex-col justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Analyst Feedback Labels
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold font-mono text-slate-900">{totalLabels}</span>
              <span className="text-xs text-slate-500">/ 20 min required</span>
            </div>
            <div className="mt-3 w-full bg-slate-100 h-1.5 rounded-full overflow-hidden">
              <div
                className="bg-slate-700 h-full rounded-full transition-all duration-500"
                style={{ width: `${Math.min(100, (totalLabels / 20) * 100)}%` }}
              />
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between text-xs">
            <span className="text-slate-600 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-500 inline-block" />
              Threats: <strong className="text-slate-900">{threatCount}</strong>
            </span>
            <span className="text-slate-600 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-slate-400 inline-block" />
              False Positives: <strong className="text-slate-900">{fpCount}</strong>
            </span>
          </div>
        </div>

        {/* Card 2: Cross Validation Performance */}
        <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs p-5 flex flex-col justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              5-Fold Stratified CV
            </div>
            {cvMetrics ? (
              <div className="mt-2 grid grid-cols-3 gap-2">
                <div>
                  <div className="text-[10px] text-slate-400 uppercase font-medium">ROC-AUC</div>
                  <div className="text-xl font-bold font-mono text-slate-900">
                    {(cvMetrics.roc_auc * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-400 uppercase font-medium">Precision</div>
                  <div className="text-xl font-bold font-mono text-emerald-700">
                    {(cvMetrics.precision * 100).toFixed(1)}%
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-slate-400 uppercase font-medium">Recall</div>
                  <div className="text-xl font-bold font-mono text-amber-700">
                    {(cvMetrics.recall * 100).toFixed(1)}%
                  </div>
                </div>
              </div>
            ) : (
              <div className="mt-3 text-xs text-slate-400 italic">
                Evaluated on labeled analyst rows upon retraining.
              </div>
            )}
          </div>
          <div className="mt-4 pt-4 border-t border-slate-100 text-[11px] text-slate-400">
            {modelStatus?.trained_at
              ? `Last trained: ${new Date(modelStatus.trained_at).toLocaleString()}`
              : "Using initial pseudo-label baseline"}
          </div>
        </div>

        {/* Card 3: Alert Pipeline Impact */}
        <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs p-5 flex flex-col justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              SOC Alert Triage Impact
            </div>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-3xl font-bold font-mono text-emerald-700">
                {feedbackStats?.reviewed_share
                  ? `${(feedbackStats.reviewed_share * 100).toFixed(0)}%`
                  : "0%"}
              </span>
              <span className="text-xs text-slate-500">of high/crit alerts reviewed</span>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              {feedbackStats?.reviewed_alerts || 0} of {feedbackStats?.total_alerts || 0} alerts labeled.
            </p>
          </div>
          <div className="mt-4 pt-4 border-t border-slate-100 flex items-center justify-between text-[11px] text-slate-400">
            <span>Sample Weight: 1.0 (labeled) / 0.2 (unlabeled)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
