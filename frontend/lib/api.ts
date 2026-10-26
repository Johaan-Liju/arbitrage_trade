export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/${path}`, { signal, cache: "no-store" });
  if (!response.ok) {
    let message = `Research API returned HTTP ${response.status}. The backend service or its connection needs attention. Retry once the service is available.`;
    try { const body = await response.json(); if (typeof body.detail === "string") message = body.detail; } catch { /* Proxy failures may be plain text. */ }
    throw new Error(message);
  }
  return response.json();
}
