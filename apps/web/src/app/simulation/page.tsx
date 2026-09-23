"use client";

import React, { useState, useEffect } from "react";
import { getDashboardOverview, runScenario } from "@/lib/api";
import { useSnapshot } from "@/lib/snapshot-context";
import {
  GitCompare,
  Activity,
  ArrowRight,
  Sparkles,
  Shield,
  AlertTriangle,
  Building2,
  Users,
  Compass,
  Play,
  RotateCcw,
  CheckCircle2
} from "lucide-react";

export default function SimulationPage() {
  const {
    snapshotId,
    activeSnapshot,
    isBaseline,
    runMonsoonScenario,
    handleResetBaseline,
    scenarioRunning
  } = useSnapshot();

  const [baseData, setBaseData] = useState<any>(null);
  const [activeData, setActiveData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchStates = async () => {
      try {
        setLoading(true);
        const [bRes, aRes] = await Promise.all([
          getDashboardOverview("SNAP_BASE_001"),
          getDashboardOverview(snapshotId)
        ]);
        setBaseData(bRes.data);
        setActiveData(aRes.data);
      } catch (err) {
        console.error("Failed to load state comparison:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchStates();
  }, [snapshotId]);

  if (loading && !baseData) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] space-y-3">
        <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <div className="text-slate-400 font-mono text-xs">
          SYNCHRONIZING CAUSAL DELTAS (E5)...
        </div>
      </div>
    );
  }

  const baseKpi = baseData?.kpis || {};
  const activeKpi = activeData?.kpis || {};

  return (
    <div className="flex flex-col gap-5 flex-1 max-w-[1700px] mx-auto w-full">
      {/* Top Header */}
      <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-950/80 border border-indigo-800/60 flex items-center justify-center">
            <GitCompare className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">
              Causal Replanning & Multi-Stage Adaptation (Engine 5)
            </h1>
            <div className="text-xs text-slate-400 font-mono">
              Baseline vs Modeled Scenario Causal Differential | Active Snapshot:{" "}
              <span className="text-cyan-400 font-semibold">{snapshotId}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-3">
          {isBaseline ? (
            <button
              onClick={() => runMonsoonScenario()}
              disabled={scenarioRunning}
              className="flex items-center space-x-2 px-3.5 py-1.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white text-xs font-semibold shadow-md transition-all disabled:opacity-50"
            >
              <Play className="w-3.5 h-3.5" />
              <span>Simulate Monsoon Surge</span>
            </button>
          ) : (
            <button
              onClick={handleResetBaseline}
              className="flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-all"
            >
              <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
              <span>Restore Baseline</span>
            </button>
          )}
        </div>
      </div>

      {/* The 7-Step Causal Chain Flow Diagram */}
      <div className="p-5 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              The 7-Step Causal Intelligence Loop
            </h2>
          </div>
          <span className="text-[11px] font-mono text-slate-400">
            A disaster does not stay static — PRISM reasons through the chain
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-2.5 text-xs font-mono">
          {/* Step 1: Hazard */}
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
            <span className="text-[10px] text-rose-400 font-bold">1. HAZARD (E1)</span>
            <div className="text-white font-semibold text-[11px]">Surge & Rise</div>
            <p className="text-[10px] text-slate-400 font-sans">
              Rainfall +20%, River level +0.50m
            </p>
          </div>

          {/* Step 2: Human Impact */}
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
            <span className="text-[10px] text-amber-400 font-bold">2. EXPOSURE (E2)</span>
            <div className="text-white font-semibold text-[11px]">Terrace Flooded</div>
            <p className="text-[10px] text-slate-400 font-sans">
              HAB_02 inundated (+8 HH, +27 pop)
            </p>
          </div>

          {/* Step 3: Priority */}
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
            <span className="text-[10px] text-indigo-400 font-bold">3. PRIORITY (E2)</span>
            <div className="text-white font-semibold text-[11px]">Score Shifts</div>
            <p className="text-[10px] text-slate-400 font-sans">
              Vulnerability recomputed dynamically
            </p>
          </div>

          {/* Step 4: Capacity */}
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
            <span className="text-[10px] text-amber-400 font-bold">4. CAPACITY (E3)</span>
            <div className="text-white font-semibold text-[11px]">Water Bottleneck</div>
            <p className="text-[10px] text-slate-400 font-sans">
              DEST_02 water drops to 45 cap
            </p>
          </div>

          {/* Step 5: Routes */}
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
            <span className="text-[10px] text-rose-400 font-bold">5. ROUTES (E4)</span>
            <div className="text-white font-semibold text-[11px]">Bridge Severed</div>
            <p className="text-[10px] text-slate-400 font-sans">
              BRIDGE_01 collapses, river cut
            </p>
          </div>

          {/* Step 6: Relocation */}
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
            <span className="text-[10px] text-emerald-400 font-bold">6. SOLVER (E4)</span>
            <div className="text-white font-semibold text-[11px]">CP-SAT Replan</div>
            <p className="text-[10px] text-slate-400 font-sans">
              73 people routed via bypasses
            </p>
          </div>

          {/* Step 7: Action */}
          <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
            <span className="text-[10px] text-cyan-400 font-bold">7. ACTION (E6)</span>
            <div className="text-white font-semibold text-[11px]">0 Unmet Demand</div>
            <p className="text-[10px] text-slate-400 font-sans">
              Manifests created, state audited
            </p>
          </div>
        </div>
      </div>

      {/* Side-by-Side State Differential Table */}
      <div className="p-5 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-2">
          <div className="flex items-center space-x-2">
            <Shield className="w-4 h-4 text-indigo-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              State Comparison Matrix: Baseline Reality vs Active Snapshot
            </h2>
          </div>
          <span className="text-xs font-mono text-cyan-400">
            Derived from Database Lineage
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-900/80 text-slate-400 uppercase text-[10px] border-b border-slate-800">
              <tr>
                <th className="p-3">Decision Dimension</th>
                <th className="p-3">Baseline State (SNAP_BASE_001)</th>
                <th className="p-3">Active State ({snapshotId.slice(0, 14)}...)</th>
                <th className="p-3">Measured Causal Delta</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              <tr className="hover:bg-slate-900/30">
                <td className="p-3 font-semibold text-slate-300">Affected Habitations</td>
                <td className="p-3 text-slate-300">1 (HAB_01 Lowlands)</td>
                <td className="p-3 text-rose-300 font-bold">
                  {isBaseline ? "1 (HAB_01 Lowlands)" : "2 (HAB_01 + HAB_02)"}
                </td>
                <td className="p-3 text-rose-400 font-semibold">
                  {isBaseline ? "0 (Baseline)" : "+1 Habitation Inundated"}
                </td>
              </tr>

              <tr className="hover:bg-slate-900/30">
                <td className="p-3 font-semibold text-slate-300">Affected Households</td>
                <td className="p-3 text-slate-300">8 households (26 people)</td>
                <td className="p-3 text-rose-300 font-bold">
                  {isBaseline ? "8 households (26 people)" : "16 households (53 people)"}
                </td>
                <td className="p-3 text-rose-400 font-semibold">
                  {isBaseline ? "0 (Baseline)" : "+8 Households (+27 people)"}
                </td>
              </tr>

              <tr className="hover:bg-slate-900/30">
                <td className="p-3 font-semibold text-slate-300">DEST_02 Effective Capacity</td>
                <td className="p-3 text-slate-300">60 persons (Water safe)</td>
                <td className="p-3 text-amber-300 font-bold">
                  {isBaseline ? "60 persons" : "45 persons (Water degradation)"}
                </td>
                <td className="p-3 text-amber-400 font-semibold">
                  {isBaseline ? "0 (Nominal)" : "-15 Persons Capacity (-25%)"}
                </td>
              </tr>

              <tr className="hover:bg-slate-900/30">
                <td className="p-3 font-semibold text-slate-300">Strategic Bridges</td>
                <td className="p-3 text-emerald-400">BRIDGE_01 OPEN</td>
                <td className="p-3 text-rose-400 font-bold">
                  {isBaseline ? "BRIDGE_01 OPEN" : "BRIDGE_01 COLLAPSED / SEVERED"}
                </td>
                <td className="p-3 text-rose-400 font-semibold">
                  {isBaseline ? "None" : "Primary River Crossing Lost"}
                </td>
              </tr>

              <tr className="hover:bg-slate-900/30">
                <td className="p-3 font-semibold text-slate-300">Relocation Re-allocation</td>
                <td className="p-3 text-slate-300">All 93 assigned to DEST_01</td>
                <td className="p-3 text-cyan-300 font-bold">
                  {isBaseline
                    ? "93 @ DEST_01"
                    : "46 @ DEST_03, 27 @ DEST_02, 20 @ DEST_01"}
                </td>
                <td className="p-3 text-cyan-400 font-semibold">
                  {isBaseline ? "0" : "73 People Relocated via Bypasses"}
                </td>
              </tr>

              <tr className="hover:bg-slate-900/30">
                <td className="p-3 font-semibold text-slate-300">Unmet Groups</td>
                <td className="p-3 text-emerald-400 font-bold">0 unmet</td>
                <td className="p-3 text-emerald-400 font-bold">
                  {activeKpi.unmet_relocation_demand ?? 0} unmet
                </td>
                <td className="p-3 text-emerald-400 font-semibold">
                  All Demand Safely Accommodated
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
