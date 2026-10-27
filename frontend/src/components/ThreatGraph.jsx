import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";

const TIER_COLORS = { Low: "#94a3b8", Medium: "#d97706", High: "#ea580c", Critical: "#e11d48" };

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
            "background-color": "#2563eb",
            label: "data(label)",
            color: "#1e293b",
            "font-size": "9px",
            "font-weight": "600",
            width: 24,
            height: 24,
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
            color: "#475569",
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
            width: "mapData(weight, 0, 1000, 1, 5)",
            "line-color": (ele) => TIER_COLORS[ele.data("risk_tier")] || "#94a3b8",
            "target-arrow-color": (ele) => TIER_COLORS[ele.data("risk_tier")] || "#94a3b8",
            "target-arrow-shape": "triangle",
            "curve-style": "bezier",
            opacity: 0.8,
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
    <div className="rounded-xl bg-white ring-1 ring-slate-200/90 shadow-xs p-5">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-semibold text-slate-800">
          Threat Graph &mdash; Employee &rarr; Destination
        </div>
        <div className="flex gap-3 text-[10px] text-slate-500 font-medium">
          {Object.entries(TIER_COLORS).map(([tier, color]) => (
            <span key={tier} className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full inline-block" style={{ background: color }} />
              {tier}
            </span>
          ))}
        </div>
      </div>
      <div ref={containerRef} className="w-full h-[420px] bg-slate-50/50 rounded-lg" />
    </div>
  );
}
