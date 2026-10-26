export async function api<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { signal, cache: "no-store" });
}

export async function post<T>(path: string, body: object, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
}

async function request<T>(path: string, options: RequestInit): Promise<T> {
  const response = await fetch(`/api/${path}`, options);
  if (!response.ok) {
    let message = `Research API returned HTTP ${response.status}. The backend service or its connection needs attention. Retry once the service is available.`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail)) message = body.detail.map((issue: { loc: (string | number)[]; msg: string }) => `${issue.loc.filter(part => part !== "body").join(" / ")}: ${issue.msg}`).join(". ");
    } catch { /* Proxy failures may be plain text. */ }
    throw new Error(message);
  }
  return response.json();
}
