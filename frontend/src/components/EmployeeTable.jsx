import TierBadge from "./TierBadge.jsx";

export default function EmployeeTable({ employees, selectedId, onSelect }) {
  return (
    <div className="rounded-xl bg-slate-900/60 ring-1 ring-slate-800 overflow-hidden">
      <div className="px-5 py-3 border-b border-slate-800 text-sm font-medium text-slate-300">
        Employees by Peak Risk
      </div>
      <div className="max-h-[520px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="text-xs uppercase text-slate-500 sticky top-0 bg-slate-900">
            <tr>
              <th className="text-left px-5 py-2 font-medium">Employee</th>
              <th className="text-left px-5 py-2 font-medium">Dept</th>
              <th className="text-left px-5 py-2 font-medium">Latest</th>
              <th className="text-left px-5 py-2 font-medium">Peak</th>
            </tr>
          </thead>
          <tbody>
            {employees.map((emp) => (
              <tr
                key={emp.id}
                onClick={() => onSelect(emp.id)}
                className={`cursor-pointer border-t border-slate-800/60 hover:bg-slate-800/40 transition-colors ${
                  selectedId === emp.id ? "bg-slate-800/60" : ""
                }`}
              >
                <td className="px-5 py-2.5 text-slate-200 font-medium">
                  {emp.id}
                  <span className="block text-xs text-slate-500 font-normal">{emp.name}</span>
                </td>
                <td className="px-5 py-2.5 text-slate-400">{emp.department}</td>
                <td className="px-5 py-2.5">
                  <TierBadge tier={emp.latest_risk_tier} />
                </td>
                <td className="px-5 py-2.5">
                  <div className="flex items-center gap-2">
                    <TierBadge tier={emp.peak_risk_tier} />
                    <span className="text-slate-400 text-xs">{emp.peak_risk_score}</span>
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
