import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded-lg bg-white ring-1 ring-slate-200 px-3 py-2 text-xs text-slate-800 shadow-md">
      <div className="font-semibold text-slate-900">{label}</div>
      <div className="text-slate-700">Risk score: <span className="font-mono font-bold text-slate-900">{point.risk_score}</span></div>
      <div className="text-slate-500">{point.risk_tier}</div>
      {point.rule_flags?.length > 0 && (
        <div className="mt-1 text-slate-500 font-mono text-[10px]">{point.rule_flags.join(", ")}</div>
      )}
    </div>
  );
}

export default function RiskTimelineChart({ timeline, employeeId }) {
  if (!timeline || timeline.length === 0) {
    return (
      <div className="rounded-xl bg-white ring-1 ring-slate-200 p-8 text-center text-slate-400 text-sm shadow-xs">
        Select an employee to view their risk timeline.
      </div>
    );
  }

  const data = timeline.map((t) => ({ ...t, dateShort: t.date.slice(5) }));

  return (
    <div className="rounded-xl bg-white ring-1 ring-slate-200/90 p-5 shadow-xs">
      <div className="text-sm font-semibold text-slate-800 mb-3">
        Risk Score Timeline &mdash; <span className="font-mono text-slate-900">{employeeId}</span>
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
          <XAxis dataKey="dateShort" stroke="#94a3b8" fontSize={11} />
          <YAxis stroke="#94a3b8" fontSize={11} domain={[0, 100]} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={85} stroke="#f43f5e" strokeDasharray="4 4" strokeOpacity={0.6} />
          <ReferenceLine y={60} stroke="#f59e0b" strokeDasharray="4 4" strokeOpacity={0.6} />
          <Line
            type="monotone"
            dataKey="risk_score"
            stroke="#2563eb"
            strokeWidth={2}
            dot={{ r: 2, fill: "#2563eb" }}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
