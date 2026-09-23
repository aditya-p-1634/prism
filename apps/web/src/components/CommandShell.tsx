"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSnapshot } from "@/lib/snapshot-context";
import {
  LayoutDashboard,
  Map as MapIcon,
  AlertTriangle,
  Users,
  Building2,
  Navigation,
  GitCompare,
  Layers,
  ShieldCheck,
  FileText,
  History,
  Cpu,
  RotateCcw,
  Sparkles,
  ChevronDown,
  Info,
  CheckCircle2,
  AlertCircle,
  X
} from "lucide-react";

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  tag?: string;
}

const NAV_ITEMS: NavItem[] = [
  { label: "Command Center", href: "/", icon: LayoutDashboard },
  { label: "GIS Workspace", href: "/map", icon: MapIcon },
  { label: "Hazard Intel (E1)", href: "/hazards", icon: AlertTriangle, tag: "E1" },
  { label: "Population & Vulnerability (E2)", href: "/population", icon: Users, tag: "E2" },
  { label: "Capacity & Bottlenecks (E3)", href: "/resources", icon: Building2, tag: "E3" },
  { label: "Safe Routing (E4)", href: "/routing", icon: Navigation, tag: "E4" },
  { label: "Causal Simulation (E5)", href: "/simulation", icon: GitCompare, tag: "E5" },
  { label: "Scenario Registry", href: "/scenarios", icon: Layers },
  { label: "Authority Overrides", href: "/overrides", icon: ShieldCheck },
  { label: "Operational Reports", href: "/reports", icon: FileText },
  { label: "Audit Trail", href: "/audit", icon: History },
  { label: "System Telemetry", href: "/settings", icon: Cpu }
];

export default function CommandShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const {
    snapshotId,
    setSnapshotId,
    snapshots,
    activeSnapshot,
    isBaseline,
    handleResetBaseline,
    scenarioRunning,
    toast
  } = useSnapshot();

  const [snapDropdownOpen, setSnapDropdownOpen] = useState(false);

  return (
    <div className="min-h-screen flex flex-col bg-[#070b12] text-slate-100 font-sans selection:bg-blue-600 selection:text-white">
      {/* Top Operational Header */}
      <header className="h-16 border-b border-slate-800/80 bg-[#0c121d]/95 backdrop-blur-md px-4 sm:px-6 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center space-x-3 sm:space-x-4">
          <Link href="/" className="flex items-center space-x-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-blue-600 via-indigo-600 to-cyan-500 flex items-center justify-center font-black tracking-wider text-white shadow-lg shadow-blue-500/25 group-hover:scale-105 transition-transform">
              P
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-extrabold text-lg tracking-wider bg-clip-text text-transparent bg-gradient-to-r from-blue-400 via-indigo-200 to-cyan-300">
                  PRISM
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded-full bg-blue-950/80 text-blue-300 border border-blue-800/60 font-mono font-medium">
                  SIH 26191
                </span>
              </div>
              <div className="text-[10px] text-slate-400 font-mono tracking-tight hidden md:block">
                Predictive Relocation & Infrastructure Safety Matrix
              </div>
            </div>
          </Link>

          {/* National Scalability Context Breadcrumbs */}
          <div className="hidden xl:flex items-center pl-4 border-l border-slate-800/80 text-[11px] text-slate-400 space-x-1 font-mono">
            <span className="text-slate-500">IND</span>
            <span>/</span>
            <span className="text-slate-500">Uttarakhand</span>
            <span>/</span>
            <span className="text-slate-500">Dehradun Dist</span>
            <span>/</span>
            <span className="text-cyan-400 font-medium px-2 py-0.5 rounded bg-cyan-950/60 border border-cyan-800/40">
              Vayu River Basin — Synthetic Demonstration Study Area
            </span>
          </div>
        </div>

        {/* Right Section: Snapshot Selector, Status Badges, Authority Profile */}
        <div className="flex items-center space-x-2 sm:space-x-3">
          {/* Active Snapshot Badge / Dropdown */}
          <div className="relative">
            <button
              onClick={() => setSnapDropdownOpen(!snapDropdownOpen)}
              className={`flex items-center space-x-2 px-2.5 py-1 rounded-lg text-xs font-mono border transition-all ${
                isBaseline
                  ? "bg-emerald-950/40 border-emerald-800/60 text-emerald-300 hover:bg-emerald-900/30"
                  : "bg-blue-950/50 border-blue-700/60 text-blue-300 hover:bg-blue-900/40"
              }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${
                  isBaseline ? "bg-emerald-400" : "bg-cyan-400 animate-pulse"
                }`}
              />
              <span className="font-semibold uppercase tracking-wider">
                {isBaseline ? "BASELINE" : "SCENARIO"}
              </span>
              <span className="text-[10px] opacity-75 hidden sm:inline">
                ({snapshotId.slice(0, 12)}...)
              </span>
              <ChevronDown className="w-3.5 h-3.5 opacity-70" />
            </button>

            {snapDropdownOpen && (
              <div className="absolute right-0 mt-2 w-72 bg-[#0d1422] border border-slate-700 rounded-xl shadow-2xl p-2 z-50 text-xs font-sans">
                <div className="px-2 py-1 text-[11px] font-mono text-slate-400 border-b border-slate-800 flex items-center justify-between">
                  <span>ACTIVE SNAPSHOT STATE</span>
                  <button
                    onClick={() => setSnapDropdownOpen(false)}
                    className="hover:text-white"
                  >
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
                <div className="max-h-60 overflow-y-auto py-1 space-y-1">
                  {snapshots.map((s) => (
                    <button
                      key={s.id}
                      onClick={() => {
                        setSnapshotId(s.id);
                        setSnapDropdownOpen(false);
                      }}
                      className={`w-full text-left p-2 rounded-lg transition-all ${
                        s.id === snapshotId
                          ? "bg-blue-600/30 border border-blue-500/50 text-white"
                          : "hover:bg-slate-800/60 text-slate-300"
                      }`}
                    >
                      <div className="font-medium flex items-center justify-between">
                        <span>{s.snapshot_type}</span>
                        <span className="text-[10px] font-mono text-slate-400">
                          {s.id === "SNAP_BASE_001" ? "IMMUTABLE" : "DERIVED"}
                        </span>
                      </div>
                      <div className="text-[11px] text-slate-400 truncate">{s.label}</div>
                    </button>
                  ))}
                </div>

                {!isBaseline && (
                  <div className="pt-2 border-t border-slate-800">
                    <button
                      onClick={() => {
                        handleResetBaseline();
                        setSnapDropdownOpen(false);
                      }}
                      className="w-full flex items-center justify-center space-x-1.5 py-1.5 px-3 rounded-lg bg-emerald-950/60 border border-emerald-800/60 text-emerald-300 hover:bg-emerald-900/60 text-xs font-medium"
                    >
                      <RotateCcw className="w-3.5 h-3.5" />
                      <span>Restore Canonical Baseline</span>
                    </button>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Decision Support Mode Badge */}
          <div className="hidden lg:flex items-center space-x-1.5 px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-800 text-[11px] font-mono text-slate-300">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span>DECISION SUPPORT MODE</span>
          </div>

          {/* Human-in-the-Loop Authority Profile */}
          <div className="flex items-center space-x-2.5 pl-2 sm:pl-3 border-l border-slate-800/80">
            <div className="text-right hidden sm:block">
              <div className="text-xs font-semibold text-slate-200">DEMO AUTHORITY</div>
              <div className="text-[10px] text-indigo-400 font-mono tracking-tight">
                ROLE: DISTRICT AUTHORITY
              </div>
            </div>
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-900 to-slate-900 border border-indigo-700/60 flex items-center justify-center font-bold text-xs text-indigo-300 shadow-inner">
              DA
            </div>
          </div>
        </div>
      </header>

      {/* Main Body with Sidebar + Viewport */}
      <div className="flex-1 flex overflow-hidden">
        {/* Persistent Operational Navigation Sidebar */}
        <aside className="w-64 border-r border-slate-800/80 bg-[#090e17] flex flex-col shrink-0 overflow-y-auto">
          <div className="p-3">
            <div className="text-[10px] font-mono uppercase tracking-wider text-slate-400 px-3 py-1 font-semibold">
              Operational Navigation (12 Modules)
            </div>
            <nav className="mt-1 space-y-1">
              {NAV_ITEMS.map((item) => {
                const Icon = item.icon;
                const active = pathname === item.href;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all group ${
                      active
                        ? "bg-blue-600 text-white font-semibold shadow-md shadow-blue-600/20"
                        : "text-slate-400 hover:text-slate-200 hover:bg-slate-800/50"
                    }`}
                  >
                    <div className="flex items-center space-x-2.5">
                      <Icon
                        className={`w-4 h-4 transition-colors ${
                          active ? "text-white" : "text-slate-400 group-hover:text-blue-400"
                        }`}
                      />
                      <span>{item.label}</span>
                    </div>
                    {item.tag && (
                      <span
                        className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                          active
                            ? "bg-blue-700 text-blue-100"
                            : "bg-slate-800 text-slate-400 border border-slate-700/60"
                        }`}
                      >
                        {item.tag}
                      </span>
                    )}
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* Quick Engine Status Footer */}
          <div className="mt-auto p-3 border-t border-slate-800/80 bg-[#070b12]/60">
            <div className="text-[10px] font-mono text-slate-400 mb-2 flex items-center justify-between">
              <span>E1–E6 BACKBONE</span>
              <span className="text-emerald-400 font-semibold">ONLINE</span>
            </div>
            <div className="grid grid-cols-6 gap-1 text-[9px] font-mono text-center">
              {["E1", "E2", "E3", "E4", "E5", "E6"].map((e) => (
                <div
                  key={e}
                  className="py-1 rounded bg-slate-900 border border-slate-800 text-slate-300 font-medium"
                >
                  {e}
                </div>
              ))}
            </div>
            <div className="mt-2 text-[10px] text-slate-400 font-mono truncate">
              CRS: EPSG:4326 | SQLite DB
            </div>
          </div>
        </aside>

        {/* Viewport Content Area */}
        <main className="flex-1 flex flex-col overflow-y-auto p-4 sm:p-6 bg-[#070b12]">
          {children}
        </main>
      </div>

      {/* Global Toast Notification */}
      {toast && (
        <div className="fixed bottom-5 right-5 z-50 flex items-center space-x-3 px-4 py-3 rounded-xl bg-slate-900 border border-slate-700 shadow-2xl text-xs max-w-md animate-in slide-in-from-bottom-2">
          {toast.type === "success" && <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />}
          {toast.type === "error" && <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />}
          {toast.type === "warning" && <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />}
          {toast.type === "info" && <Info className="w-4 h-4 text-blue-400 shrink-0" />}
          <span className="text-slate-200">{toast.message}</span>
        </div>
      )}
    </div>
  );
}
