import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";

const TIER_COLORS = { Low: "#334155", Medium: "#eab308", High: "#f97316", Critical: "#ef4444" };

export default function ThreatGraph({ graph }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !graph) return;

    const elements = [
      ...graph.nodes.map((n) => ({ data: n.data })),
      ...graph.edges.map((e) => ({ data: e.data })),
    ];

    if (cyRef.current) {
      cyRef.current.destroy();
    }

    cyRef.current = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node[type='employee']",
          style: {
            "background-color": "#38bdf8",
            label: "data(label)",
            color: "#e2e8f0",
            "font-size": "9px",
            width: 26,
            height: 26,
            "text-valign": "bottom",
            "text-margin-y": 4,
          },
        },
        {
          selector: "node[type='destination']",
          style: {
            "background-color": "#64748b",
            shape: "diamond",
            label: "data(label)",
            color: "#94a3b8",
            "font-size": "8px",
            width: 18,
            height: 18,
            "text-valign": "bottom",
            "text-margin-y": 4,
          },
        },
        {
          selector: "edge",
          style: {
            width: "mapData(weight, 0, 1000, 1, 6)",
            "line-color": (ele) => TIER_COLORS[ele.data("risk_tier")] || "#334155",
            "target-arrow-color": (ele) => TIER_COLORS[ele.data("risk_tier")] || "#334155",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            opacity: 0.85,
          },
        },
      ],
      layout: { name: "cose", animate: false, padding: 20 },
    });

    return () => {
      if (cyRef.current) cyRef.current.destroy();
    };
  }, [graph]);

  return (
    <div className="rounded-xl bg-slate-900/60 ring-1 ring-slate-800 p-5">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-medium text-slate-300">
          Threat Graph — Employee &rarr; Destination
        </div>
        <div className="flex gap-3 text-[10px] text-slate-400">
          {Object.entries(TIER_COLORS).map(([tier, color]) => (
            <span key={tier} className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full inline-block" style={{ background: color }} />
              {tier}
            </span>
          ))}
        </div>
      </div>
      <div ref={containerRef} className="w-full h-[420px]" />
    </div>
  );
}
