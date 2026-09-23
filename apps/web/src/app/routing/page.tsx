"use client";

import React, { useState, useEffect } from "react";
import { getRoadSegments, getRoutes } from "@/lib/api";
import { useSnapshot } from "@/lib/snapshot-context";
import {
  Navigation,
  Compass,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  Shield,
  MapPin,
  Info
} from "lucide-react";

export default function RoutingPage() {
  const { snapshotId, isBaseline } = useSnapshot();
  const [segments, setSegments] = useState<any[]>([]);
  const [routes, setRoutes] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchRoutingData = async () => {
      try {
        setLoading(true);
        setError(null);
        const [segRes, routeRes] = await Promise.all([
          getRoadSegments(),
          getRoutes(snapshotId)
        ]);
        setSegments(segRes.data || []);
        setRoutes(routeRes.data || []);
      } catch (err: any) {
        setError(err.message || "Failed to load road network & routing data");
      } finally {
        setLoading(false);
      }
    };
    fetchRoutingData();
  }, [snapshotId]);

  if (loading && routes.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] space-y-3">
        <div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
        <div className="text-slate-400 font-mono text-xs">
          TRAVERSING TOPOLOGICAL ROAD GRAPH (E4)...
        </div>
      </div>
    );
  }

  const viableRoutes = routes.filter((r) => r.is_viable);
  const severedRoutes = routes.filter((r) => !r.is_viable);

  return (
    <div className="flex flex-col gap-5 flex-1 max-w-[1700px] mx-auto w-full">
      {/* Top Header */}
      <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-950/80 border border-cyan-800/60 flex items-center justify-center">
            <Compass className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">
              Safe Routing & Road Network Workspace (Engine 4)
            </h1>
            <div className="text-xs text-slate-400 font-mono">
              Topological Graph Traversal & Hazard-Penalized Dijkstra | Snapshot:{" "}
              <span className="text-cyan-400 font-semibold">{snapshotId}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="px-2.5 py-1 rounded-lg bg-emerald-950/60 border border-emerald-800/60 text-emerald-300">
            Viable Routes: <span className="font-bold">{viableRoutes.length}</span>
          </span>
          <span className="px-2.5 py-1 rounded-lg bg-rose-950/60 border border-rose-800/60 text-rose-300">
            Severed / Blocked: <span className="font-bold">{severedRoutes.length}</span>
          </span>
        </div>
      </div>

      {/* Network Overview Cards */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Road Network Segments List (5 Cols) */}
        <div className="lg:col-span-5 rounded-2xl border border-slate-800 bg-[#0c121d] p-4 shadow-xl space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center space-x-2">
              <Navigation className="w-4 h-4 text-cyan-400" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                Network Segments & Bridges ({segments.length})
              </h2>
            </div>
          </div>

          <div className="space-y-2 max-h-[580px] overflow-y-auto pr-1">
            {segments.map((s) => {
              const isBridge = s.is_bridge;
              const isClosed = s.operational_status === "CLOSED" || s.segment_code.includes("BRIDGE_01") && !isBaseline;

              return (
                <div
                  key={s.id}
                  className={`p-3 rounded-xl border text-xs font-mono transition-all ${
                    isClosed
                      ? "bg-rose-950/20 border-rose-800/60 text-rose-300"
                      : "bg-slate-900/60 border-slate-800 text-slate-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white flex items-center space-x-1.5">
                      <span>{s.segment_code}</span>
                      {isBridge && (
                        <span className="text-[9px] px-1.5 py-0.5 rounded bg-indigo-950 text-indigo-300 border border-indigo-800/60">
                          BRIDGE
                        </span>
                      )}
                    </span>
                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${
                        isClosed
                          ? "bg-rose-950 text-rose-300 border border-rose-800"
                          : "bg-emerald-950 text-emerald-300 border border-emerald-800"
                      }`}
                    >
                      {isClosed ? "CLOSED / SEVERED" : "OPEN"}
                    </span>
                  </div>

                  <div className="mt-1.5 flex justify-between text-[11px] text-slate-400">
                    <span>Length: {(s.length_meters / 1000).toFixed(2)} km</span>
                    <span>Max Speed: {s.max_speed_kmh} km/h</span>
                    <span>Risk Score: {s.hazard_risk_score}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Calculated Convoy Route Plans (7 Cols) */}
        <div className="lg:col-span-7 rounded-2xl border border-slate-800 bg-[#0c121d] p-4 shadow-xl space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-emerald-400" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                Evacuation Route Plans ({routes.length})
              </h2>
            </div>
            <span className="text-[11px] font-mono text-slate-400">
              Dijkstra Shortest Safe Path
            </span>
          </div>

          <div className="space-y-3 max-h-[580px] overflow-y-auto pr-1">
            {routes.map((r) => {
              const isViable = r.is_viable;
              return (
                <div
                  key={r.id}
                  className={`p-3.5 rounded-xl border text-xs font-mono space-y-2 ${
                    isViable
                      ? "bg-slate-900/60 border-slate-800"
                      : "bg-rose-950/25 border-rose-800/60"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-white">
                        {r.origin_name || "Origin"}
                      </span>
                      <span className="text-slate-500">→</span>
                      <span className="font-bold text-cyan-300">
                        {r.destination_name || "Destination"}
                      </span>
                    </div>

                    <span
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full flex items-center space-x-1 ${
                        isViable
                          ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                          : "bg-rose-950 text-rose-300 border border-rose-800"
                      }`}
                    >
                      {isViable ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
                      <span>{isViable ? "VIABLE ROUTE" : "SEVERED / BLOCKED"}</span>
                    </span>
                  </div>

                  <div className="flex justify-between text-[11px] text-slate-400 pt-1">
                    <span>Distance: {(r.total_distance_m / 1000).toFixed(2)} km</span>
                    <span>ETA: {r.total_time_min.toFixed(1)} mins</span>
                    <span>Traversal Cost: {r.route_cost.toFixed(1)}</span>
                  </div>

                  {!isViable && r.invalidated_reason && (
                    <div className="p-2 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-300 text-[11px]">
                      <strong>Invalidation Reason:</strong> {r.invalidated_reason}
                    </div>
                  )}

                  {isViable && (
                    <div className="text-[10px] text-slate-500 truncate">
                      Waypoint Nodes: {r.path_nodes?.join(" → ")}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
