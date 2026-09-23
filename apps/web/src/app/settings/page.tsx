"use client";

import React, { useState, useEffect } from "react";
import { getSystemTelemetry } from "@/lib/api";
import { useSnapshot } from "@/lib/snapshot-context";
import {
  Cpu,
  Database,
  Server,
  Activity,
  CheckCircle2,
  AlertTriangle,
  RotateCcw,
  Shield,
  Layers,
  Info,
  Clock
} from "lucide-react";

export default function SettingsPage() {
  const { snapshotId, handleResetBaseline, isBaseline } = useSnapshot();
  const [telemetry, setTelemetry] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [confirmResetOpen, setConfirmResetOpen] = useState(false);
  const [resetting, setResetting] = useState(false);

  const fetchTelemetry = async () => {
    try {
      setLoading(true);
      const res = await getSystemTelemetry();
      setTelemetry(res);
    } catch (err) {
      console.error("Failed to load telemetry:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
  }, [snapshotId]);

  const onConfirmReset = async () => {
    try {
      setResetting(true);
      await handleResetBaseline();
      setConfirmResetOpen(false);
      await fetchTelemetry();
    } finally {
      setResetting(false);
    }
  };

  if (loading && !telemetry) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] space-y-3">
        <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <div className="text-slate-400 font-mono text-xs">
          MEASURING REAL-TIME RUNTIME TELEMETRY...
        </div>
      </div>
    );
  }

  const measured = telemetry?.measured_telemetry || {};
  const engines = telemetry?.engines || {};
  const dbInfo = telemetry?.database || {};
  const studyArea = telemetry?.study_area || {};

  return (
    <div className="flex flex-col gap-5 flex-1 max-w-[1700px] mx-auto w-full">
      {/* Top Header */}
      <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-slate-900 border border-slate-700 flex items-center justify-center">
            <Cpu className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">
              System Telemetry & Architecture Specifications
            </h1>
            <div className="text-xs text-slate-400 font-mono">
              Measured Runtime Performance & Engine Status | Edition:{" "}
              <span className="text-indigo-400 font-semibold">{telemetry?.architecture_edition}</span>
            </div>
          </div>
        </div>

        <button
          onClick={fetchTelemetry}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono transition-all border border-slate-700"
        >
          <Activity className="w-3.5 h-3.5 text-cyan-400" />
          <span>Refresh Telemetry</span>
        </button>
      </div>

      {/* Measured Dynamic Telemetry KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 font-mono text-xs">
        <div className="p-4 rounded-xl bg-[#0c121d] border border-slate-800 shadow-md">
          <div className="flex items-center justify-between text-slate-400 text-[10px]">
            <span>DB QUERY LATENCY</span>
            <Database className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 mt-2">
            {measured.query_latency_ms ?? 0.0} ms
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Measured via SQL SELECT 1</div>
        </div>

        <div className="p-4 rounded-xl bg-[#0c121d] border border-slate-800 shadow-md">
          <div className="flex items-center justify-between text-slate-400 text-[10px]">
            <span>TELEMETRY CYCLE</span>
            <Activity className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-cyan-400 mt-2">
            {measured.telemetry_latency_ms ?? 0.0} ms
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Dynamic Runtime Profiling</div>
        </div>

        <div className="p-4 rounded-xl bg-[#0c121d] border border-slate-800 shadow-md">
          <div className="flex items-center justify-between text-slate-400 text-[10px]">
            <span>DATABASE SIZE</span>
            <Server className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">
            {dbInfo.file_size_kb ?? 0} KB
          </div>
          <div className="text-[10px] text-slate-400 mt-1">Local Demonstration Store</div>
        </div>

        <div className="p-4 rounded-xl bg-[#0c121d] border border-slate-800 shadow-md">
          <div className="flex items-center justify-between text-slate-400 text-[10px]">
            <span>DATABASE STATUS</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 mt-2">
            {dbInfo.connected ? "CONNECTED" : "OFFLINE"}
          </div>
          <div className="text-[10px] text-slate-400 mt-1">ACID Transactional</div>
        </div>
      </div>

      {/* Engines Health Matrix */}
      <div className="p-5 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center space-x-2">
            <Cpu className="w-4 h-4 text-indigo-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              E1–E6 Decision Backbone Engines Status
            </h2>
          </div>
          <span className="text-xs font-mono text-emerald-400">All Engines Active</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5 text-xs font-mono">
          {Object.entries(engines).map(([name, eng]: [string, any]) => (
            <div key={name} className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-white">{name.replace("_", " ")}</span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                  {eng.status}
                </span>
              </div>
              <p className="text-[11px] text-slate-400 font-sans leading-relaxed">
                {eng.role}
              </p>
              <div className="text-[10px] text-indigo-400 border-t border-slate-800/80 pt-1">
                Quality: {eng.quality}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Scalability Story & Migration Architecture */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        {/* Persistence Story */}
        <div className="p-5 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl space-y-3 text-xs">
          <div className="flex items-center space-x-2 text-indigo-300 font-bold uppercase tracking-wider">
            <Database className="w-4 h-4" />
            <span>Persistence & Future Scale Target</span>
          </div>
          <p className="text-slate-300 leading-relaxed font-sans">
            The current SIH prototype operates on a local SQLite store ({dbInfo.engine}) with full domain repository abstraction. The engines never interact with SQLite-specific SQL directly, ensuring clean forward compatibility with the enterprise target:
          </p>
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 font-mono text-cyan-300 text-[11px] space-y-1">
            <div>Target Deployment: PostgreSQL 16 + PostGIS 3.4</div>
            <div>Geospatial Backend: PostGIS Geometry Columns (EPSG:4326 / EPSG:32643)</div>
            <div>Spatial Indexing: R-Tree / GiST Spatial Indexing</div>
          </div>
          <div className="text-slate-500 font-mono text-[10px]">
            * Note: Do not claim national-scale measured performance until benchmarked against the full PostGIS national layer.
          </div>
        </div>

        {/* Study Area Geospatial Info & Canonical Reset Action */}
        <div className="p-5 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl space-y-4 text-xs">
          <div className="flex items-center space-x-2 text-cyan-300 font-bold uppercase tracking-wider">
            <Layers className="w-4 h-4" />
            <span>Study Area Cartographic Parameters</span>
          </div>
          <div className="space-y-1.5 font-mono text-slate-300">
            <div className="flex justify-between">
              <span className="text-slate-500">Name:</span>
              <span className="text-white font-semibold">{studyArea.name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Code:</span>
              <span>{studyArea.code}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">CRS:</span>
              <span className="text-cyan-400">{studyArea.coordinate_reference_system}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-500">Entities:</span>
              <span>
                {studyArea.entities?.habitations} Habs | {studyArea.entities?.destinations} Dests |{" "}
                {studyArea.entities?.road_segments} Roads
              </span>
            </div>
          </div>

          <div className="pt-3 border-t border-slate-800">
            <button
              onClick={() => setConfirmResetOpen(true)}
              className="w-full py-2.5 px-4 rounded-xl bg-rose-950/60 hover:bg-rose-900/60 border border-rose-800/80 text-rose-300 font-bold text-xs flex items-center justify-center space-x-2 transition-all font-mono"
            >
              <RotateCcw className="w-4 h-4" />
              <span>Restore Canonical Baseline World (SNAP_BASE_001)</span>
            </button>
          </div>
        </div>
      </div>

      {/* Confirmation Modal */}
      {confirmResetOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-in fade-in">
          <div className="p-6 rounded-2xl bg-[#0d1422] border border-rose-800/80 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center space-x-3 text-rose-400">
              <AlertTriangle className="w-6 h-6" />
              <h3 className="font-bold text-sm text-white">Confirm Canonical Baseline Reset</h3>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              This will purge all active scenario runs and uncommitted authority overrides, restoring the deterministic canonical baseline world (SNAP_BASE_001) for the SIH jury presentation.
            </p>
            <div className="flex items-center justify-end space-x-3 font-mono text-xs pt-2">
              <button
                onClick={() => setConfirmResetOpen(false)}
                className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={onConfirmReset}
                disabled={resetting}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white font-bold"
              >
                {resetting ? "Resetting..." : "Yes, Restore Canonical State"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
