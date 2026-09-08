import { readFileSync } from 'node:fs'

import { describe, expect, it, vi } from 'vitest'

import { findRelayServerConnection } from './levolia-model-relay'

describe('findRelayServerConnection', () => {
  it('keeps an OAuth server even though it has no static token', () => {
    const decrypt = vi.fn()

    expect(
      findRelayServerConnection(
        [
          { kind: 'local' },
          { kind: 'remote', url: 'https://client.levolia.ai/', authMode: 'oauth' }
        ],
        decrypt
      )
    ).toEqual({ authMode: 'oauth', token: '', url: 'https://client.levolia.ai' })
    expect(decrypt).not.toHaveBeenCalled()
  })

  it('decrypts and requires the static token for token-authenticated servers', () => {
    expect(
      findRelayServerConnection(
        [{ kind: 'remote', url: 'https://client.levolia.ai', authMode: 'token', token: 'encrypted' }],
        value => (value === 'encrypted' ? 'relay-token' : '')
      )
    ).toEqual({ authMode: 'token', token: 'relay-token', url: 'https://client.levolia.ai' })

    expect(
      findRelayServerConnection(
        [{ kind: 'remote', url: 'https://client.levolia.ai', authMode: 'token' }],
        () => ''
      )
    ).toBeNull()
  })

  it('configures the local relay before waiting for inference-ready WebSocket state', () => {
    const source = readFileSync(new URL('./main.ts', import.meta.url), 'utf8')
    const localBoot = source.indexOf('Starting Levolia backend for profile')
    const sync = source.indexOf('await syncLocalModelFromLevoliaServer', localBoot)
    const bootStart = source.lastIndexOf('const authToken = await adoptServedDashboardToken', sync)
    const probe = source.indexOf('const wsProbe = await probeGatewayWebSocket', sync)

    expect(localBoot).toBeGreaterThan(-1)
    expect(bootStart).toBeGreaterThan(-1)
    expect(sync).toBeGreaterThan(bootStart)
    expect(probe).toBeGreaterThan(sync)
  })
})
