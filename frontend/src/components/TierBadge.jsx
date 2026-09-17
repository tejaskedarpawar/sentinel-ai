const TIER_STYLES = {
  Low: "bg-emerald-500/15 text-emerald-400 ring-emerald-500/30",
  Medium: "bg-yellow-500/15 text-yellow-400 ring-yellow-500/30",
  High: "bg-orange-500/15 text-orange-400 ring-orange-500/30",
  Critical: "bg-red-500/15 text-red-400 ring-red-500/30",
};

export default function TierBadge({ tier }) {
  const style = TIER_STYLES[tier] || TIER_STYLES.Low;
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ring-1 ${style}`}>
      {tier}
    </span>
  );
}
