"use client";

import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import { getSnapshots, runScenario, resetBaseline, getSystemTelemetry } from "./api";

interface Toast {
  message: string;
  type: "info" | "success" | "warning" | "error";
}

interface SystemHealth {
  apiOnline: boolean;
  dbConnected: boolean;
  status: "ONLINE" | "DEGRADED" | "OFFLINE" | "CHECKING";
  fileSizeKb?: number;
  queryLatencyMs?: number;
}

interface SnapshotContextType {
  snapshotId: string;
  setSnapshotId: (id: string) => void;
  snapshots: any[];
  activeSnapshot: any;
  isBaseline: boolean;
  refreshSnapshots: () => Promise<void>;
  runMonsoonScenario: (overrides?: Record<string, any>) => Promise<any>;
  handleResetBaseline: () => Promise<void>;
  scenarioRunning: boolean;
  toast: Toast | null;
  showToast: (message: string, type?: "info" | "success" | "warning" | "error") => void;
  systemHealth: SystemHealth;
  refreshHealth: () => Promise<void>;
}

const SnapshotContext = createContext<SnapshotContextType | undefined>(undefined);

export function SnapshotProvider({ children }: { children: ReactNode }) {
  const [snapshotId, setSnapshotId] = useState<string>("SNAP_BASE_001");
  const [snapshots, setSnapshots] = useState<any[]>([]);
  const [scenarioRunning, setScenarioRunning] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [systemHealth, setSystemHealth] = useState<SystemHealth>({
    apiOnline: false,
    dbConnected: false,
    status: "CHECKING"
  });

  const showToast = (message: string, type: "info" | "success" | "warning" | "error" = "info") => {
    setToast({ message, type });
    setTimeout(() => {
      setToast(null);
    }, 4500);
  };

  const refreshHealth = async () => {
    try {
      const tel = await getSystemTelemetry();
      const dbOk = tel?.database?.connected ?? false;
      setSystemHealth({
        apiOnline: true,
        dbConnected: dbOk,
        status: dbOk ? "ONLINE" : "DEGRADED",
        fileSizeKb: tel?.database?.file_size_kb,
        queryLatencyMs: tel?.measured_telemetry?.query_latency_ms
      });
    } catch (err) {
      setSystemHealth({
        apiOnline: false,
        dbConnected: false,
        status: "OFFLINE"
      });
    }
  };

  const refreshSnapshots = async () => {
    try {
      const res = await getSnapshots();
      const list = res.data || [];
      setSnapshots(list);
    } catch (err: any) {
      // Handled via health check
    }
  };

  useEffect(() => {
    refreshHealth();
    refreshSnapshots();
    const interval = setInterval(refreshHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    refreshSnapshots();
  }, [snapshotId]);

  const activeSnapshot = snapshots.find((s) => s.id === snapshotId) || {
    id: snapshotId,
    label: snapshotId === "SNAP_BASE_001" ? "Canonical Baseline Reality (Pre-Monsoon Flood)" : "Active Scenario Execution",
    snapshot_type: snapshotId === "SNAP_BASE_001" ? "BASELINE" : "SCENARIO",
    is_immutable: true
  };

  const isBaseline = snapshotId === "SNAP_BASE_001";

  const runMonsoonScenario = async (overrides?: Record<string, any>) => {
    try {
      setScenarioRunning(true);
      showToast("PRISM is recomputing the affected decision chain...", "info");
      const res = await runScenario("MONSOON_SURGE_01", overrides || {});
      const delta = res.data;
      await refreshSnapshots();
      await refreshHealth();
      if (delta.scenario_snapshot_id) {
        setSnapshotId(delta.scenario_snapshot_id);
      }
      showToast("Scenario MONSOON_SURGE_01 recomputed successfully.", "success");
      return delta;
    } catch (err: any) {
      showToast(`Scenario execution failed: ${err.message}`, "error");
      throw err;
    } finally {
      setScenarioRunning(false);
    }
  };

  const handleResetBaseline = async () => {
    try {
      showToast("Restoring canonical baseline reality...", "info");
      await resetBaseline();
      await refreshSnapshots();
      await refreshHealth();
      setSnapshotId("SNAP_BASE_001");
      showToast("Canonical baseline restored (SNAP_BASE_001).", "success");
    } catch (err: any) {
      showToast(`Baseline reset failed: ${err.message}`, "error");
    }
  };

  return (
    <SnapshotContext.Provider
      value={{
        snapshotId,
        setSnapshotId,
        snapshots,
        activeSnapshot,
        isBaseline,
        refreshSnapshots,
        runMonsoonScenario,
        handleResetBaseline,
        scenarioRunning,
        toast,
        showToast,
        systemHealth,
        refreshHealth
      }}
    >
      {children}
    </SnapshotContext.Provider>
  );
}

export function useSnapshot() {
  const context = useContext(SnapshotContext);
  if (!context) {
    throw new Error("useSnapshot must be used within a SnapshotProvider");
  }
  return context;
}
