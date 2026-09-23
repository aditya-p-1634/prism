"use client";

import React, { useState, useEffect } from "react";
import { getAllocations, getDestinations, overrideAllocation } from "@/lib/api";
import { useSnapshot } from "@/lib/snapshot-context";
import {
  ShieldAlert,
  CheckCircle2,
  AlertTriangle,
  Building2,
  Users,
  Send,
  History,
  Info,
  ShieldCheck,
  RotateCcw
} from "lucide-react";

export default function OverridesPage() {
  const { snapshotId, showToast } = useSnapshot();
  const [allocations, setAllocations] = useState<any[]>([]);
  const [destinations, setDestinations] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Form State
  const [selectedAllocId, setSelectedAllocId] = useState("");
  const [targetDestId, setTargetDestId] = useState("DEST_03");
  const [justification, setJustification] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [lastOverridden, setLastOverridden] = useState<any>(null);

  const loadAllocationsAndDestinations = async () => {
    try {
      setLoading(true);
      const [allocRes, destRes] = await Promise.all([
        getAllocations(snapshotId),
        getDestinations(snapshotId)
      ]);
      const allocData = allocRes.data || [];
      const destData = destRes.data || [];
      setAllocations(allocData);
      setDestinations(destData);
      if (allocData.length > 0 && !selectedAllocId) {
        setSelectedAllocId(allocData[0].id);
      }
    } catch (err) {
      console.error("Failed to load allocation data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAllocationsAndDestinations();
  }, [snapshotId]);

  const selectedAlloc = allocations.find((a) => a.id === selectedAllocId);
  const targetDest = destinations.find((d) => d.id === targetDestId || d.code === targetDestId);

  const handleSubmitOverride = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!justification.trim()) {
      showToast("Mandatory justification required for human authority override.", "warning");
      return;
    }
    try {
      setSubmitting(true);
      const res = await overrideAllocation(selectedAllocId, targetDestId, justification);
      setLastOverridden(res.data);
      showToast(`Allocation overridden to ${targetDest?.name || targetDestId} with immutable audit log.`, "success");
      setJustification("");
      await loadAllocationsAndDestinations();
    } catch (err: any) {
      showToast(`Override failed: ${err.message}`, "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex flex-col gap-5 flex-1 max-w-[1700px] mx-auto w-full">
      {/* Top Header */}
      <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-950/80 border border-indigo-800/60 flex items-center justify-center">
            <ShieldAlert className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">
              Human-in-the-Loop Authority Override Workspace
            </h1>
            <div className="text-xs text-slate-400 font-mono">
              Role: DEMO AUTHORITY (District Authority) | Snapshot:{" "}
              <span className="text-indigo-400 font-semibold">{snapshotId}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="px-2.5 py-1 rounded-lg bg-indigo-950 text-indigo-300 border border-indigo-800">
            PRISM Recommends → Human Authorizes → Immutable Audit Log
          </span>
        </div>
      </div>

      {/* Main Grid: Form & Allocations Table */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Interactive Intervention Form (5 Cols) */}
        <div className="lg:col-span-5 rounded-2xl border border-slate-800 bg-[#0c121d] p-5 shadow-xl space-y-4">
          <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
            <ShieldCheck className="w-4 h-4 text-indigo-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Intervention Command Form
            </h2>
          </div>

          <form onSubmit={handleSubmitOverride} className="space-y-4 text-xs font-mono">
            {/* Step 1: Select Household Group */}
            <div className="space-y-1.5">
              <label className="text-slate-300 font-semibold flex items-center justify-between">
                <span>1. Target Relocation Group:</span>
                <span className="text-slate-500 font-normal">Select Group / Household</span>
              </label>
              <select
                value={selectedAllocId}
                onChange={(e) => setSelectedAllocId(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-indigo-500 font-sans text-xs"
              >
                {allocations.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.habitation_name} — {a.assigned_capacity_count} persons ({a.allocation_status})
                  </option>
                ))}
              </select>
            </div>

            {/* Current Recommendation Inspector */}
            {selectedAlloc && (
              <div className="p-3.5 rounded-xl bg-slate-900/80 border border-slate-800 space-y-2">
                <span className="text-[10px] text-slate-400 font-bold uppercase">
                  CURRENT SYSTEM RECOMMENDATION:
                </span>
                <div className="flex justify-between text-slate-300">
                  <span>Assigned Shelter:</span>
                  <span className="font-bold text-cyan-300">
                    {selectedAlloc.destination_name || "UNMET DEMAND"}
                  </span>
                </div>
                <div className="flex justify-between text-slate-300">
                  <span>Origin Habitation:</span>
                  <span className="text-slate-200">{selectedAlloc.habitation_name}</span>
                </div>
                <div className="flex justify-between text-slate-300">
                  <span>Headcount:</span>
                  <span className="text-slate-200">{selectedAlloc.assigned_capacity_count} persons</span>
                </div>
                <div className="flex justify-between text-slate-300">
                  <span>Allocation Status:</span>
                  <span className="font-semibold text-emerald-400">{selectedAlloc.allocation_status}</span>
                </div>
                <div className="text-[11px] text-slate-400 truncate">
                  Reason: {selectedAlloc.reason_code}
                </div>
              </div>
            )}

            {/* Step 2: Target Destination */}
            <div className="space-y-1.5">
              <label className="text-slate-300 font-semibold">
                2. Reassign to Authorized Shelter:
              </label>
              <select
                value={targetDestId}
                onChange={(e) => setTargetDestId(e.target.value)}
                className="w-full p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-200 focus:outline-none focus:border-indigo-500 font-sans text-xs"
              >
                {destinations.map((d) => {
                  const rem = d.capacity_state?.remaining_capacity ?? 0;
                  return (
                    <option key={d.id} value={d.id}>
                      {d.code} — {d.name} (Remaining: {rem} people)
                    </option>
                  );
                })}
              </select>
            </div>

            {/* Step 3: Mandatory Justification */}
            <div className="space-y-1.5">
              <label className="text-slate-300 font-semibold flex items-center justify-between">
                <span>3. Mandatory Operational Justification:</span>
                <span className="text-amber-400 text-[10px]">* Required for Audit</span>
              </label>
              <textarea
                rows={3}
                value={justification}
                onChange={(e) => setJustification(e.target.value)}
                placeholder="e.g., Tactical field convoy re-routing due to local bridge blockage; authorized under District Disaster Directive D-26191."
                className="w-full p-2.5 rounded-xl bg-slate-900 border border-slate-800 text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 font-sans text-xs"
              />
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={submitting}
              className="w-full py-2.5 px-4 rounded-xl bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white font-bold text-xs shadow-lg shadow-indigo-600/25 flex items-center justify-center space-x-2 transition-all disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              <span>
                {submitting ? "PERSISTING OVERRIDE & AUDIT RECORD..." : "COMMIT OFFICIAL AUTHORITY OVERRIDE"}
              </span>
            </button>
          </form>

          {lastOverridden && (
            <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-800/60 text-emerald-300 text-xs font-mono space-y-1">
              <div className="flex items-center space-x-1.5 font-bold">
                <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                <span>Override Persisted to Database</span>
              </div>
              <div className="text-[11px] text-slate-300">
                Allocation updated to status: <span className="font-bold">{lastOverridden.allocation_status}</span>
              </div>
            </div>
          )}
        </div>

        {/* Right Column: Active Relocation Allocations Matrix (7 Cols) */}
        <div className="lg:col-span-7 rounded-2xl border border-slate-800 bg-[#0c121d] p-5 shadow-xl space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center space-x-2">
              <History className="w-4 h-4 text-emerald-400" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                Active Relocation Allocations & Overrides ({allocations.length})
              </h2>
            </div>
            <span className="text-[11px] font-mono text-slate-400">
              Live State Matrix
            </span>
          </div>

          <div className="overflow-x-auto max-h-[560px] overflow-y-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-900/80 text-slate-400 uppercase text-[10px] border-b border-slate-800 sticky top-0">
                <tr>
                  <th className="p-2.5">Origin</th>
                  <th className="p-2.5">Headcount</th>
                  <th className="p-2.5">Assigned Destination</th>
                  <th className="p-2.5">Status</th>
                  <th className="p-2.5">Reason Code / Justification</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {allocations.map((a) => {
                  const isOverridden = a.allocation_status === "OVERRIDDEN";
                  return (
                    <tr
                      key={a.id}
                      onClick={() => setSelectedAllocId(a.id)}
                      className={`cursor-pointer transition-colors ${
                        isOverridden
                          ? "bg-indigo-950/30 text-indigo-200"
                          : a.id === selectedAllocId
                          ? "bg-slate-800/40"
                          : "hover:bg-slate-900/30 text-slate-300"
                      }`}
                    >
                      <td className="p-2.5 font-bold text-white">{a.habitation_name}</td>
                      <td className="p-2.5">{a.assigned_capacity_count}</td>
                      <td className="p-2.5 text-cyan-300 font-semibold">{a.destination_name}</td>
                      <td className="p-2.5">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                            isOverridden
                              ? "bg-indigo-950 text-indigo-300 border border-indigo-700"
                              : "bg-emerald-950 text-emerald-300 border border-emerald-800"
                          }`}
                        >
                          {a.allocation_status}
                        </span>
                      </td>
                      <td className="p-2.5 text-[11px] text-slate-400 truncate max-w-[200px]">
                        {a.reason_code}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
