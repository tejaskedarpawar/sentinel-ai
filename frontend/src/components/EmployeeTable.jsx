import TierBadge from "./TierBadge.jsx";

export default function EmployeeTable({ employees, selectedId, onSelect }) {
  return (
    <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-100 text-sm font-semibold text-slate-800">
        Employees by Peak Risk
      </div>
      <div className="max-h-[520px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="text-[11px] font-semibold uppercase text-slate-500 sticky top-0 bg-slate-50/90 backdrop-blur-xs border-b border-slate-200">
            <tr>
              <th className="text-left px-5 py-2.5">Employee</th>
              <th className="text-left px-5 py-2.5">Dept</th>
              <th className="text-left px-5 py-2.5">Latest</th>
              <th className="text-left px-5 py-2.5">Peak</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {employees.map((emp) => (
              <tr
                key={emp.id}
                onClick={() => onSelect(emp.id)}
                className={`cursor-pointer transition-colors ${
                  selectedId === emp.id
                    ? "bg-slate-100/90 text-slate-900 font-medium"
                    : "hover:bg-slate-50 text-slate-700"
                }`}
              >
                <td className="px-5 py-2.5 text-slate-900 font-medium">
                  {emp.id}
                  <span className="block text-xs text-slate-500 font-normal">{emp.name}</span>
                </td>
                <td className="px-5 py-2.5 text-slate-600">{emp.department}</td>
                <td className="px-5 py-2.5">
                  <TierBadge tier={emp.latest_risk_tier} />
                </td>
                <td className="px-5 py-2.5">
                  <div className="flex items-center gap-2">
                    <TierBadge tier={emp.peak_risk_tier} />
                    <span className="text-slate-500 font-mono text-xs">{emp.peak_risk_score}</span>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
