"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ArrowRight, CheckCircle2, ClipboardCheck, ShieldAlert, Users } from "lucide-react";
import { getOperatorBriefing, getSpatialEventEvidence } from "@/lib/api";
import { useSnapshot } from "@/lib/snapshot-context";

type Briefing = {
  snapshot: { id: string; label: string; snapshot_type: string; is_immutable: boolean; requires_human_review: boolean };
  situation: { hazard_present: boolean; hazard_type?: string; hazard_severity?: number; hazard_confidence?: number; red_zone_count: number; status: string };
  decision_summary: Record<string, number>;
  top_priority_groups: Array<Record<string, any>>;
  warnings: Array<{ code: string; severity: string; message: string }>;
  next_actions: Array<{ code: string; priority: string; label: string; reason: string }>;
  integrity: { allocation_is_not_evacuation: boolean; field_confirmation_available: boolean; approval_required: boolean };
};

type SpatialEvidence = {
  telemetry: { rows: number; observed_start: string; observed_end: string };
  historical_event: { event_start: string; event_end: string; temporal_join_status: string; reason: string };
  station: { gcc_points_within_2km: number; nrsc_features_intersecting_station: number };
  interpretation: { operational_claim_allowed: boolean; can_train_supervised_flood_label: boolean; safe_use: string };
};

export default function OperatorBriefingPage() {
  const { snapshotId, showToast } = useSnapshot();
  const [briefing, setBriefing] = useState<Briefing | null>(null);
  const [evidence, setEvidence] = useState<SpatialEvidence | null>(null);
  const [loading, setLoading] = useState(true);

  const loadBriefing = async () => {
    try {
      setLoading(true);
      const [response, evidenceResponse] = await Promise.all([getOperatorBriefing(snapshotId), getSpatialEventEvidence()]);
      setBriefing(response.data);
      setEvidence(evidenceResponse.data);
    } catch (error: any) {
      showToast(error.message || "Unable to load operator briefing", "error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadBriefing(); }, [snapshotId]);

  if (loading && !briefing) {
    return <div className="flex min-h-[500px] items-center justify-center text-xs font-mono text-slate-400">BUILDING OPERATOR BRIEFING...</div>;
  }

  if (!briefing) {
    return <div className="rounded-2xl border border-rose-800/60 bg-rose-950/30 p-6 text-sm text-rose-200">No briefing is available for this snapshot.</div>;
  }

  const summary = briefing.decision_summary;
  const urgent = briefing.warnings.some((warning) => warning.severity === "HIGH");

  return (
    <div className="mx-auto flex w-full max-w-[1500px] flex-col gap-5">
      <section className="rounded-2xl border border-slate-800 bg-[#0c121d] p-5 shadow-xl">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <div className="mb-2 flex items-center gap-2 text-xs font-mono uppercase tracking-wider text-cyan-300">
              <ClipboardCheck className="h-4 w-4" /> Operator decision brief
            </div>
            <h1 className="text-2xl font-bold text-white">What requires attention now?</h1>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-slate-400">
              A read-only summary of the selected snapshot for the district emergency operations planner. Review the evidence, constraints, and next actions before authorizing a plan.
            </p>
          </div>
          <div className={`rounded-xl border px-3 py-2 text-right ${urgent ? "border-rose-800/70 bg-rose-950/30" : "border-emerald-800/70 bg-emerald-950/20"}`}>
            <div className="text-[10px] font-mono uppercase text-slate-400">Situation status</div>
            <div className={`mt-1 text-sm font-bold ${urgent ? "text-rose-300" : "text-emerald-300"}`}>{briefing.situation.status}</div>
            <div className="mt-1 text-[10px] font-mono text-slate-500">{briefing.snapshot.id}</div>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2 text-[11px] font-mono">
          <span className="rounded-full border border-slate-700 bg-slate-900 px-2 py-1 text-slate-300">{briefing.snapshot.snapshot_type}</span>
          {briefing.snapshot.is_immutable && <span className="rounded-full border border-emerald-800 bg-emerald-950/40 px-2 py-1 text-emerald-300">BASELINE IMMUTABLE</span>}
          <span className="rounded-full border border-amber-800 bg-amber-950/30 px-2 py-1 text-amber-300">HUMAN REVIEW REQUIRED</span>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {[
          ["Immediate groups", summary.immediate_groups, "text-rose-300"],
          ["Short-term groups", summary.short_term_groups, "text-amber-300"],
          ["Unmet demand", summary.unmet_groups, summary.unmet_groups ? "text-rose-300" : "text-emerald-300"],
          ["Invalid routes", summary.invalid_routes, summary.invalid_routes ? "text-rose-300" : "text-emerald-300"],
        ].map(([label, value, color]) => (
          <div key={label as string} className="rounded-xl border border-slate-800 bg-[#0c121d] p-4">
            <div className="text-[10px] font-mono uppercase text-slate-500">{label}</div>
            <div className={`mt-2 text-3xl font-extrabold ${color}`}>{value}</div>
          </div>
        ))}
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-2">
        <section className="rounded-2xl border border-slate-800 bg-[#0c121d] p-5">
          <div className="mb-4 flex items-center gap-2 border-b border-slate-800 pb-3 text-xs font-bold uppercase tracking-wider text-slate-200">
            <ShieldAlert className="h-4 w-4 text-amber-400" /> Review before action
          </div>
          <div className="space-y-3">
            {briefing.warnings.length === 0 && <div className="flex items-center gap-2 text-sm text-emerald-300"><CheckCircle2 className="h-4 w-4" /> No blocking warning detected.</div>}
            {briefing.warnings.map((warning) => (
              <div key={warning.code} className="rounded-xl border border-amber-800/60 bg-amber-950/20 p-3">
                <div className="flex items-center gap-2 text-xs font-bold text-amber-300"><AlertTriangle className="h-4 w-4" /> {warning.code}</div>
                <p className="mt-1 text-xs leading-relaxed text-slate-300">{warning.message}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 rounded-xl border border-slate-800 bg-slate-950/50 p-3 text-xs text-slate-400">
            Hazard confidence: <span className="font-mono text-slate-200">{briefing.situation.hazard_confidence ?? "not available"}</span> · Red zones: <span className="font-mono text-slate-200">{briefing.situation.red_zone_count}</span>
          </div>
        </section>

        <section className="rounded-2xl border border-slate-800 bg-[#0c121d] p-5">
          <div className="mb-4 flex items-center gap-2 border-b border-slate-800 pb-3 text-xs font-bold uppercase tracking-wider text-slate-200">
            <ArrowRight className="h-4 w-4 text-cyan-400" /> Next actions
          </div>
          <div className="space-y-2">
            {briefing.next_actions.map((action) => (
              <div key={action.code} className="rounded-xl border border-slate-800 bg-slate-900/60 p-3">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-sm font-semibold text-white">{action.label}</span>
                  <span className="text-[10px] font-mono text-cyan-300">{action.priority}</span>
                </div>
                <p className="mt-1 text-xs text-slate-400">{action.reason}</p>
              </div>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link href="/population" className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800">Inspect population</Link>
            <Link href="/resources" className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800">Inspect capacity</Link>
            <Link href="/routing" className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800">Inspect routes</Link>
          </div>
        </section>
      </div>

      <section className="rounded-2xl border border-slate-800 bg-[#0c121d] p-5">
        <div className="mb-4 flex items-center gap-2 border-b border-slate-800 pb-3 text-xs font-bold uppercase tracking-wider text-slate-200">
          <Users className="h-4 w-4 text-indigo-400" /> Highest-priority groups
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[700px] text-left text-xs">
            <thead className="text-[10px] uppercase text-slate-500"><tr><th className="p-2">Group</th><th className="p-2">Location</th><th className="p-2">Class</th><th className="p-2">Score</th><th className="p-2">Assistance</th><th className="p-2">Data</th></tr></thead>
            <tbody className="divide-y divide-slate-800/70">
              {briefing.top_priority_groups.map((group) => <tr key={group.household_id}>
                <td className="p-2 font-mono text-slate-200">{group.household_code}</td>
                <td className="p-2 text-slate-300">{group.habitation}</td>
                <td className="p-2 text-rose-300">{group.priority_class}</td>
                <td className="p-2 font-mono text-slate-200">{group.priority_score}</td>
                <td className="p-2">{group.assistance_required ? <span className="text-amber-300">Required</span> : <span className="text-slate-500">Self/unknown</span>}</td>
                <td className="p-2">{group.has_partial_data ? <span className="text-amber-300">Partial</span> : <span className="text-emerald-300">Complete</span>}</td>
              </tr>)}
            </tbody>
          </table>
        </div>
      </section>

      <section className="rounded-xl border border-cyan-900/60 bg-cyan-950/20 p-4 text-xs leading-relaxed text-cyan-100">
        <strong>Safety boundary:</strong> relocation allocations are recommendations, not proof of evacuation. Field confirmation is unavailable in this prototype, and approval remains with the human authority.
      </section>

      {evidence && <section className="rounded-2xl border border-violet-900/60 bg-violet-950/20 p-5">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            <div className="text-xs font-bold uppercase tracking-wider text-violet-200">Research evidence · read-only</div>
            <p className="mt-1 text-xs text-violet-100/70">Historical spatial context is displayed separately from live E1–E6 decision state.</p>
          </div>
          <span className="rounded-full border border-amber-700/70 px-2 py-1 text-[10px] font-mono text-amber-200">NON-OPERATIONAL</span>
        </div>
        <div className="grid grid-cols-2 gap-3 text-xs md:grid-cols-4">
          <div><div className="text-violet-100/60">Telemetry rows</div><div className="mt-1 font-mono text-white">{evidence.telemetry.rows.toLocaleString()}</div></div>
          <div><div className="text-violet-100/60">GCC points &lt;2 km</div><div className="mt-1 font-mono text-white">{evidence.station.gcc_points_within_2km}</div></div>
          <div><div className="text-violet-100/60">NRSC station intersections</div><div className="mt-1 font-mono text-white">{evidence.station.nrsc_features_intersecting_station}</div></div>
          <div><div className="text-violet-100/60">Temporal join</div><div className="mt-1 font-mono text-amber-200">{evidence.historical_event.temporal_join_status}</div></div>
        </div>
        <p className="mt-4 text-xs leading-relaxed text-violet-100/80">{evidence.historical_event.reason} This evidence supports {evidence.interpretation.safe_use}; it is not a flood label or an operational forecast.</p>
      </section>}
    </div>
  );
}
