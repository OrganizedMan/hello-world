export type DomainErrorPayload = {
  code: string;
  message: string;
  action: string;
};


export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly action: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}


export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    const payload = (await response.json()) as DomainErrorPayload;
    throw new ApiError(response.status, payload.code, payload.message, payload.action);
  }
  return (await response.json()) as T;
}


export const api = {
  get<T>(path: string) {
    return requestJson<T>(path);
  },
  post<T>(path: string, body?: unknown) {
    return requestJson<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  },
  upload<T>(path: string, form: FormData) {
    return requestJson<T>(path, { method: "POST", body: form });
  },
};
