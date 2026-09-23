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
      throw new Error(errorData.detail || `API request failed with status ${res.status}`);
    }
    return await res.json();
  } catch (err: any) {
    console.error(`API Error on ${endpoint}:`, err);
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
