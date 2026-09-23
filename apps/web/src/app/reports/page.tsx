"use client";

import React, { useState, useEffect } from "react";
import { getReportSummary, getReportExportUrl } from "@/lib/api";
import { useSnapshot } from "@/lib/snapshot-context";
import {
  FileText,
  Download,
  Printer,
  Users,
  Building2,
  Navigation,
  CheckCircle2,
  AlertTriangle,
  Info
} from "lucide-react";

export default function ReportsPage() {
  const { snapshotId, isBaseline } = useSnapshot();
  const [reportData, setReportData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"manifest" | "shelters" | "infrastructure">("manifest");

  useEffect(() => {
    const fetchReport = async () => {
      try {
        setLoading(true);
        setError(null);
        const res = await getReportSummary(snapshotId);
        setReportData(res);
      } catch (err: any) {
        setError(err.message || "Failed to generate operational report");
      } finally {
        setLoading(false);
      }
    };
    fetchReport();
  }, [snapshotId]);

  const handlePrint = () => {
    window.print();
  };

  if (loading && !reportData) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center min-h-[500px] space-y-3">
        <div className="w-10 h-10 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin" />
        <div className="text-slate-400 font-mono text-xs">
          GENERATING OPERATIONAL MANIFESTS...
        </div>
      </div>
    );
  }

  const summary = reportData?.summary || {};
  const manifest = reportData?.manifest || [];
  const shelters = reportData?.shelters || [];
  const infrastructure = reportData?.infrastructure || [];

  return (
    <div className="flex flex-col gap-5 flex-1 max-w-[1700px] mx-auto w-full">
      {/* Top Header */}
      <div className="p-4 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-cyan-950/80 border border-cyan-800/60 flex items-center justify-center">
            <FileText className="w-5 h-5 text-cyan-400" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white tracking-wide">
              Operational Manifests & Logistics Reports
            </h1>
            <div className="text-xs text-slate-400 font-mono">
              Field-Response Team Operational Rosters | Snapshot:{" "}
              <span className="text-cyan-400 font-semibold">{snapshotId}</span>
            </div>
          </div>
        </div>

        {/* Export & Print Actions */}
        <div className="flex items-center space-x-2 text-xs font-mono">
          <a
            href={getReportExportUrl(activeTab, snapshotId)}
            download
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium shadow-md transition-all"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </a>
          <button
            onClick={handlePrint}
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium border border-slate-700 transition-all"
          >
            <Printer className="w-3.5 h-3.5 text-slate-400" />
            <span>Print View</span>
          </button>
        </div>
      </div>

      {/* Summary KPI Cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3.5 font-mono text-xs">
        <div className="p-3.5 rounded-xl bg-[#0c121d] border border-slate-800">
          <span className="text-slate-400 text-[10px]">TOTAL DEMAND GROUPS</span>
          <div className="text-xl font-bold text-white mt-1">{summary.total_groups}</div>
          <div className="text-[11px] text-slate-400">28 Households (93 people)</div>
        </div>

        <div className="p-3.5 rounded-xl bg-[#0c121d] border border-slate-800">
          <span className="text-slate-400 text-[10px]">ACCOMMODATED GROUPS</span>
          <div className="text-xl font-bold text-emerald-400 mt-1">
            {summary.allocated_groups}
          </div>
          <div className="text-[11px] text-emerald-400/80">
            {summary.total_relocated_headcount} Persons Accommodated
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-[#0c121d] border border-slate-800">
          <span className="text-slate-400 text-[10px]">UNMET DEMAND</span>
          <div
            className={`text-xl font-bold mt-1 ${
              summary.unmet_groups > 0 ? "text-rose-400" : "text-slate-300"
            }`}
          >
            {summary.unmet_groups}
          </div>
          <div className="text-[11px] text-slate-400">
            {summary.unmet_headcount} Persons Unmet
          </div>
        </div>

        <div className="p-3.5 rounded-xl bg-[#0c121d] border border-slate-800">
          <span className="text-slate-400 text-[10px]">CLOSED ROAD SEGMENTS</span>
          <div className="text-xl font-bold text-amber-400 mt-1">
            {summary.closed_roads_count}
          </div>
          <div className="text-[11px] text-amber-400/80">Infrastructure Severances</div>
        </div>
      </div>

      {/* Tab Switcher */}
      <div className="flex border-b border-slate-800 text-xs font-mono space-x-2">
        <button
          onClick={() => setActiveTab("manifest")}
          className={`pb-2 px-3 border-b-2 font-semibold transition-all ${
            activeTab === "manifest"
              ? "border-cyan-500 text-cyan-300"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Evacuation Manifest ({manifest.length})
        </button>

        <button
          onClick={() => setActiveTab("shelters")}
          className={`pb-2 px-3 border-b-2 font-semibold transition-all ${
            activeTab === "shelters"
              ? "border-cyan-500 text-cyan-300"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Shelter Logistics ({shelters.length})
        </button>

        <button
          onClick={() => setActiveTab("infrastructure")}
          className={`pb-2 px-3 border-b-2 font-semibold transition-all ${
            activeTab === "infrastructure"
              ? "border-cyan-500 text-cyan-300"
              : "border-transparent text-slate-400 hover:text-slate-200"
          }`}
        >
          Infrastructure Status ({infrastructure.length})
        </button>
      </div>

      {/* Report Content Panels */}
      <div className="p-5 rounded-2xl bg-[#0c121d] border border-slate-800 shadow-xl overflow-hidden">
        {/* Tab 1: Manifest */}
        {activeTab === "manifest" && (
          <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-900/80 text-slate-400 uppercase text-[10px] border-b border-slate-800 sticky top-0">
                <tr>
                  <th className="p-3">Household</th>
                  <th className="p-3">Habitation</th>
                  <th className="p-3">Headcount</th>
                  <th className="p-3">Priority Class</th>
                  <th className="p-3">Assigned Destination</th>
                  <th className="p-3">Distance (km)</th>
                  <th className="p-3">ETA (min)</th>
                  <th className="p-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {manifest.map((m: any) => (
                  <tr key={m.allocation_id} className="hover:bg-slate-900/40">
                    <td className="p-3 font-bold text-white">{m.household_code}</td>
                    <td className="p-3 text-slate-300">{m.habitation_name}</td>
                    <td className="p-3 text-slate-300">{m.member_count}</td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          m.priority_class === "IMMEDIATE"
                            ? "bg-rose-950 text-rose-300 border border-rose-800"
                            : m.priority_class === "SHORT_TERM"
                            ? "bg-amber-950 text-amber-300 border border-amber-800"
                            : "bg-slate-800 text-slate-300 border border-slate-700"
                        }`}
                      >
                        {m.priority_class}
                      </span>
                    </td>
                    <td className="p-3 text-cyan-300 font-semibold">{m.destination_name}</td>
                    <td className="p-3 text-slate-400">{m.route_distance_km ?? "—"}</td>
                    <td className="p-3 text-slate-400">{m.estimated_time_min ?? "—"}</td>
                    <td className="p-3">
                      <span className="text-emerald-400 font-semibold">{m.status}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 2: Shelters */}
        {activeTab === "shelters" && (
          <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-900/80 text-slate-400 uppercase text-[10px] border-b border-slate-800 sticky top-0">
                <tr>
                  <th className="p-3">Facility Code</th>
                  <th className="p-3">Facility Name</th>
                  <th className="p-3">Effective Capacity</th>
                  <th className="p-3">Occupied</th>
                  <th className="p-3">Remaining</th>
                  <th className="p-3">Utilization</th>
                  <th className="p-3">Limiting Bottleneck</th>
                  <th className="p-3">Safety Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {shelters.map((s: any) => (
                  <tr key={s.destination_id} className="hover:bg-slate-900/40">
                    <td className="p-3 font-bold text-white">{s.destination_code}</td>
                    <td className="p-3 text-slate-300">{s.destination_name}</td>
                    <td className="p-3 text-slate-200 font-bold">{s.effective_capacity}</td>
                    <td className="p-3 text-emerald-400">{s.occupied_capacity}</td>
                    <td className="p-3 text-cyan-400">{s.remaining_capacity}</td>
                    <td className="p-3 text-slate-300">{s.utilization_pct}%</td>
                    <td className="p-3 text-amber-400 font-semibold">{s.bottleneck_resource}</td>
                    <td className="p-3">
                      <span className="text-emerald-400 font-semibold">
                        {s.is_safe ? "VERIFIED SAFE" : "UNSAFE"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 3: Infrastructure */}
        {activeTab === "infrastructure" && (
          <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead className="bg-slate-900/80 text-slate-400 uppercase text-[10px] border-b border-slate-800 sticky top-0">
                <tr>
                  <th className="p-3">Segment Code</th>
                  <th className="p-3">Road Class</th>
                  <th className="p-3">Length (m)</th>
                  <th className="p-3">Is Bridge?</th>
                  <th className="p-3">Operational Status</th>
                  <th className="p-3">Hazard Risk Score</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {infrastructure.map((i: any) => (
                  <tr key={i.segment_code} className="hover:bg-slate-900/40">
                    <td className="p-3 font-bold text-white">{i.segment_code}</td>
                    <td className="p-3 text-slate-300">{i.road_class}</td>
                    <td className="p-3 text-slate-400">{i.length_meters}</td>
                    <td className="p-3 text-slate-300">{i.is_bridge ? "YES" : "NO"}</td>
                    <td className="p-3">
                      <span
                        className={`font-semibold ${
                          i.operational_status === "CLOSED" ? "text-rose-400" : "text-emerald-400"
                        }`}
                      >
                        {i.operational_status}
                      </span>
                    </td>
                    <td className="p-3 text-slate-400">{i.hazard_risk_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
