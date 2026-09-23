"use client";

import React, { useState, useEffect } from "react";
import { getHabitations, getPriorities } from "@/lib/api";
import { useSnapshot } from "@/lib/snapshot-context";
import {
  Users,
  Search,
  Filter,
  AlertTriangle,
  HelpCircle,
  Accessibility,
  Baby,
  HeartPulse,
  Info,
  ArrowUpDown,
  CheckCircle2
} from "lucide-react";

export default function PopulationPage() {
  const { snapshotId, isBaseline } = useSnapshot();
  const [habitations, setHabitations] = useState<any[]>([]);
  const [priorities, setPriorities] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState("");
  const [filterHabitation, setFilterHabitation] = useState("ALL");
  const [filterTier, setFilterTier] = useState("ALL");
  const [selectedRecord, setSelectedRecord] = useState<any>(null);

  useEffect(() => {
    const fetchPopulationData = async () => {
      try {
        setLoading(true);
        setError(null);
        const [habRes, prioRes] = await Promise.all([
          getHabitations(snapshotId),
          getPriorities(snapshotId)
        ]);
        setHabitations(habRes.data || []);
        setPriorities(prioRes.data || []);
      } catch (err: any) {
        setError(err.message || "Failed to load population vulnerability data");
      } finally {
        setLoading(false);
      }
    };
    fetchPopulationData();
  }, [snapshotId]);

  if (loading && priorities.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] space-y-3">
        <div className="w-10 h-10 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin" />
        <div className="text-slate-400 font-mono text-xs">
          CALCULATING VULNERABILITY SCORES (E2)...
        </div>
      </div>
    );
  }

  // Filtered List
  const filteredList = priorities.filter((p) => {
    const matchesSearch =
      p.household_code?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      p.habitation_name?.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesHabitation =
      filterHabitation === "ALL" || p.habitation_id === filterHabitation;
    const matchesTier = filterTier === "ALL" || p.priority_class === filterTier;
    return matchesSearch && matchesHabitation && matchesTier;
  });

  return (
    <div className="flex flex-col gap-5 flex-1 max-w-[1700px] mx-auto w-full">
      {/* Top Header */}
      <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-950/80 border border-indigo-800/60 flex items-center justify-center">
            <Users className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">
              Vulnerable Population Prioritization Workspace (Engine 2)
            </h1>
            <div className="text-xs text-slate-400 font-mono">
              Demographic Vulnerability Weighting & Reason Codes | Snapshot:{" "}
              <span className="text-indigo-400 font-semibold">{snapshotId}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 text-slate-300">
            Total Surveyed: <span className="text-cyan-400 font-bold">{priorities.length} Households</span>
          </span>
        </div>
      </div>

      {/* Habitation Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
        {habitations.map((h) => (
          <div key={h.id} className="p-4 rounded-xl bg-[#0c121d] border border-slate-800 shadow-md space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white">{h.name}</span>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-slate-800 text-slate-300">
                {h.code}
              </span>
            </div>

            <div className="text-xs text-slate-400 flex justify-between font-mono">
              <span>Population (Est):</span>
              <span className="text-slate-200 font-semibold">{h.population_estimate}</span>
            </div>
            <div className="text-xs text-slate-400 flex justify-between font-mono">
              <span>Elevation:</span>
              <span className="text-slate-200 font-semibold">{h.elevation_m}m</span>
            </div>

            <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] font-mono">
              <span className="text-rose-400 font-semibold">
                Imm: {h.priority_breakdown?.IMMEDIATE || 0}
              </span>
              <span className="text-amber-400">
                Early: {h.priority_breakdown?.SHORT_TERM || 0}
              </span>
              <span className="text-slate-400">
                Med: {h.priority_breakdown?.MEDIUM_TERM || 0}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Search & Filter Toolbar */}
      <div className="p-3.5 rounded-xl bg-[#0c121d] border border-slate-800 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center space-x-2 flex-1 min-w-[240px]">
          <div className="relative w-full max-w-sm">
            <Search className="w-3.5 h-3.5 absolute left-3 top-2.5 text-slate-500" />
            <input
              type="text"
              placeholder="Search household code or habitation..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-200 text-xs focus:outline-none focus:border-indigo-500"
            />
          </div>
        </div>

        <div className="flex items-center space-x-3 font-mono">
          <div className="flex items-center space-x-1.5">
            <span className="text-slate-400">Habitation:</span>
            <select
              value={filterHabitation}
              onChange={(e) => setFilterHabitation(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-slate-200 focus:outline-none"
            >
              <option value="ALL">All Habitations</option>
              {habitations.map((h) => (
                <option key={h.id} value={h.id}>
                  {h.name} ({h.code})
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center space-x-1.5">
            <span className="text-slate-400">Priority Tier:</span>
            <select
              value={filterTier}
              onChange={(e) => setFilterTier(e.target.value)}
              className="bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-slate-200 focus:outline-none"
            >
              <option value="ALL">All Tiers</option>
              <option value="IMMEDIATE">Immediate (P ≥ 75)</option>
              <option value="SHORT_TERM">Short-Term (50 ≤ P &lt; 75)</option>
              <option value="MEDIUM_TERM">Medium-Term (P &lt; 50)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Household Prioritization Table & Reason Code Drawer */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Table Column (8 Cols) */}
        <div className="lg:col-span-8 rounded-2xl border border-slate-800 bg-[#0c121d] overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-900/80 text-slate-400 uppercase text-[10px] border-b border-slate-800">
                <tr>
                  <th className="p-3">Household Code</th>
                  <th className="p-3">Habitation</th>
                  <th className="p-3">Size</th>
                  <th className="p-3">Priority Score</th>
                  <th className="p-3">Priority Class</th>
                  <th className="p-3">Vulnerability Indicators</th>
                  <th className="p-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredList.map((p) => {
                  const isImmediate = p.priority_class === "IMMEDIATE";
                  const isShort = p.priority_class === "SHORT_TERM";
                  const isSelected = selectedRecord?.id === p.id;

                  return (
                    <tr
                      key={p.id}
                      onClick={() => setSelectedRecord(p)}
                      className={`cursor-pointer transition-colors ${
                        isSelected
                          ? "bg-indigo-950/40"
                          : isImmediate
                          ? "hover:bg-rose-950/20"
                          : "hover:bg-slate-800/30"
                      }`}
                    >
                      <td className="p-3 font-bold text-white flex items-center space-x-2">
                        <span>{p.household_code}</span>
                        {p.has_partial_data && (
                          <span className="text-[9px] px-1 py-0.5 rounded bg-amber-950 text-amber-300 border border-amber-800/60">
                            PARTIAL
                          </span>
                        )}
                      </td>
                      <td className="p-3 text-slate-300">{p.habitation_name}</td>
                      <td className="p-3 text-slate-400">{p.member_count}</td>
                      <td className="p-3">
                        <span
                          className={`font-bold ${
                            p.priority_score >= 75
                              ? "text-rose-400"
                              : p.priority_score >= 50
                              ? "text-amber-400"
                              : "text-slate-300"
                          }`}
                        >
                          {p.priority_score.toFixed(1)}
                        </span>
                      </td>
                      <td className="p-3">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            isImmediate
                              ? "bg-rose-950 text-rose-300 border border-rose-800"
                              : isShort
                              ? "bg-amber-950 text-amber-300 border border-amber-800"
                              : "bg-slate-800 text-slate-300 border border-slate-700"
                          }`}
                        >
                          {p.priority_class}
                        </span>
                      </td>
                      <td className="p-3">
                        <div className="flex items-center space-x-1.5 text-slate-400">
                          {p.vulnerable_elderly > 0 && (
                            <span className="flex items-center space-x-0.5 text-indigo-300 text-[10px]" title="Elderly">
                              <HeartPulse className="w-3 h-3" />
                              <span>{p.vulnerable_elderly}</span>
                            </span>
                          )}
                          {p.vulnerable_children > 0 && (
                            <span className="flex items-center space-x-0.5 text-cyan-300 text-[10px]" title="Children">
                              <Baby className="w-3 h-3" />
                              <span>{p.vulnerable_children}</span>
                            </span>
                          )}
                          {p.mobility_impaired > 0 && (
                            <span className="flex items-center space-x-0.5 text-amber-300 text-[10px]" title="Mobility Impaired">
                              <Accessibility className="w-3 h-3" />
                              <span>{p.mobility_impaired}</span>
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="p-3 text-right">
                        <span className="text-[11px] text-indigo-400 font-semibold hover:underline">
                          Inspect
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        {/* Reason Code & Factor Breakdown Drawer (4 Cols) */}
        <div className="lg:col-span-4 rounded-2xl border border-slate-800 bg-[#0c121d] p-4 shadow-xl space-y-4">
          <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
            <Info className="w-4 h-4 text-indigo-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Why Is This Group Prioritized?
            </h2>
          </div>

          {selectedRecord ? (
            <div className="space-y-3 font-mono text-xs">
              <div className="p-3 rounded-xl bg-slate-900 border border-slate-800">
                <div className="font-bold text-white text-sm">
                  {selectedRecord.household_code}
                </div>
                <div className="text-slate-400 text-[11px]">
                  Habitation: {selectedRecord.habitation_name}
                </div>
                <div className="mt-1 flex items-center space-x-2">
                  <span className="text-rose-400 font-bold">
                    Score: {selectedRecord.priority_score.toFixed(1)}
                  </span>
                  <span className="text-slate-500">|</span>
                  <span className="text-slate-300 font-semibold">
                    {selectedRecord.priority_class}
                  </span>
                </div>
              </div>

              {/* Reason Codes Badge List */}
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                <span className="text-slate-400 text-[11px] font-semibold">
                  ACTIVE REASON CODES:
                </span>
                <div className="space-y-1">
                  {selectedRecord.reason_codes?.map((code: string, idx: number) => (
                    <div
                      key={idx}
                      className="p-1.5 rounded bg-slate-900 border border-slate-800 text-[11px] text-indigo-300 flex items-center space-x-1.5"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                      <span>{code}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Component Factor Breakdown */}
              <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2 text-[11px]">
                <span className="text-slate-400 font-semibold">
                  MATHEMATICAL COMPONENT SCORES:
                </span>
                {Object.entries(selectedRecord.component_scores || {}).map(([k, v]) => (
                  <div key={k} className="flex justify-between border-b border-slate-900 pb-1">
                    <span className="text-slate-400">{k}:</span>
                    <span className="text-slate-200 font-bold">
                      {typeof v === "number" ? v.toFixed(2) : String(v)}
                    </span>
                  </div>
                ))}
              </div>

              {selectedRecord.has_partial_data && (
                <div className="p-2.5 rounded-lg bg-amber-950/40 border border-amber-800/60 text-amber-300 text-[11px]">
                  <strong>Partial Data Warning:</strong> Demographic indicators for this household contain unverified attributes. PRISM engine applies conservative vulnerability risk weighting (UNKNOWN != SAFE).
                </div>
              )}
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-6 space-y-2 text-slate-500">
              <Users className="w-8 h-8 opacity-40" />
              <p className="text-xs font-mono">
                Click any household in the table to inspect its multi-factor mathematical scores and active reason codes.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
