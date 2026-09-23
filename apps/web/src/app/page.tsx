"use client";

import React, { useState, useEffect } from "react";
import MapViewer from "@/components/MapViewer";
import { getDashboardOverview, runScenario, overrideAllocation, getSnapshots } from "@/lib/api";
import {
  AlertTriangle, Shield, Users, Building2, Navigation, Activity,
  CheckCircle2, ArrowRight, Play, RefreshCw, Lock, Sparkles, Filter
} from "lucide-react";

export default function DashboardPage() {
  const [snapshotId, setSnapshotId] = useState("SNAP_BASE_001");
  const [snapshots, setSnapshots] = useState<any[]>([]);
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [activeTab, setActiveTab] = useState<"CAUSAL" | "E1" | "E2" | "E3" | "E4" | "OVERRIDE">("CAUSAL");
  const [selectedEntity, setSelectedEntity] = useState<any>(null);
  const [scenarioRunning, setScenarioRunning] = useState(false);
  const [deltaReport, setDeltaReport] = useState<any>(null);

  // Override Form State
  const [overrideGroupId, setOverrideGroupId] = useState("");
  const [overrideDestId, setOverrideDestId] = useState("DEST_03");
  const [overrideJustification, setOverrideJustification] = useState("");
  const [overrideSuccess, setOverrideSuccess] = useState(false);

  const loadData = async (snapId: string) => {
    try {
      setLoading(true);
      setError(null);
      const res = await getDashboardOverview(snapId);
      setData(res.data);
      const snapRes = await getSnapshots();
      setSnapshots(snapRes.data);
    } catch (err: any) {
      setError(err.message || "Failed to connect to PRISM backend");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData(snapshotId);
  }, [snapshotId]);

  const handleRunScenario = async () => {
    try {
      setScenarioRunning(true);
      const res = await runScenario("MONSOON_SURGE_01");
      setDeltaReport(res.data);
      setSnapshotId(res.data.scenario_snapshot_id);
      await loadData(res.data.scenario_snapshot_id);
      setActiveTab("CAUSAL");
    } catch (err: any) {
      alert(`Scenario execution failed: ${err.message}`);
    } finally {
      setScenarioRunning(false);
    }
  };

  const handleApplyOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!overrideJustification.trim()) {
      alert("Please enter a mandatory operational justification for the audit log.");
      return;
    }
    try {
      await overrideAllocation(overrideGroupId, overrideDestId, overrideJustification);
      setOverrideSuccess(true);
      setTimeout(() => setOverrideSuccess(false), 4000);
      setOverrideJustification("");
      loadData(snapshotId);
    } catch (err: any) {
      alert(`Override failed: ${err.message}`);
    }
  };

  if (loading && !data) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] space-y-4">
        <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
        <div className="text-slate-400 font-mono text-sm tracking-wide">
          CONNECTING TO PRISM CAUSAL BACKBONE...
        </div>
      </div>
    );
  }

  const kpis = data?.kpis || {};
  const layers = data?.layers || {};

  return (
    <div className="flex flex-col gap-4 flex-1">
      {/* Top Operational Status Strip */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        {/* KPI 1 */}
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>HABITATIONS</span>
            <Users className="w-4 h-4 text-blue-400" />
          </div>
          <div className="mt-1.5 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-white">{kpis.total_habitations}</span>
            <span className="text-xs text-slate-400">({kpis.total_households} HH)</span>
          </div>
          <div className="mt-1 text-[11px] text-blue-400 font-mono">Vayu River Basin</div>
        </div>

        {/* KPI 2 */}
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>IMMEDIATE EVACUATION</span>
            <AlertTriangle className="w-4 h-4 text-red-400" />
          </div>
          <div className="mt-1.5 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-red-400">{kpis.immediate_priority_households}</span>
            <span className="text-xs text-slate-400">P ≥ 75</span>
          </div>
          <div className="mt-1 text-[11px] text-red-400 font-mono">Critical Red Zone</div>
        </div>

        {/* KPI 3 */}
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>ACTIVE BOTTLENECK</span>
            <Building2 className="w-4 h-4 text-amber-400" />
          </div>
          <div className="mt-1.5 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-amber-300">
              {kpis.active_bottlenecks?.includes("WATER") ? "WATER" : "SHELTER"}
            </span>
          </div>
          <div className="mt-1 text-[11px] text-amber-400/80 font-mono">Limiting Resource @ D2</div>
        </div>

        {/* KPI 4 */}
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>ASSIGNED CONVOYS</span>
            <CheckCircle2 className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="mt-1.5 flex items-baseline space-x-2">
            <span className="text-2xl font-bold text-emerald-400">{kpis.total_relocations_assigned}</span>
            <span className="text-xs text-slate-400">groups</span>
          </div>
          <div className="mt-1 text-[11px] text-emerald-400/80 font-mono">CP-SAT Optimized</div>
        </div>

        {/* KPI 5 */}
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 shadow-md">
          <div className="flex items-center justify-between text-slate-400 text-xs font-mono">
            <span>UNMET DEMAND</span>
            <Shield className="w-4 h-4 text-purple-400" />
          </div>
          <div className="mt-1.5 flex items-baseline space-x-2">
            <span className={`text-2xl font-bold ${kpis.unmet_relocation_demand > 0 ? "text-purple-400" : "text-slate-300"}`}>
              {kpis.unmet_relocation_demand}
            </span>
            <span className="text-xs text-slate-400">groups</span>
          </div>
          <div className="mt-1 text-[11px] text-purple-400/80 font-mono">Explicit Safety Limit</div>
        </div>
      </div>

      {/* Main Command Center: Map + Tactical Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 flex-1">
        {/* Left: Interactive Vector Geospatial Map (7 Cols) */}
        <div className="lg:col-span-7 flex flex-col">
          <MapViewer
            layers={layers}
            selectedEntity={selectedEntity}
            onSelectEntity={(entity) => {
              setSelectedEntity(entity);
              if (entity.type === "HABITATION") setActiveTab("E2");
              if (entity.type === "DESTINATION") setActiveTab("E3");
            }}
          />
        </div>

        {/* Right: Tactical Multi-Engine Inspector (5 Cols) */}
        <div className="lg:col-span-5 flex flex-col rounded-xl border border-slate-800 bg-[#0d131f] shadow-xl overflow-hidden min-h-[580px]">
          {/* Tactical Tab Navigation */}
          <div className="flex border-b border-slate-800 bg-slate-900/60 p-1 text-xs font-mono overflow-x-auto">
            <button
              onClick={() => setActiveTab("CAUSAL")}
              className={`px-3 py-2 rounded-lg transition-all flex items-center space-x-1.5 whitespace-nowrap ${
                activeTab === "CAUSAL" ? "bg-blue-600 text-white font-semibold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Activity className="w-3.5 h-3.5" />
              <span>Causal Loop</span>
            </button>

            <button
              onClick={() => setActiveTab("E1")}
              className={`px-3 py-2 rounded-lg transition-all flex items-center space-x-1.5 whitespace-nowrap ${
                activeTab === "E1" ? "bg-blue-600 text-white font-semibold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <span>E1 Hazard</span>
            </button>

            <button
              onClick={() => setActiveTab("E2")}
              className={`px-3 py-2 rounded-lg transition-all flex items-center space-x-1.5 whitespace-nowrap ${
                activeTab === "E2" ? "bg-blue-600 text-white font-semibold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <span>E2 People</span>
            </button>

            <button
              onClick={() => setActiveTab("E3")}
              className={`px-3 py-2 rounded-lg transition-all flex items-center space-x-1.5 whitespace-nowrap ${
                activeTab === "E3" ? "bg-blue-600 text-white font-semibold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <span>E3 Capacity</span>
            </button>

            <button
              onClick={() => setActiveTab("E4")}
              className={`px-3 py-2 rounded-lg transition-all flex items-center space-x-1.5 whitespace-nowrap ${
                activeTab === "E4" ? "bg-blue-600 text-white font-semibold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <span>E4 Routes</span>
            </button>

            <button
              onClick={() => setActiveTab("OVERRIDE")}
              className={`px-3 py-2 rounded-lg transition-all flex items-center space-x-1.5 whitespace-nowrap ${
                activeTab === "OVERRIDE" ? "bg-indigo-600 text-white font-semibold" : "text-slate-400 hover:text-slate-200"
              }`}
            >
              <Shield className="w-3.5 h-3.5" />
              <span>Authority</span>
            </button>
          </div>

          {/* Tactical Tab Content Panel */}
          <div className="p-4 flex-1 overflow-y-auto space-y-4">
            {/* TAB 1: CAUSAL LOOP & SCENARIO INJECTION */}
            {activeTab === "CAUSAL" && (
              <div className="space-y-4">
                {/* Causal Chain Breadcrumb Bar */}
                <div className="p-3 rounded-lg bg-slate-950/80 border border-slate-800">
                  <div className="text-[11px] font-mono text-slate-400 mb-2">DECISION-SUPPORT CAUSAL CHAIN:</div>
                  <div className="flex items-center justify-between text-xs font-mono font-bold">
                    <span className="text-blue-400">HAZARD</span>
                    <ArrowRight className="w-3 h-3 text-slate-600" />
                    <span className="text-amber-400">HUMAN</span>
                    <ArrowRight className="w-3 h-3 text-slate-600" />
                    <span className="text-red-400">PRIORITY</span>
                    <ArrowRight className="w-3 h-3 text-slate-600" />
                    <span className="text-cyan-400">CAPACITY</span>
                    <ArrowRight className="w-3 h-3 text-slate-600" />
                    <span className="text-emerald-400">ACTION</span>
                  </div>
                </div>

                {/* Scenario Simulator Card */}
                <div className="p-4 rounded-xl bg-gradient-to-br from-indigo-950/50 to-slate-900 border border-indigo-800/40 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-2">
                      <Sparkles className="w-4 h-4 text-indigo-400" />
                      <span className="font-bold text-sm text-indigo-200">WHAT-IF PREDICTIVE SIMULATOR (E5)</span>
                    </div>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-900/60 text-indigo-300 border border-indigo-700/50">
                      Adaptive Replanning
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed">
                    Inject compound disaster conditions: <strong>+20% precipitation surge</strong>, <strong>+0.50m river rise</strong>, <strong>BRIDGE_01 closure</strong>, and a <strong>-25% water capacity bottleneck at Destination 2</strong>. Observe live causal propagation.
                  </p>

                  <div className="flex items-center space-x-3 pt-2">
                    <button
                      onClick={handleRunScenario}
                      disabled={scenarioRunning}
                      className="flex-1 py-2.5 px-4 rounded-lg bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800 text-white font-semibold text-xs tracking-wide flex items-center justify-center space-x-2 transition-all shadow-lg shadow-blue-600/30"
                    >
                      {scenarioRunning ? (
                        <>
                          <RefreshCw className="w-4 h-4 animate-spin text-white" />
                          <span>PROPAGATING CAUSAL CASCADE...</span>
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4 fill-white" />
                          <span>ACTIVATE: MONSOON_SURGE_01</span>
                        </>
                      )}
                    </button>

                    <button
                      onClick={() => setSnapshotId("SNAP_BASE_001")}
                      className="py-2.5 px-3 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-mono"
                    >
                      Reset Baseline
                    </button>
                  </div>
                </div>

                {/* Live Causal Delta Report if Scenario Run */}
                {deltaReport && (
                  <div className="p-4 rounded-xl bg-slate-950 border border-cyan-800/60 space-y-3 animate-fadeIn">
                    <div className="flex items-center justify-between text-xs font-mono text-cyan-400 font-bold">
                      <span>CAUSAL DELTA REPORT</span>
                      <span>{deltaReport.scenario_code}</span>
                    </div>

                    <div className="text-xs text-slate-200 bg-slate-900/90 p-3 rounded-lg border border-slate-800 leading-relaxed">
                      {deltaReport.summary_explanation}
                    </div>

                    <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                      <div className="p-2 rounded bg-slate-900 border border-slate-800">
                        <span className="text-slate-400">Route Invalidation:</span>
                        <div className="text-red-400 font-bold mt-0.5">BRIDGE_01 (CLOSED)</div>
                      </div>
                      <div className="p-2 rounded bg-slate-900 border border-slate-800">
                        <span className="text-slate-400">Unmet Demand:</span>
                        <div className="text-purple-400 font-bold mt-0.5">+{deltaReport.unmet_demand_delta} groups</div>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* TAB 2: E1 HAZARD INTELLIGENCE */}
            {activeTab === "E1" && (
              <div className="space-y-3">
                <div className="text-xs font-bold text-slate-300 font-mono">PHYSICAL HAZARD EXTENT & EVIDENCE</div>
                {layers?.red_zones?.features?.map((rz: any, idx: number) => (
                  <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-red-900/60 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-xs text-red-400">{rz.properties.designation}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-red-950 text-red-300 border border-red-800">
                        ACTIVE RED ZONE
                      </span>
                    </div>
                    <div className="text-xs text-slate-300">
                      Reason: <span className="font-mono text-amber-300">{rz.properties.reason}</span>
                    </div>
                    <div className="text-[11px] text-slate-400 font-mono pt-1 border-t border-slate-900">
                      Confidence: 95% Heuristic | Planar Metric Buffer
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* TAB 3: E2 PEOPLE & PRIORITY */}
            {activeTab === "E2" && (
              <div className="space-y-3">
                <div className="text-xs font-bold text-slate-300 font-mono">HABITATION EXPOSURE & VULNERABILITY BREAKDOWN</div>
                {layers?.habitations?.features?.map((h: any, idx: number) => (
                  <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-sm text-slate-100">{h.properties.name}</span>
                      <span className={`text-[10px] font-mono px-2 py-0.5 rounded ${
                        h.properties.immediate_priority_count > 0 ? "bg-red-950 text-red-400 border border-red-800" : "bg-emerald-950 text-emerald-400 border border-emerald-800"
                      }`}>
                        {h.properties.highest_priority}
                      </span>
                    </div>
                    <div className="grid grid-cols-3 gap-2 text-xs font-mono text-center">
                      <div className="p-1.5 rounded bg-slate-900">
                        <div className="text-slate-400 text-[10px]">Pop</div>
                        <div className="text-white font-bold">{h.properties.population}</div>
                      </div>
                      <div className="p-1.5 rounded bg-slate-900">
                        <div className="text-slate-400 text-[10px]">Immediate</div>
                        <div className="text-red-400 font-bold">{h.properties.immediate_priority_count}</div>
                      </div>
                      <div className="p-1.5 rounded bg-slate-900">
                        <div className="text-slate-400 text-[10px]">Elevation</div>
                        <div className="text-slate-300 font-bold">{h.properties.elevation_m}m</div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* TAB 4: E3 DESTINATIONS & CAPACITY */}
            {activeTab === "E3" && (
              <div className="space-y-3">
                <div className="text-xs font-bold text-slate-300 font-mono">CANDIDATE DESTINATIONS & BOTTLENECK ANALYSIS</div>
                {layers?.destinations?.features?.map((d: any, idx: number) => (
                  <div key={idx} className="p-3.5 rounded-lg bg-slate-950 border border-slate-800 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-sm text-emerald-400">{d.properties.name}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-emerald-950 text-emerald-300 border border-emerald-800">
                        {d.properties.operational_status}
                      </span>
                    </div>
                    <div className="text-xs text-slate-300 flex items-center justify-between font-mono">
                      <span>Effective Capacity: <strong>{d.properties.effective_capacity}</strong></span>
                      <span>Remaining: <strong>{d.properties.remaining_capacity}</strong></span>
                    </div>
                    <div className="p-2 rounded bg-slate-900 text-xs font-mono flex items-center justify-between">
                      <span className="text-slate-400">Limiting Bottleneck:</span>
                      <span className={d.properties.bottleneck_resource === "WATER" ? "text-amber-400 font-bold" : "text-slate-200"}>
                        {d.properties.bottleneck_resource}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* TAB 5: E4 ROUTES & ALLOCATIONS */}
            {activeTab === "E4" && (
              <div className="space-y-3">
                <div className="text-xs font-bold text-slate-300 font-mono">SAFE ROUTE PLANS & CONVOY ASSIGNMENTS</div>
                {layers?.active_routes?.features?.slice(0, 5).map((r: any, idx: number) => (
                  <div key={idx} className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs font-mono space-y-1">
                    <div className="flex items-center justify-between text-blue-400 font-bold">
                      <span>Route Corridor #{idx+1}</span>
                      <span>{r.properties.time_min} mins</span>
                    </div>
                    <div className="text-slate-400">Distance: {r.properties.distance_m}m | Cost: {r.properties.cost}</div>
                  </div>
                ))}
              </div>
            )}

            {/* TAB 6: AUTHORITY OVERRIDE & AUDIT */}
            {activeTab === "OVERRIDE" && (
              <form onSubmit={handleApplyOverride} className="space-y-3 p-1">
                <div className="flex items-center space-x-2 text-indigo-400 font-bold text-xs font-mono">
                  <Lock className="w-3.5 h-3.5" />
                  <span>HUMAN AUTHORITY OPERATIONAL OVERRIDE</span>
                </div>
                <p className="text-xs text-slate-400">
                  Authorized commanders can override automated CP-SAT allocations. All overrides are recorded in the immutable audit log.
                </p>

                <div className="space-y-2 pt-2">
                  <div>
                    <label className="text-[11px] font-mono text-slate-400">Select Allocation / Group</label>
                    <input
                      type="text"
                      placeholder="e.g. ALLOC_001"
                      value={overrideGroupId}
                      onChange={(e) => setOverrideGroupId(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white font-mono mt-1"
                      required
                    />
                  </div>

                  <div>
                    <label className="text-[11px] font-mono text-slate-400">Reassign to Destination</label>
                    <select
                      value={overrideDestId}
                      onChange={(e) => setOverrideDestId(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white font-mono mt-1"
                    >
                      <option value="DEST_01">Vayu Community Center (DEST_01)</option>
                      <option value="DEST_02">District Senior Secondary School (DEST_02)</option>
                      <option value="DEST_03">Hilltop Sports Complex (DEST_03 - High Ground)</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-[11px] font-mono text-slate-400">Operational Justification (Mandatory)</label>
                    <textarea
                      placeholder="e.g. Critical medical dependency requires relocation to High Ground facility."
                      value={overrideJustification}
                      onChange={(e) => setOverrideJustification(e.target.value)}
                      rows={3}
                      className="w-full px-3 py-2 rounded-lg bg-slate-950 border border-slate-800 text-xs text-white font-mono mt-1"
                      required
                    />
                  </div>

                  <button
                    type="submit"
                    className="w-full py-2.5 px-4 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs font-mono transition-all shadow-lg"
                  >
                    CONFIRM & AUDIT OVERRIDE
                  </button>

                  {overrideSuccess && (
                    <div className="p-2.5 rounded bg-emerald-950 border border-emerald-800 text-emerald-300 text-xs font-mono text-center">
                      ✓ Override successfully applied and recorded to Audit Trail!
                    </div>
                  )}
                </div>
              </form>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
