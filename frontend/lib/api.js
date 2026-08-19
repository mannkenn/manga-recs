// In the deployed image FastAPI serves this bundle, so the API lives on the same
// origin and the base URL is empty. For `next dev` against a separately running
// backend, set NEXT_PUBLIC_API_BASE=http://localhost:8000.
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '';

export async function fetchHealth() {
  const response = await fetch(`${API_BASE}/health`);
  if (!response.ok) throw new Error(`Health check failed with status ${response.status}`);
  return response.json();
}

export async function fetchRecommendations({ title, topN, signal }) {
  const response = await fetch(`${API_BASE}/recommendations/`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title, top_n: topN }),
    signal,
  });

  let payload = null;
  try {
    payload = await response.json();
  } catch {
    // A non-JSON body (a proxy error page, say) should not mask the status.
    throw new Error(`Request failed with status ${response.status}`);
  }

  if (!response.ok) {
    throw new Error(payload?.detail || `Request failed with status ${response.status}`);
  }
  return payload;
}
