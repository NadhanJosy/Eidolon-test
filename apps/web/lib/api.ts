const DEFAULT_LOCAL_API_BASE_URL = "http://localhost:8000";
const configuredApiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();

export class ApiError extends Error {
  status: number;
  debugMessage: string;

  constructor(message: string, status: number, debugMessage = message) {
    super(message);
    this.status = status;
    this.debugMessage = debugMessage;
  }
}

export function getApiBaseUrl(): string {
  if (configuredApiBaseUrl) {
    return trimTrailingSlash(configuredApiBaseUrl);
  }

  if (typeof window !== "undefined") {
    const inferredCodespacesUrl = inferCodespacesApiBaseUrl(window.location);
    if (inferredCodespacesUrl) {
      return inferredCodespacesUrl;
    }
  }

  return DEFAULT_LOCAL_API_BASE_URL;
}

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const apiBaseUrl = getApiBaseUrl();
  const headers = new Headers(options.headers);

  try {
    return await fetch(`${apiBaseUrl}${path}`, {
      ...options,
      headers,
      cache: "no-store",
      credentials: "include"
    });
  } catch (caught) {
    throw new ApiError(
      "Eidolon cannot reach its private service right now. Check that the backend is running and try again.",
      0,
      networkFailureDebugMessage(apiBaseUrl, path, caught)
    );
  }
}

export async function apiJson<T>(
  path: string,
  options: RequestInit & { token?: string | null } = {}
): Promise<T> {
  const headers = new Headers(options.headers);
  headers.set("Content-Type", "application/json");
  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  const response = await apiFetch(path, {
    ...options,
    headers
  });
  if (!response.ok) {
    throw await apiErrorFromResponse(response, path);
  }
  return (await response.json()) as T;
}

export async function apiErrorFromResponse(response: Response, path: string): Promise<ApiError> {
  const detail = await readErrorDetail(response);
  return new ApiError(detail, response.status, `Eidolon API ${response.status} on ${path}: ${detail}`);
}

function inferCodespacesApiBaseUrl(location: Pick<Location, "hostname" | "protocol">) {
  const match = location.hostname.match(/^(.+)-\d+\.app\.github\.dev$/);
  if (!match) {
    return null;
  }
  return `${location.protocol}//${match[1]}-8000.app.github.dev`;
}

async function readErrorDetail(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((item) => {
          if (
            typeof item === "object" &&
            item !== null &&
            "msg" in item &&
            typeof item.msg === "string"
          ) {
            return item.msg;
          }
          return JSON.stringify(item);
        })
        .join("; ");
    }
  } catch {
    return "The backend answered, but not in a useful shape.";
  }
  return "The backend did not accept that request.";
}

function networkFailureDebugMessage(apiBaseUrl: string, path: string, caught: unknown): string {
  const browserMessage = caught instanceof Error ? caught.message : "network error";
  return `Could not reach ${apiBaseUrl}${path}. Browser reported: ${browserMessage}.`;
}

function trimTrailingSlash(value: string) {
  return value.replace(/\/$/, "");
}
