"use client";

import React, { useState, useEffect } from "react";
import { getScenarios, getSnapshots } from "@/lib/api";
import { useSnapshot } from "@/lib/snapshot-context";
import {
  Layers,
  Play,
  RotateCcw,
  Sliders,
  CheckCircle2,
  Clock,
  AlertTriangle,
  ArrowRight,
  Sparkles
} from "lucide-react";

export default function ScenariosPage() {
  const {
    snapshotId,
    setSnapshotId,
    runMonsoonScenario,
    handleResetBaseline,
    scenarioRunning,
    snapshots
  } = useSnapshot();

  const [scenarios, setScenarios] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Parameter Customization State
  const [rainfallDelta, setRainfallDelta] = useState(0.20);
  const [riverLevelDelta, setRiverLevelDelta] = useState(0.50);
  const [closeBridge, setCloseBridge] = useState(true);
  const [waterReduction, setWaterReduction] = useState(0.75);

  const [lastDelta, setLastDelta] = useState<any>(null);

  useEffect(() => {
    const fetchScenarios = async () => {
      try {
        setLoading(true);
        const res = await getScenarios();
        setScenarios(res.data || []);
      } catch (err) {
        console.error("Failed to load scenarios:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchScenarios();
  }, []);

  const handleExecuteWithOverrides = async () => {
    try {
      const overrides: Record<string, any> = {
        rainfall_multiplier_delta: rainfallDelta,
        river_level_delta_m: riverLevelDelta,
        closed_road_segments: closeBridge ? ["BRIDGE_01"] : [],
        resource_capacity_reductions: {
          DEST_02: { WATER: waterReduction }
        }
      };
      const delta = await runMonsoonScenario(overrides);
      setLastDelta(delta);
    } catch (err) {
      // toast shown in context
    }
  };

  return (
    <div className="flex flex-col gap-5 flex-1 max-w-[1700px] mx-auto w-full">
      {/* Top Header */}
      <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-blue-950/80 border border-blue-800/60 flex items-center justify-center">
            <Layers className="w-5 h-5 text-blue-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">
              Scenario Registry & Dynamic Adaptation Engine
            </h1>
            <div className="text-xs text-slate-400 font-mono">
              Branching Multi-Hazard Simulation Catalog | Active Snapshot:{" "}
              <span className="text-blue-400 font-semibold">{snapshotId}</span>
            </div>
          </div>
        </div>

        <button
          onClick={handleResetBaseline}
          className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium border border-slate-700 transition-all font-mono"
        >
          <RotateCcw className="w-3.5 h-3.5 text-slate-400" />
          <span>Reset All to Baseline</span>
        </button>
      </div>

      {/* Main Grid: Catalog & Parameter Tuner */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Registered Canonical Scenario & Customizer (7 Cols) */}
        <div className="lg:col-span-7 flex flex-col gap-5">
          {/* Canonical Scenario Card */}
          <div className="p-5 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-blue-950 text-blue-300 border border-blue-800 font-semibold">
                  CANONICAL BENCHMARK SCENARIO
                </span>
                <h2 className="text-base font-bold text-white mt-1.5">
                  MONSOON_SURGE_01: Severe Monsoon Flash Flood & Critical Infrastructure Failure
                </h2>
              </div>
              <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            </div>

            <p className="text-xs text-slate-300 leading-relaxed font-sans">
              Models compound extreme conditions: sudden 20% precipitation surge over Vayu basin catchments, a +0.50m river stage surge, physical collapse of strategic BRIDGE_01 across the river channel corridor, and a 25% potable water degradation at District Senior Secondary School (DEST_02).
            </p>

            {/* Interactive Parameter Tuner */}
            <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800 space-y-4 font-mono text-xs">
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <div className="flex items-center space-x-2 text-cyan-400 font-bold">
                  <Sliders className="w-4 h-4" />
                  <span>SIMULATION PARAMETER CONTROLS</span>
                </div>
                <span className="text-[10px] text-slate-400">Affects CP-SAT solver inputs</span>
              </div>

              {/* Slider 1: Rainfall Multiplier Delta */}
              <div className="space-y-1">
                <div className="flex justify-between text-slate-300">
                  <span>Rainfall Multiplier Delta:</span>
                  <span className="text-cyan-400 font-bold">+{(rainfallDelta * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="0.50"
                  step="0.05"
                  value={rainfallDelta}
                  onChange={(e) => setRainfallDelta(parseFloat(e.target.value))}
                  className="w-full accent-cyan-500 cursor-pointer"
                />
              </div>

              {/* Slider 2: River Stage Delta */}
              <div className="space-y-1">
                <div className="flex justify-between text-slate-300">
                  <span>River Level Delta (m):</span>
                  <span className="text-blue-400 font-bold">+{riverLevelDelta.toFixed(2)}m</span>
                </div>
                <input
                  type="range"
                  min="0.0"
                  max="1.50"
                  step="0.10"
                  value={riverLevelDelta}
                  onChange={(e) => setRiverLevelDelta(parseFloat(e.target.value))}
                  className="w-full accent-blue-500 cursor-pointer"
                />
              </div>

              {/* Toggle 3: Bridge 01 Closure */}
              <div className="flex items-center justify-between py-1">
                <span className="text-slate-300">Simulate BRIDGE_01 Structural Collapse:</span>
                <input
                  type="checkbox"
                  checked={closeBridge}
                  onChange={(e) => setCloseBridge(e.target.checked)}
                  className="w-4 h-4 accent-rose-500 rounded cursor-pointer"
                />
              </div>

              {/* Slider 4: Water Capacity Factor at DEST_02 */}
              <div className="space-y-1">
                <div className="flex justify-between text-slate-300">
                  <span>DEST_02 Water Capacity Retention:</span>
                  <span className="text-amber-400 font-bold">{(waterReduction * 100).toFixed(0)}%</span>
                </div>
                <input
                  type="range"
                  min="0.25"
                  max="1.0"
                  step="0.05"
                  value={waterReduction}
                  onChange={(e) => setWaterReduction(parseFloat(e.target.value))}
                  className="w-full accent-amber-500 cursor-pointer"
                />
              </div>

              {/* Run Button */}
              <button
                onClick={handleExecuteWithOverrides}
                disabled={scenarioRunning}
                className="w-full mt-2 py-2.5 px-4 rounded-xl bg-gradient-to-r from-blue-600 via-indigo-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-bold text-xs shadow-lg shadow-blue-600/25 flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
              >
                <Play className="w-4 h-4 fill-white" />
                <span>
                  {scenarioRunning
                    ? "PRISM IS RECOMPUTING DECISION CHAIN..."
                    : "EXECUTE DYNAMIC SCENARIO SIMULATION"}
                </span>
              </button>
            </div>
          </div>
        </div>

        {/* Right Column: Snapshots & Lineage History (5 Cols) */}
        <div className="lg:col-span-5 rounded-2xl border border-slate-800 bg-[#0c121d] p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-emerald-400" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                State Snapshot Registry ({snapshots.length})
              </h2>
            </div>
            <span className="text-[10px] font-mono text-slate-400">E6 ACID Lineage</span>
          </div>

          <div className="space-y-2.5 max-h-[560px] overflow-y-auto pr-1">
            {snapshots.map((s) => {
              const isSelected = s.id === snapshotId;
              const isBase = s.id === "SNAP_BASE_001";

              return (
                <div
                  key={s.id}
                  onClick={() => setSnapshotId(s.id)}
                  className={`p-3 rounded-xl border text-xs font-mono cursor-pointer transition-all ${
                    isSelected
                      ? "bg-blue-950/40 border-blue-500/80 text-white shadow-md shadow-blue-500/10"
                      : "bg-slate-900/50 border-slate-800 hover:bg-slate-800/40 text-slate-300"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-white truncate max-w-[70%]">
                      {s.label}
                    </span>
                    <span
                      className={`text-[9px] px-1.5 py-0.5 rounded font-semibold ${
                        isBase
                          ? "bg-emerald-950 text-emerald-300 border border-emerald-800"
                          : "bg-blue-950 text-cyan-300 border border-cyan-800"
                      }`}
                    >
                      {s.snapshot_type}
                    </span>
                  </div>

                  <div className="mt-1 flex items-center justify-between text-[10px] text-slate-400">
                    <span className="truncate">ID: {s.id}</span>
                    <span>{s.created_at?.slice(11, 19)}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
