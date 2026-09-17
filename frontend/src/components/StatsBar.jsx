import { motion } from "framer-motion";

function StatCard({ label, value, accent }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex-1 min-w-[140px] rounded-xl bg-slate-900/60 ring-1 ring-slate-800 px-5 py-4"
    >
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`mt-1 text-2xl font-semibold ${accent || "text-slate-100"}`}>{value}</div>
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
      <StatCard label="Critical" value={by_tier?.Critical ?? 0} accent="text-red-400" />
      <StatCard label="High" value={by_tier?.High ?? 0} accent="text-orange-400" />
      <StatCard label="Medium" value={by_tier?.Medium ?? 0} accent="text-yellow-400" />
      <StatCard label="Low" value={by_tier?.Low ?? 0} accent="text-emerald-400" />
    </div>
  );
}
