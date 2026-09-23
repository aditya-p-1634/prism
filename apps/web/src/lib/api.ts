const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

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

export async function getDashboardOverview(snapshotId: string = "SNAP_BASE_001") {
  return fetchAPI(`/dashboard/overview?snapshot_id=${snapshotId}`);
}

export async function getSnapshots() {
  return fetchAPI(`/snapshots`);
}

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
