import { hermesApi } from './client'

// Levolia: optional Google Workspace connection (hermes_cli/levolia_google.py).

export interface LevoliaGoogleStatus {
  available: boolean
  authorized: boolean
  detail?: string
}

export function getLevoliaGoogleStatus(): Promise<LevoliaGoogleStatus> {
  return hermesApi<LevoliaGoogleStatus>({ path: '/api/levolia/google/status', timeoutMs: 20_000 })
}

export function getLevoliaGoogleAuthUrl(): Promise<{ url: string }> {
  return hermesApi<{ url: string }>({ path: '/api/levolia/google/auth-url', method: 'POST', body: {}, timeoutMs: 30_000 })
}

export function submitLevoliaGoogleCode(code: string): Promise<{ ok: boolean; detail?: string }> {
  return hermesApi<{ ok: boolean; detail?: string }>({
    path: '/api/levolia/google/auth-code',
    method: 'POST',
    body: { code },
    timeoutMs: 60_000
  })
}
