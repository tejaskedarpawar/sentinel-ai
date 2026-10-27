const TIER_STYLES = {
  Low: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  Medium: "bg-yellow-50 text-yellow-800 ring-yellow-200",
  High: "bg-amber-50 text-amber-800 ring-amber-200",
  Critical: "bg-rose-50 text-rose-700 ring-rose-200",
};

export default function TierBadge({ tier }) {
  const style = TIER_STYLES[tier] || TIER_STYLES.Low;
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ring-1 ${style}`}>
      {tier}
    </span>
  );
}
