import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const point = payload[0].payload;
  return (
    <div className="rounded-lg bg-slate-800 ring-1 ring-slate-700 px-3 py-2 text-xs text-slate-200 shadow-lg">
      <div className="font-medium">{label}</div>
      <div>Risk score: {point.risk_score}</div>
      <div className="text-slate-400">{point.risk_tier}</div>
      {point.rule_flags?.length > 0 && (
        <div className="mt-1 text-slate-400">{point.rule_flags.join(", ")}</div>
      )}
    </div>
  );
}

export default function RiskTimelineChart({ timeline, employeeId }) {
  if (!timeline || timeline.length === 0) {
    return (
      <div className="rounded-xl bg-slate-900/60 ring-1 ring-slate-800 p-8 text-center text-slate-500 text-sm">
        Select an employee to view their risk timeline.
      </div>
    );
  }

  const data = timeline.map((t) => ({ ...t, dateShort: t.date.slice(5) }));

  return (
    <div className="rounded-xl bg-slate-900/60 ring-1 ring-slate-800 p-5">
      <div className="text-sm font-medium text-slate-300 mb-3">
        Risk Score Timeline — {employeeId}
      </div>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
          <XAxis dataKey="dateShort" stroke="#64748b" fontSize={11} />
          <YAxis stroke="#64748b" fontSize={11} domain={[0, 100]} />
          <Tooltip content={<CustomTooltip />} />
          <ReferenceLine y={85} stroke="#ef4444" strokeDasharray="4 4" strokeOpacity={0.5} />
          <ReferenceLine y={60} stroke="#f97316" strokeDasharray="4 4" strokeOpacity={0.5} />
          <Line
            type="monotone"
            dataKey="risk_score"
            stroke="#38bdf8"
            strokeWidth={2}
            dot={{ r: 2, fill: "#38bdf8" }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
