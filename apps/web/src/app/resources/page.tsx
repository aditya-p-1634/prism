"use client";

import React, { useState, useEffect } from "react";
import { getDestinations } from "@/lib/api";
import { useSnapshot } from "@/lib/snapshot-context";
import {
  Building2,
  Droplets,
  HeartPulse,
  Utensils,
  ShieldCheck,
  AlertTriangle,
  Zap,
  Info,
  Layers,
  ArrowRight
} from "lucide-react";

export default function ResourcesPage() {
  const { snapshotId, isBaseline } = useSnapshot();
  const [destinations, setDestinations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchDestinations = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await getDestinations(snapshotId);
        setDestinations(res.data || []);
      } catch (err: any) {
        setError(err.message || "Failed to load destination capacity data");
      } finally {
        setLoading(false);
      }
    };
    fetchDestinations();
  }, [snapshotId]);

  if (loading && destinations.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] space-y-3">
        <div className="w-10 h-10 border-4 border-amber-500 border-t-transparent rounded-full animate-spin" />
        <div className="text-slate-400 font-mono text-xs">
          ANALYZING DYNAMIC CARRYING CAPACITIES (E3)...
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 flex-1 max-w-[1700px] mx-auto w-full">
      {/* Top Header */}
      <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-amber-950/80 border border-amber-800/60 flex items-center justify-center">
            <Building2 className="w-5 h-5 text-amber-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">
              Destination & Dynamic Carrying Capacity Workspace (Engine 3)
            </h1>
            <div className="text-xs text-slate-400 font-mono">
              Multi-Resource Bottleneck Identification & Safe Shelters | Snapshot:{" "}
              <span className="text-amber-400 font-semibold">{snapshotId}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300">
            Active Candidates: <span className="text-emerald-400 font-bold">{destinations.length} Facilities</span>
          </span>
        </div>
      </div>

      {/* Bottleneck Logic Explanation Banner */}
      <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 flex items-start space-x-3 text-xs">
        <Info className="w-5 h-5 text-cyan-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-slate-200">
            THE WEAKEST LINK (LEIBIG&apos;S LAW) PRINCIPLE
          </span>
          <p className="text-slate-400 leading-relaxed font-sans">
            Effective carrying capacity is strictly bounded by the minimum supportable population across all critical life-support resources (Shelter Floor, Water Rations, Healthcare Support, Food Supply). A facility with 120 bed spaces but only 45 person-days of potable water has an <strong>Effective Capacity of 45</strong>.
          </p>
        </div>
      </div>

      {/* Destinations Cards List */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {destinations.map((d) => {
          const cap = d.capacity_state || {};
          const eff = cap.effective_capacity || 0;
          const occ = cap.occupied_capacity || 0;
          const rem = cap.remaining_capacity || 0;
          const bottleneck = cap.bottleneck_resource || "NONE";
          const isSafe = cap.is_safe ?? true;
          const utilizationPct = eff > 0 ? Math.round((occ / eff) * 100) : 0;

          return (
            <div
              key={d.id}
              className="p-5 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl flex flex-col justify-between space-y-4"
            >
              <div className="space-y-3">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center space-x-2">
                      <span className="text-sm font-bold text-white">{d.name}</span>
                    </div>
                    <div className="text-xs font-mono text-slate-400 mt-0.5">
                      Code: {d.code} | Type: {d.facility_type}
                    </div>
                  </div>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded-full font-semibold ${
                      isSafe
                        ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                        : "bg-rose-950 text-rose-300 border border-rose-800"
                    }`}
                  >
                    {isSafe ? "SAFE / VERIFIED" : "UNSAFE / FLOODED"}
                  </span>
                </div>

                {/* Capacity Gauges */}
                <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2 font-mono text-xs">
                  <div className="flex justify-between items-baseline">
                    <span className="text-slate-400">Effective Capacity:</span>
                    <span className="text-lg font-bold text-white">{eff} persons</span>
                  </div>
                  <div className="flex justify-between text-slate-400 text-[11px]">
                    <span>Occupied / Assigned:</span>
                    <span className="text-emerald-400 font-semibold">{occ} persons</span>
                  </div>
                  <div className="flex justify-between text-slate-400 text-[11px]">
                    <span>Remaining Headroom:</span>
                    <span className="text-cyan-400 font-semibold">{rem} persons</span>
                  </div>

                  <div className="pt-2">
                    <div className="h-2 rounded-full bg-slate-800 overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all ${
                          utilizationPct > 85
                            ? "bg-rose-500"
                            : utilizationPct > 50
                            ? "bg-amber-500"
                            : "bg-emerald-500"
                        }`}
                        style={{ width: `${utilizationPct}%` }}
                      />
                    </div>
                    <div className="mt-1 text-right text-[10px] text-slate-400">
                      Utilization: {utilizationPct}%
                    </div>
                  </div>
                </div>

                {/* Limiting Bottleneck Highlight */}
                <div className="p-3 rounded-xl bg-amber-950/20 border border-amber-800/40 text-xs font-mono flex items-center justify-between">
                  <span className="text-amber-300 font-semibold">Active Limiting Resource:</span>
                  <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-300 font-bold border border-amber-800/60">
                    {bottleneck}
                  </span>
                </div>

                {/* Resources Breakdown Table */}
                <div className="space-y-1.5 pt-1">
                  <span className="text-[11px] font-mono font-semibold text-slate-400">
                    INVENTORY & SUPPORTABLE POPULATION:
                  </span>
                  <div className="space-y-1 font-mono text-xs">
                    {d.resources?.map((r: any) => {
                      const isBottleneck = r.resource_type === bottleneck;
                      return (
                        <div
                          key={r.id}
                          className={`p-2 rounded-lg border flex items-center justify-between ${
                            isBottleneck
                              ? "bg-amber-950/30 border-amber-700/60 text-amber-200"
                              : "bg-slate-900/50 border-slate-800 text-slate-300"
                          }`}
                        >
                          <div className="flex items-center space-x-1.5">
                            {r.resource_type === "WATER" && <Droplets className="w-3.5 h-3.5 text-blue-400" />}
                            {r.resource_type === "SHELTER" && <Building2 className="w-3.5 h-3.5 text-indigo-400" />}
                            {r.resource_type === "HEALTHCARE" && <HeartPulse className="w-3.5 h-3.5 text-rose-400" />}
                            {r.resource_type === "FOOD" && <Utensils className="w-3.5 h-3.5 text-amber-400" />}
                            <span>{r.resource_type}</span>
                          </div>
                          <div className="text-right">
                            <span className="font-bold">{r.supportable_population}</span>
                            <span className="text-[10px] text-slate-400 ml-1">people</span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              <div className="pt-2 border-t border-slate-800/80 text-[11px] font-mono text-slate-400 flex justify-between items-center">
                <span>Suitability Score:</span>
                <span className="text-emerald-400 font-bold">{d.suitability_score}/100</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
