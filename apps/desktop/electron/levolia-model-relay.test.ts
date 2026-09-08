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
})
