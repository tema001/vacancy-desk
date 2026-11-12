export async function readErrorDetail(response: Response): Promise<string | null> {
  try {
    const body = (await response.json()) as { detail?: unknown }
    return typeof body.detail === 'string' ? body.detail : null
  } catch {
    return null
  }
}

export async function toResponseError(
  response: Response,
  errorMessage: string,
): Promise<Error> {
  const detail = await readErrorDetail(response)
  return new Error(detail ?? `${errorMessage} (${response.status})`)
}

export async function fetchJson<T>(
  url: string,
  init?: RequestInit,
  errorMessage = 'Request failed',
): Promise<T> {
  const response = await fetch(url, init)

  if (!response.ok) {
    throw await toResponseError(response, errorMessage)
  }

  return (await response.json()) as T
}

export async function fetchOk(
  url: string,
  init?: RequestInit,
  errorMessage = 'Request failed',
): Promise<void> {
  const response = await fetch(url, init)

  if (!response.ok) {
    throw await toResponseError(response, errorMessage)
  }
}

export function jsonInit(method: string, body?: unknown): RequestInit {
  return {
    method,
    headers: { 'Content-Type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  }
}
