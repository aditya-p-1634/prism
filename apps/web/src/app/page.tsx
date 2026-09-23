"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import MapViewer from "@/components/MapViewer";
import { getDashboardOverview, getAuditEvents } from "@/lib/api";
import { useSnapshot } from "@/lib/snapshot-context";
import {
  AlertTriangle,
  Users,
  Building2,
  Navigation,
  Activity,
  CheckCircle2,
  ArrowRight,
  Play,
  RotateCcw,
  Sparkles,
  ShieldAlert,
  ArrowUpRight,
  TrendingUp,
  MapPin,
  Clock,
  Layers
} from "lucide-react";

export default function CommandDashboardPage() {
  const {
    snapshotId,
    activeSnapshot,
    isBaseline,
    runMonsoonScenario,
    handleResetBaseline,
    scenarioRunning,
    showToast
  } = useSnapshot();

  const [data, setData] = useState<any>(null);
  const [auditEvents, setAuditEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<any>(null);
  const [deltaReport, setDeltaReport] = useState<any>(null);

  const loadData = async (snapId: string) => {
    try {
      setLoading(true);
      setError(null);
      const [res, auditRes] = await Promise.all([
        getDashboardOverview(snapId),
        getAuditEvents(undefined, 8).catch(() => ({ events: [] }))
      ]);
      setData(res.data);
      setAuditEvents(auditRes.events || []);
    } catch (err: any) {
      setError(err.message || "Failed to connect to PRISM causal backbone");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(snapshotId);
  }, [snapshotId]);

  const handleRunScenarioClick = async () => {
    try {
      const delta = await runMonsoonScenario();
      setDeltaReport(delta);
    } catch (err: any) {
      // Toast already shown in context
    }
  };

  if (loading && !data) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] space-y-4">
        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
        <div className="text-slate-400 font-mono text-sm tracking-wide">
          QUERYING PRISM CAUSAL BACKBONE ({snapshotId})...
        </div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="p-6 rounded-2xl bg-rose-950/30 border border-rose-800/60 max-w-xl mx-auto my-12 text-center space-y-4">
        <AlertTriangle className="w-10 h-10 text-rose-400 mx-auto" />
        <h2 className="text-lg font-bold text-rose-200">Backend Connection Error</h2>
        <p className="text-xs text-rose-300 font-mono">{error}</p>
        <button
          onClick={() => loadData(snapshotId)}
          className="px-4 py-2 bg-rose-600 hover:bg-rose-500 text-white rounded-lg text-xs font-semibold"
        >
          Retry Connection
        </button>
      </div>
    );
  }

  const kpis = data?.kpis || {};
  const layers = data?.layers || {};

  return (
    <div className="flex flex-col gap-5 flex-1 max-w-[1800px] mx-auto w-full">
      {/* Scenario Control Strip */}
      <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-blue-950 border border-blue-800/60 flex items-center justify-center">
            <Activity className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-sm font-bold text-white tracking-wide">
                {activeSnapshot.label || "Vayu River Basin State"}
              </span>
              <span
                className={`text-[10px] font-mono px-2 py-0.5 rounded-full ${
                  isBaseline
                    ? "bg-emerald-950 text-emerald-300 border border-emerald-800/60"
                    : "bg-blue-950 text-cyan-300 border border-cyan-800/60"
                }`}
              >
                {isBaseline ? "CANONICAL BASELINE" : "ADAPTIVE SCENARIO"}
              </span>
            </div>
            <div className="text-xs text-slate-400 font-mono mt-0.5">
              Snapshot ID: <span className="text-slate-300">{snapshotId}</span> | Status:{" "}
              <span className="text-emerald-400 font-medium">IMMUTABLE / ACID</span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-3">
          {isBaseline ? (
            <button
              onClick={handleRunScenarioClick}
              disabled={scenarioRunning}
              className="flex items-center space-x-2 px-4 py-2 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium text-xs shadow-lg shadow-blue-600/25 transition-all disabled:opacity-50"
            >
              <Play className="w-4 h-4 fill-white" />
              <span>
                {scenarioRunning
                  ? "PRISM IS RECOMPUTING DECISION CHAIN..."
                  : "SIMULATE MONSOON_SURGE_01"}
              </span>
            </button>
          ) : (
            <div className="flex items-center space-x-2">
              <Link
                href="/simulation"
                className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-blue-600/30 border border-blue-500/50 hover:bg-blue-600/40 text-blue-200 text-xs font-medium transition-all"
              >
                <Sparkles className="w-4 h-4 text-cyan-400" />
                <span>View Full Causal Comparison</span>
              </Link>
              <button
                onClick={handleResetBaseline}
                className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-all border border-slate-700"
              >
                <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
                <span>Reset to Baseline</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* KPI Cards Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3.5">
        {/* KPI 1: Habitations */}
        <div className="p-4 rounded-xl bg-[#0c121d] border border-slate-800 shadow-md flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>STUDY AREA HABITATIONS</span>
            <Users className="w-4 h-4 text-blue-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-white">{kpis.total_habitations}</span>
            <span className="text-xs text-slate-400">({kpis.total_households} HH)</span>
          </div>
          <div className="mt-1 text-[11px] text-blue-400 font-mono">
            Vayu River Basin (93 Pop)
          </div>
        </div>

        {/* KPI 2: Immediate Evacuation */}
        <div className="p-4 rounded-xl bg-[#0c121d] border border-slate-800 shadow-md flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>IMMEDIATE EVACUATION</span>
            <AlertTriangle className="w-4 h-4 text-rose-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-rose-400">
              {kpis.immediate_priority_households}
            </span>
            <span className="text-xs text-slate-400">P ≥ 75</span>
          </div>
          <div className="mt-1 text-[11px] text-rose-400/90 font-mono">
            Critical Red Zone Exposure
          </div>
        </div>

        {/* KPI 3: Limiting Bottleneck */}
        <div className="p-4 rounded-xl bg-[#0c121d] border border-slate-800 shadow-md flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>ACTIVE BOTTLENECK</span>
            <Building2 className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-amber-300">
              {kpis.active_bottlenecks?.includes("WATER") ? "WATER" : "SHELTER"}
            </span>
          </div>
          <div className="mt-1 text-[11px] text-amber-400/90 font-mono">
            Limiting Constraint @ DEST_02
          </div>
        </div>

        {/* KPI 4: Assigned Convoys */}
        <div className="p-4 rounded-xl bg-[#0c121d] border border-slate-800 shadow-md flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>ASSIGNED RELOCATIONS</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-3xl font-extrabold text-emerald-400">
              {kpis.total_relocations_assigned}
            </span>
            <span className="text-xs text-slate-400">groups (93 pop)</span>
          </div>
          <div className="mt-1 text-[11px] text-emerald-400/90 font-mono">
            CP-SAT Constrained Solver
          </div>
        </div>

        {/* KPI 5: Unmet Demand */}
        <div className="p-4 rounded-xl bg-[#0c121d] border border-slate-800 shadow-md flex flex-col justify-between">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>UNMET DEMAND</span>
            <ShieldAlert className="w-4 h-4 text-purple-400" />
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span
              className={`text-3xl font-extrabold ${
                kpis.unmet_relocation_demand > 0 ? "text-rose-400" : "text-slate-300"
              }`}
            >
              {kpis.unmet_relocation_demand}
            </span>
            <span className="text-xs text-slate-400">groups</span>
          </div>
          <div className="mt-1 text-[11px] text-purple-400/90 font-mono">
            Explicit Safety Limit (0 unmet)
          </div>
        </div>
      </div>

      {/* Main Grid: GIS Map & Operational Workspace Panels */}
      <div className="grid grid-cols-1 xl:grid-cols-12 gap-5 flex-1">
        {/* Left Column: Interactive GIS Map Viewer (7 Cols) */}
        <div className="xl:col-span-7 flex flex-col rounded-2xl border border-slate-800 bg-[#0c121d] shadow-xl overflow-hidden min-h-[580px]">
          <div className="p-3.5 border-b border-slate-800/80 bg-slate-900/60 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <MapPin className="w-4 h-4 text-cyan-400" />
              <span className="text-xs font-bold uppercase tracking-wider text-slate-200">
                Operational GIS Map — Vayu River Basin
              </span>
            </div>
            <Link
              href="/map"
              className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
            >
              <span>Full GIS Workspace</span>
              <ArrowUpRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          <div className="flex-1 p-2">
            <MapViewer
              layers={layers}
              selectedEntity={selectedEntity}
              onSelectEntity={(entity) => setSelectedEntity(entity)}
            />
          </div>
        </div>

        {/* Right Column: Tactical Causal Loop & Workspaces (5 Cols) */}
        <div className="xl:col-span-5 flex flex-col gap-4">
          {/* Causal Scenario Delta Card */}
          {!isBaseline ? (
            <div className="p-4 rounded-2xl bg-gradient-to-br from-indigo-950/40 via-slate-900/80 to-[#0c121d] border border-indigo-700/50 shadow-xl space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-indigo-300 font-bold text-xs uppercase tracking-wider">
                  <Sparkles className="w-4 h-4 text-cyan-400" />
                  <span>Causal Replanning Delta Analysis</span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-900/60 text-indigo-300 border border-indigo-700/60">
                  MONSOON_SURGE_01
                </span>
              </div>

              <div className="space-y-2 text-xs">
                <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                  <div className="font-semibold text-rose-400 text-[11px] font-mono">
                    1. WHAT CHANGED (HAZARD & INFRASTRUCTURE)
                  </div>
                  <p className="text-slate-300 mt-1">
                    Precipitation surge (+20%), river stage (+0.5m) inundated Terrace Settlement (HAB_02).{" "}
                    <span className="text-rose-300 font-semibold">BRIDGE_01 collapsed</span>, cutting direct access to DEST_01.
                  </p>
                </div>

                <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                  <div className="font-semibold text-amber-400 text-[11px] font-mono">
                    2. CAPACITY & ROUTING CONSEQUENCES
                  </div>
                  <p className="text-slate-300 mt-1">
                    DEST_02 water degradation reduced effective capacity from 60 to 45. Direct river routes severed; secondary Eastern & Southern bypasses engaged.
                  </p>
                </div>

                <div className="p-2.5 rounded-xl bg-slate-950/60 border border-slate-800/80">
                  <div className="font-semibold text-emerald-400 text-[11px] font-mono">
                    3. ADAPTIVE RELOCATION ACTION
                  </div>
                  <p className="text-slate-300 mt-1">
                    CP-SAT dynamically reallocated <span className="text-emerald-300 font-bold">73 people</span> away from DEST_01:
                    46 to DEST_03 (Sports Complex), 27 to DEST_02 (School), with 20 remaining safe at DEST_01.{" "}
                    <span className="text-emerald-400 font-semibold">0 unmet groups</span>.
                  </p>
                </div>
              </div>

              <div className="pt-1 flex items-center justify-between">
                <Link
                  href="/overrides"
                  className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center space-x-1 font-medium"
                >
                  <span>Authorize Operational Override</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
                <Link
                  href="/reports"
                  className="text-xs text-cyan-400 hover:text-cyan-300 flex items-center space-x-1 font-medium"
                >
                  <span>Download Manifest (CSV)</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          ) : (
            <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2 text-slate-300 font-bold text-xs uppercase tracking-wider">
                  <Activity className="w-4 h-4 text-emerald-400" />
                  <span>Canonical Baseline State</span>
                </div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800/60">
                  SNAP_BASE_001
                </span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Normal pre-monsoon condition. River flow remains within primary channel corridors. All 28 households across the 4 habitations are pre-allocated to Vayu Community Center (DEST_01, effective capacity 150), with all 12 road segments and bridges fully open.
              </p>
              <div className="pt-2 flex items-center space-x-3">
                <button
                  onClick={handleRunScenarioClick}
                  disabled={scenarioRunning}
                  className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-medium transition-all"
                >
                  <Play className="w-3.5 h-3.5" />
                  <span>Run Monsoon Surge Test</span>
                </button>
                <Link
                  href="/simulation"
                  className="text-xs text-slate-400 hover:text-white flex items-center space-x-1"
                >
                  <span>Inspect Architecture</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          )}

          {/* Destination Capacity Overview Card */}
          <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-slate-200">
                <Building2 className="w-4 h-4 text-indigo-400" />
                <span>Destination Shelter Capacities (E3)</span>
              </div>
              <Link
                href="/resources"
                className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
              >
                <span>Details</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>

            <div className="space-y-3">
              {layers?.destinations?.features?.map((f: any) => {
                const p = f.properties;
                const eff = p.effective_capacity || 1;
                const rem = p.remaining_capacity || 0;
                const occ = eff - rem;
                const pct = Math.min(100, Math.round((occ / eff) * 100));

                return (
                  <div key={p.id} className="p-2.5 rounded-xl bg-slate-900/60 border border-slate-800/80 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-200">
                        {p.code} — {p.name}
                      </span>
                      <span className="text-[10px] font-mono text-amber-400">
                        Bottleneck: {p.bottleneck_resource}
                      </span>
                    </div>

                    <div className="mt-2 flex items-center space-x-2">
                      <div className="flex-1 h-2 rounded-full bg-slate-800 overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${
                            pct > 85 ? "bg-rose-500" : pct > 50 ? "bg-amber-500" : "bg-emerald-500"
                          }`}
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                      <span className="text-[11px] font-mono text-slate-300 shrink-0">
                        {occ}/{eff} ({pct}%)
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Recent Operational Audit Stream */}
          <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl space-y-3">
            <div className="flex items-center justify-between border-b border-slate-800 pb-2">
              <div className="flex items-center space-x-2 text-xs font-bold uppercase tracking-wider text-slate-200">
                <Clock className="w-4 h-4 text-emerald-400" />
                <span>Recent Operational Audit Stream</span>
              </div>
              <Link
                href="/audit"
                className="text-[11px] font-mono text-cyan-400 hover:text-cyan-300 flex items-center space-x-1"
              >
                <span>Full Audit</span>
                <ArrowRight className="w-3 h-3" />
              </Link>
            </div>

            <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
              {auditEvents.length === 0 ? (
                <div className="text-xs text-slate-500 font-mono py-2">
                  No recent operational override events recorded yet.
                </div>
              ) : (
                auditEvents.slice(0, 4).map((evt: any) => (
                  <div
                    key={evt.id}
                    className="p-2 rounded-lg bg-slate-900/50 border border-slate-800 text-[11px] font-mono space-y-1"
                  >
                    <div className="flex items-center justify-between text-slate-300">
                      <span className="text-indigo-400 font-semibold">{evt.action_type}</span>
                      <span className="text-slate-500">{evt.created_at?.slice(11, 19)}</span>
                    </div>
                    <div className="text-slate-400 truncate">
                      {evt.justification || `Action executed on ${evt.entity_type}`}
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
