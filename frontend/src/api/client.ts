// Every state-changing request needs the CSRF header the API's
// CSRFHeaderMiddleware checks for (api/security.py) - a plain cross-site
// <form> POST or a no-cors cross-site fetch cannot attach a custom header,
// so this is what proves a request came from this app's own JS.
const CSRF_HEADER = 'x-mes-client'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const method = (init.method ?? 'GET').toUpperCase()
  const unsafe = method !== 'GET' && method !== 'HEAD'

  // FormData sets its own multipart Content-Type (with the boundary) - the
  // browser only gets that right when the header is left unset entirely.
  const isFormData = init.body instanceof FormData

  const res = await fetch(`/api${path}`, {
    ...init,
    method,
    credentials: 'include', // send/receive the httpOnly mes_session cookie
    headers: {
      ...(init.body && !isFormData ? { 'Content-Type': 'application/json' } : {}),
      ...(unsafe ? { [CSRF_HEADER]: '1' } : {}),
      ...init.headers,
    },
  })

  if (res.status === 204) return undefined as T

  const body = await res.json().catch(() => null)
  if (!res.ok) {
    throw new ApiError(res.status, body?.detail ?? res.statusText)
  }
  return body as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'POST', body: data ? JSON.stringify(data) : undefined }),
  postForm: <T>(path: string, data: FormData) => request<T>(path, { method: 'POST', body: data }),
  put: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'PUT', body: data ? JSON.stringify(data) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
