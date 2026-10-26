export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { signal, cache: "no-store" });
}

export async function post<T>(path: string, body: object, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
}

async function request<T>(path: string, options: RequestInit): Promise<T> {
  const response = await fetch(`/api/${path}`, options);
  if (!response.ok) {
<<<<<<< HEAD
    let message = `Research API returned HTTP ${response.status}. The backend service or its connection needs attention. Retry once the service is available.`;
    try { const body = await response.json(); if (typeof body.detail === "string") message = body.detail; } catch { /* Proxy failures may be plain text. */ }
=======
    let message = `Local API returned HTTP ${response.status}. Check that the backend is running on port 8000.`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((issue: { loc: (string | number)[]; msg: string }) => `${issue.loc.filter(part => part !== "body").join(" / ")}: ${issue.msg}`).join(". ");
    } catch { /* Proxy failures may be plain text. */ }
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849
    throw new Error(message);
  }
  return response.json();
}
