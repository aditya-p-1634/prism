"use client";

import React, { useState, useEffect } from "react";
import { getAuditEvents } from "@/lib/api";
import { useSnapshot } from "@/lib/snapshot-context";
import {
  History,
  ShieldCheck,
  Filter,
  Clock,
  User,
  FileCode,
  ArrowRight,
  AlertCircle
} from "lucide-react";

export default function AuditPage() {
  const { snapshotId } = useSnapshot();
  const [events, setEvents] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterAction, setFilterAction] = useState("ALL");
  const [selectedEvent, setSelectedEvent] = useState<any>(null);

  useEffect(() => {
    const fetchAudit = async () => {
      try {
        setLoading(true);
        const actionParam = filterAction === "ALL" ? undefined : filterAction;
        const res = await getAuditEvents(actionParam, 100);
        setEvents(res.events || []);
        if (res.events?.length > 0 && !selectedEvent) {
          setSelectedEvent(res.events[0]);
        }
      } catch (err) {
        console.error("Failed to load audit events:", err);
      } finally {
        setLoading(false);
      }
    };
    fetchAudit();
  }, [filterAction, snapshotId]);

  return (
    <div className="flex flex-col gap-5 flex-1 max-w-[1700px] mx-auto w-full">
      {/* Top Header */}
      <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-indigo-950/80 border border-indigo-800/60 flex items-center justify-center">
            <History className="w-5 h-5 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">
              Tamper-Evident Governance & Audit Trail
            </h1>
            <div className="text-xs text-slate-400 font-mono">
              Immutable Traceability of Operational Changes | Total Events:{" "}
              <span className="text-indigo-400 font-semibold">{events.length}</span>
            </div>
          </div>
        </div>

        {/* Filter Control */}
        <div className="flex items-center space-x-2 text-xs font-mono">
          <span className="text-slate-400">Action Filter:</span>
          <select
            value={filterAction}
            onChange={(e) => setFilterAction(e.target.value)}
            className="bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1 text-slate-200 focus:outline-none"
          >
            <option value="ALL">All Actions</option>
            <option value="AUTHORITY_ALLOCATION_OVERRIDE">Authority Overrides</option>
            <option value="SCENARIO_RUN">Scenario Executions</option>
          </select>
        </div>
      </div>

      {/* Main Grid: Events List & Diff Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        {/* Left Column: Events Table (7 Cols) */}
        <div className="lg:col-span-7 rounded-2xl border border-slate-800 bg-[#0c121d] p-5 shadow-xl space-y-3">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center space-x-2">
              <Clock className="w-4 h-4 text-emerald-400" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
                Audit Event Stream ({events.length})
              </h2>
            </div>
          </div>

          <div className="space-y-2.5 max-h-[620px] overflow-y-auto pr-1">
            {events.length === 0 ? (
              <div className="text-center py-10 text-slate-500 font-mono text-xs">
                No audit events recorded under current filter.
              </div>
            ) : (
              events.map((evt) => {
                const isSelected = selectedEvent?.id === evt.id;
                return (
                  <div
                    key={evt.id}
                    onClick={() => setSelectedEvent(evt)}
                    className={`p-3.5 rounded-xl border text-xs font-mono cursor-pointer transition-all ${
                      isSelected
                        ? "bg-indigo-950/40 border-indigo-500/80 text-white shadow-md shadow-indigo-500/10"
                        : "bg-slate-900/50 border-slate-800 hover:bg-slate-800/40 text-slate-300"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-indigo-400">{evt.action_type}</span>
                      <span className="text-[10px] text-slate-400">
                        {evt.created_at?.replace("T", " ").slice(0, 19)}
                      </span>
                    </div>

                    <div className="mt-1 flex items-center justify-between text-[11px] text-slate-300">
                      <span>
                        Actor: <strong className="text-white">{evt.user_name}</strong> ({evt.user_role})
                      </span>
                      <span className="text-slate-500">Target: {evt.entity_type}</span>
                    </div>

                    {evt.justification && (
                      <div className="mt-1 text-[11px] text-slate-400 italic truncate">
                        &quot;{evt.justification}&quot;
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Event Diff Inspector (5 Cols) */}
        <div className="lg:col-span-5 rounded-2xl border border-slate-800 bg-[#0c121d] p-5 shadow-xl space-y-4">
          <div className="flex items-center space-x-2 border-b border-slate-800 pb-2">
            <FileCode className="w-4 h-4 text-cyan-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Audit Record & State Diff
            </h2>
          </div>

          {selectedEvent ? (
            <div className="space-y-4 text-xs font-mono">
              <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 space-y-1">
                <div className="font-bold text-indigo-300">{selectedEvent.action_type}</div>
                <div className="text-slate-400 text-[11px]">Record ID: {selectedEvent.id}</div>
                <div className="text-slate-400 text-[11px]">
                  Target Entity: {selectedEvent.entity_type} ({selectedEvent.entity_id})
                </div>
                <div className="text-slate-400 text-[11px]">
                  Timestamp: {selectedEvent.created_at}
                </div>
              </div>

              {selectedEvent.justification && (
                <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1">
                  <span className="text-[10px] text-amber-400 font-bold uppercase">
                    MANDATORY OPERATIONAL JUSTIFICATION:
                  </span>
                  <p className="text-slate-200 italic font-sans">
                    &quot;{selectedEvent.justification}&quot;
                  </p>
                </div>
              )}

              {/* Before vs After State Diffs */}
              <div className="space-y-2">
                <span className="text-[11px] text-slate-400 font-semibold">
                  BEFORE STATE SNAPSHOT:
                </span>
                <pre className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 text-rose-300 text-[11px] overflow-x-auto">
                  {JSON.stringify(selectedEvent.before_state, null, 2) || "None (Initial State)"}
                </pre>

                <span className="text-[11px] text-slate-400 font-semibold">
                  AFTER STATE COMMIT:
                </span>
                <pre className="p-3 rounded-xl bg-slate-950 border border-slate-800/80 text-emerald-300 text-[11px] overflow-x-auto">
                  {JSON.stringify(selectedEvent.after_state, null, 2)}
                </pre>
              </div>
            </div>
          ) : (
            <div className="text-center py-12 text-slate-500 font-mono text-xs">
              Select an audit event from the stream to view its cryptographic diff and operational lineage.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
