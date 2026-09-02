const DEFAULT_API_BASE_URL = "http://127.0.0.1:8000";

function getApiBaseUrl(): string {
  return (
    process.env.NOMI_API_BASE_URL ??
    process.env.NEXT_PUBLIC_NOMI_API_BASE_URL ??
    DEFAULT_API_BASE_URL
  ).replace(/\/$/, "");
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  let response: Response;

  try {
    response = await fetch(`${getApiBaseUrl()}${path}`, {
      cache: "no-store",
      headers: { Accept: "application/json" },
    });
  } catch (error) {
    throw new ApiError(
      503,
      error instanceof Error
        ? `Unable to reach the Nomi API: ${error.message}`
        : "Unable to reach the Nomi API.",
    );
  }

  if (!response.ok) {
    let message = `Nomi API returned ${response.status}.`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) message = body.detail;
    } catch {
      // Keep the status-based fallback for non-JSON error responses.
    }
    throw new ApiError(response.status, message);
  }

  return (await response.json()) as T;
}
