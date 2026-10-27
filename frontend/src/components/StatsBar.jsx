import { motion } from "framer-motion";

function StatCard({ label, value, accent }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex-1 min-w-[140px] rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs px-5 py-4"
    >
      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">{label}</div>
      <div className={`mt-1.5 text-2xl font-bold font-mono ${accent || "text-slate-900"}`}>{value}</div>
    </motion.div>
  );
}

export default function StatsBar({ stats }) {
  if (!stats) return null;
  const { total_employee_days, employees_monitored, by_tier } = stats;

  return (
    <div className="flex flex-wrap gap-3">
      <StatCard label="Employees Monitored" value={employees_monitored} />
      <StatCard label="Employee-Days Analysed" value={total_employee_days} />
      <StatCard label="Critical" value={by_tier?.Critical ?? 0} accent="text-rose-600" />
      <StatCard label="High" value={by_tier?.High ?? 0} accent="text-amber-600" />
      <StatCard label="Medium" value={by_tier?.Medium ?? 0} accent="text-yellow-600" />
      <StatCard label="Low" value={by_tier?.Low ?? 0} accent="text-emerald-600" />
    </div>
  );
}
