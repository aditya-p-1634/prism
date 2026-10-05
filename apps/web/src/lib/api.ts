export const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function fetchAPI(endpoint: string, options: RequestInit = {}) {
  const url = `${API_BASE}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers
      },
      cache: "no-store"
    });
    if (!res.ok) {
      const errorData = await res.json().catch(() => ({}));
      const msg = errorData.detail || `HTTP Error ${res.status}: ${res.statusText}`;
      const err: any = new Error(msg);
      err.status = res.status;
      throw err;
    }
    return await res.json();
  } catch (err: any) {
    if (err.name === "TypeError" && (err.message === "Failed to fetch" || err.message?.includes("fetch"))) {
      const netErr: any = new Error("PRISM Backend Unreachable. The FastAPI daemon is either starting or offline.");
      netErr.isNetworkError = true;
      throw netErr;
    }
    throw err;
  }
}


// 1. Dashboard Overview
export async function getDashboardOverview(snapshotId: string = "SNAP_BASE_001") {
  return fetchAPI(`/dashboard/overview?snapshot_id=${snapshotId}`);
}

// 2. Snapshots & Lineage
export async function getSnapshots() {
  return fetchAPI(`/snapshots`);
}

export async function resetBaseline() {
  return fetchAPI(`/snapshots/reset`, { method: "POST" });
}

// 3. Scenarios
export async function getScenarios() {
  return fetchAPI(`/scenarios`);
}

export async function runScenario(scenarioCode: string, overrides: Record<string, any> = {}) {
  return fetchAPI(`/scenarios/run`, {
    method: "POST",
    body: JSON.stringify({
      scenario_code: scenarioCode,
      parameter_overrides: overrides
    })
  });
}

// 4. Hazards (E1)
export async function getCurrentHazards(snapshotId: string = "SNAP_BASE_001") {
  return fetchAPI(`/hazards/current?snapshot_id=${snapshotId}`);
}

export async function getRedZones(snapshotId: string = "SNAP_BASE_001") {
  return fetchAPI(`/hazards/red-zones?snapshot_id=${snapshotId}`);
}

// 5. People & Vulnerability (E2)
export async function getHabitations(snapshotId: string = "SNAP_BASE_001") {
  return fetchAPI(`/people/habitations?snapshot_id=${snapshotId}`);
}

export async function getHouseholds(habitationId?: string) {
  const q = habitationId ? `?habitation_id=${habitationId}` : '';
  return fetchAPI(`/people/households${q}`);
}

export async function getPriorities(snapshotId: string = "SNAP_BASE_001") {
  return fetchAPI(`/people/priorities?snapshot_id=${snapshotId}`);
}

// 6. Destinations & Capacity (E3)
export async function getDestinations(snapshotId: string = "SNAP_BASE_001") {
  return fetchAPI(`/destinations?snapshot_id=${snapshotId}`);
}

// 7. Routes & Road Network (E4)
export async function getRoadSegments() {
  return fetchAPI(`/road-segments`);
}

export async function getRoutes(snapshotId: string = "SNAP_BASE_001") {
  return fetchAPI(`/routes?snapshot_id=${snapshotId}`);
}

export async function getAllocations(snapshotId: string = "SNAP_BASE_001") {
  return fetchAPI(`/relocation/allocations?snapshot_id=${snapshotId}`);
}

export async function overrideAllocation(allocationId: string, newDestinationId: string, justification: string) {
  return fetchAPI(`/relocation/override`, {
    method: "POST",
    body: JSON.stringify({
      allocation_id: allocationId,
      new_destination_id: newDestinationId,
      justification
    })
  });
}

// 8. Reports
export async function getReportSummary(snapshotId: string = "SNAP_BASE_001") {
  return fetchAPI(`/reports/summary?snapshot_id=${snapshotId}`);
}

export function getReportExportUrl(reportType: "manifest" | "shelters" | "infrastructure", snapshotId: string = "SNAP_BASE_001") {
  return `${API_BASE}/reports/export?report_type=${reportType}&snapshot_id=${snapshotId}`;
}

// 9. Audit Trail
export async function getAuditEvents(actionType?: string, limit: number = 50) {
  const q = actionType ? `&action_type=${encodeURIComponent(actionType)}` : '';
  return fetchAPI(`/audit/events?limit=${limit}${q}`);
}

// 10. System Telemetry & Health
export async function getSystemTelemetry() {
  return fetchAPI(`/health/telemetry`);
}

// 11. Simulation Observability & Control (Phase A.5)
export async function getSimulationRun(runId: string) {
  return fetchAPI(`/simulation-runs/${runId}`);
}

export async function getSimulationState(runId: string) {
  return fetchAPI(`/simulation-runs/${runId}/state`);
}

export async function getSimulationMetrics(runId: string) {
  return fetchAPI(`/simulation-runs/${runId}/metrics`);
}

export async function getSimulationTimeline(runId: string, limit: number = 50, offset: number = 0, eventType?: string) {
  const q = eventType ? `&event_type=${encodeURIComponent(eventType)}` : '';
  return fetchAPI(`/simulation-runs/${runId}/timeline?limit=${limit}&offset=${offset}${q}`);
}

export async function stepSimulation(runId: string) {
  return fetchAPI(`/simulation-runs/${runId}/step`, { method: "POST" });
}

export async function pauseSimulation(runId: string) {
  return fetchAPI(`/simulation-runs/${runId}/pause`, { method: "POST" });
}

export async function resumeSimulation(runId: string) {
  return fetchAPI(`/simulation-runs/${runId}/resume`, { method: "POST" });
}

export async function cancelSimulation(runId: string) {
  return fetchAPI(`/simulation-runs/${runId}/cancel`, { method: "POST" });
}

// 12. Hazard Prediction & Intelligence (Phase A.6)
export async function createHazardPrediction(data: {
  current_stage_m: number;
  lag1_stage_m?: number;
  rainfall_rate_mmh?: number;
  rolling_rain_30m?: number;
  horizon_minutes?: number;
  model_type?: string;
  simulation_run_id?: string;
  snapshot_id?: string;
  source_time_min?: number;
}) {
  return fetchAPI(`/hazard-predictions`, {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export async function getHazardPrediction(predictionId: string) {
  return fetchAPI(`/hazard-predictions/${predictionId}`);
}

export async function evaluateHazardPrediction(predictionId: string, actualValue: number) {
  return fetchAPI(`/hazard-predictions/${predictionId}/evaluate`, {
    method: "POST",
    body: JSON.stringify({ actual_value: actualValue })
  });
}

export async function getModelBenchmarkMetrics() {
  return fetchAPI(`/hazard-predictions/models/metrics`);
}

export async function getHazardPredictions(params?: { simulation_run_id?: string; snapshot_id?: string; limit?: number }) {
  const query = new URLSearchParams();
  if (params?.simulation_run_id) query.append("simulation_run_id", params.simulation_run_id);
  if (params?.snapshot_id) query.append("snapshot_id", params.snapshot_id);
  if (params?.limit) query.append("limit", params.limit.toString());
  const qs = query.toString() ? `?${query.toString()}` : '';
  return fetchAPI(`/hazard-predictions${qs}`);
}

// -------------------------------------------------------------
// Phase A.7: Real Telemetry Observations & Stations
// -------------------------------------------------------------

export async function getHazardStations(params?: { hazard_type?: string; district?: string; is_active?: boolean }) {
  const query = new URLSearchParams();
  if (params?.hazard_type) query.append("hazard_type", params.hazard_type);
  if (params?.district) query.append("district", params.district);
  if (params?.is_active !== undefined) query.append("is_active", params.is_active.toString());
  const qs = query.toString() ? `?${query.toString()}` : '';
  return fetchAPI(`/hazard-stations${qs}`);
}

export async function getHazardStationCurrentState(stationIdOrCode: string) {
  return fetchAPI(`/hazard-stations/${stationIdOrCode}/current-state`);
}

export async function getHazardObservations(params?: { station_code?: string; quality_status?: string; freshness?: string; limit?: number }) {
  const query = new URLSearchParams();
  if (params?.station_code) query.append("station_code", params.station_code);
  if (params?.quality_status) query.append("quality_status", params.quality_status);
  if (params?.freshness) query.append("freshness", params.freshness);
  if (params?.limit) query.append("limit", params.limit.toString());
  const qs = query.toString() ? `?${query.toString()}` : '';
  return fetchAPI(`/hazard-observations${qs}`);
}

export async function getLatestHazardObservation(stationCode?: string) {
  const query = stationCode ? `?station_code=${stationCode}` : '';
  return fetchAPI(`/hazard-observations/latest${query}`);
}

export async function ingestHazardObservation(data: {
  station_code: string;
  observed_at: string;
  value: number;
  unit?: string;
  source?: string;
  source_dataset?: string;
  raw_reference?: any;
}) {
  return fetchAPI(`/hazard-observations`, {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export async function evaluateHazardObservation(observationId: string, data: {
  snapshot_id: string;
  study_area_id?: string;
  allow_stale?: boolean;
}) {
  return fetchAPI(`/hazard-observations/${observationId}/evaluate`, {
    method: "POST",
    body: JSON.stringify(data)
  });
}

export async function importHazardObservationsCsv(csvContent: string, filename?: string) {
  return fetchAPI(`/hazard-observations/import`, {
    method: "POST",
    body: JSON.stringify({ csv_content: csvContent, filename })
  });
}



