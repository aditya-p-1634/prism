"use client";

import React, { useState, useEffect } from "react";
import { getCurrentHazards, getRedZones } from "@/lib/api";
import { useSnapshot } from "@/lib/snapshot-context";
import {
  AlertTriangle,
  Shield,
  Activity,
  Droplets,
  Thermometer,
  Layers,
  FileCheck,
  Info,
  Scale
} from "lucide-react";

export default function HazardsPage() {
  const { snapshotId, activeSnapshot, isBaseline } = useSnapshot();
  const [hazards, setHazards] = useState<any[]>([]);
  const [redZones, setRedZones] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchHazardData = async () => {
      try {
        setLoading(true);
        setError(null);
        const [hazRes, rzRes] = await Promise.all([
          getCurrentHazards(snapshotId),
          getRedZones(snapshotId)
        ]);
        setHazards(hazRes.data || []);
        setRedZones(rzRes.data || []);
      } catch (err: any) {
        setError(err.message || "Failed to load Hazard Intelligence data");
      } finally {
        setLoading(false);
      }
    };
    fetchHazardData();
  }, [snapshotId]);

  if (loading && hazards.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] space-y-3">
        <div className="w-10 h-10 border-4 border-rose-500 border-t-transparent rounded-full animate-spin" />
        <div className="text-slate-400 font-mono text-xs">
          COMPUTING HAZARD ENVELOPE (E1)...
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5 flex-1 max-w-[1700px] mx-auto w-full">
      {/* Top Header */}
      <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-rose-950/80 border border-rose-800/60 flex items-center justify-center">
            <AlertTriangle className="w-5 h-5 text-rose-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">
              Hazard Intelligence Workspace (Engine 1)
            </h1>
            <div className="text-xs text-slate-400 font-mono">
              Red Zone Delineation & Compound Flood Extent | Snapshot:{" "}
              <span className="text-rose-400 font-semibold">{snapshotId}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300">
            Model Confidence: <span className="text-emerald-400 font-bold">95.0%</span>
          </span>
          <span className="px-2.5 py-1 rounded-lg bg-rose-950/60 border border-rose-800/60 text-rose-300">
            Red Zones: <span className="font-bold">{redZones.length}</span>
          </span>
        </div>
      </div>

      {/* Model Disclaimer Alert Banner */}
      <div className="p-3.5 rounded-xl bg-amber-950/30 border border-amber-800/60 text-xs flex items-start space-x-3">
        <Info className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
        <div className="space-y-1">
          <span className="font-bold text-amber-300">
            PROTOTYPE DECISION-SUPPORT HEURISTIC DISCLAIMER
          </span>
          <p className="text-amber-200/80 leading-relaxed font-sans">
            The flood extent and Red Zone geometries displayed here are computed via planar projected buffer heuristics and synthetic elevation contours for decision-support prototyping (SIH 26191). This is an operational heuristic rather than a validated hydrodynamic forecasting model.
          </p>
        </div>
      </div>

      {/* Hazard State Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {hazards.map((h) => (
          <div key={h.id} className="p-4 rounded-xl bg-[#0c121d] border border-slate-800 shadow-lg space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-slate-200 uppercase font-mono">
                {h.hazard_type}
              </span>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800">
                {h.state_type}
              </span>
            </div>

            <div className="space-y-1 text-xs">
              <div className="flex justify-between text-slate-400">
                <span>Severity Scale:</span>
                <span className="text-rose-400 font-bold">{h.severity}</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Heuristic Confidence:</span>
                <span className="text-emerald-400 font-mono">{(h.confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="flex justify-between text-slate-400">
                <span>Geometry Type:</span>
                <span className="text-slate-300 font-mono">{h.geom_geojson?.type || "Polygon"}</span>
              </div>
            </div>

            <div className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800 text-[11px] text-slate-400 font-mono">
              Corridor Corridor: Vayu River Axial Stream
            </div>
          </div>
        ))}
      </div>

      {/* Red Zones & Evidence Table */}
      <div className="p-5 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2">
            <Shield className="w-4 h-4 text-rose-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Active Red Zone Designations & Threshold Evidence
            </h2>
          </div>
          <span className="text-xs text-slate-400 font-mono">
            E1 Hazard Verification Pipeline
          </span>
        </div>

        {redZones.length === 0 ? (
          <div className="text-center py-8 text-slate-500 font-mono text-xs">
            No Red Zones delineated for snapshot {snapshotId}.
          </div>
        ) : (
          <div className="space-y-4">
            {redZones.map((rz) => (
              <div key={rz.id} className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center space-x-2">
                    <span className="font-bold text-sm text-white font-mono">{rz.designation_code}</span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-rose-950 text-rose-300 border border-rose-800/60">
                      {rz.operational_status}
                    </span>
                  </div>
                  <span className="text-xs font-mono text-amber-400">
                    Reason: {rz.reason_code}
                  </span>
                </div>

                {/* Evidence Metrics Table */}
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs font-mono">
                    <thead className="bg-slate-950/60 text-slate-400 uppercase text-[10px] border-b border-slate-800">
                      <tr>
                        <th className="p-2">Observed Metric</th>
                        <th className="p-2">Measured Value</th>
                        <th className="p-2">Trigger Threshold</th>
                        <th className="p-2">Telemetry Reference</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {rz.evidences?.map((ev: any) => (
                        <tr key={ev.id} className="hover:bg-slate-800/30">
                          <td className="p-2 text-slate-300 font-medium">{ev.metric_name}</td>
                          <td className="p-2 text-rose-400 font-bold">{ev.measured_value}</td>
                          <td className="p-2 text-amber-400">{ev.threshold_value}</td>
                          <td className="p-2 text-slate-400">{ev.source_reference}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
