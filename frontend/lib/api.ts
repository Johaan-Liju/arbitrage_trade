export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/${path}`, { signal, cache: "no-store" });
  if (!response.ok) {
    let message = `Local API returned HTTP ${response.status}. Check that the backend is running on port 8000.`;
    try { const body = await response.json(); if (typeof body.detail === "string") message = body.detail; } catch { /* Proxy failures may be plain text. */ }
    throw new Error(message);
  }
  return response.json();
}
