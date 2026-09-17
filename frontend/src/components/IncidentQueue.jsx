import { motion, AnimatePresence } from "framer-motion";
import TierBadge from "./TierBadge.jsx";

export default function IncidentQueue({ alerts, onSelect }) {
  return (
    <div className="rounded-xl bg-slate-900/60 ring-1 ring-slate-800 overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-800 text-sm font-medium text-slate-300">
        Incident Timeline — AI Investigation Agent
      </div>
      <div className="max-h-[520px] overflow-y-auto divide-y divide-slate-800/60">
        <AnimatePresence>
          {alerts.map((a) => (
            <motion.div
              key={a.id}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              onClick={() => onSelect(a.employee_id)}
              className="px-5 py-3 hover:bg-slate-800/40 cursor-pointer transition-colors"
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="font-medium text-slate-200 text-sm">{a.employee_id}</span>
                  <span className="text-xs text-slate-500">{a.date}</span>
                </div>
                <div className="flex items-center gap-2">
                  <TierBadge tier={a.risk_tier} />
                  <span className="text-xs text-slate-400 w-9 text-right">{a.risk_score}</span>
                </div>
              </div>
              <p className="mt-1.5 text-xs text-slate-400 leading-relaxed">{a.explanation}</p>
              <div className="mt-1.5 flex gap-1.5 flex-wrap">
                {a.rule_flags.map((f) => (
                  <span key={f} className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400">
                    {f}
                  </span>
                ))}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {alerts.length === 0 && (
          <div className="px-5 py-8 text-center text-slate-500 text-sm">No High/Critical alerts.</div>
        )}
      </div>
    </div>
  );
}
