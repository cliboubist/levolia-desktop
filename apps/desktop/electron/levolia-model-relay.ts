export interface RelayRegistryConnection {
  authMode?: string
  kind?: string
  token?: unknown
  url?: unknown
}

export interface RelayServerConnection {
  authMode: 'oauth' | 'token'
  token: string
  url: string
}

export function findRelayServerConnection(
  connections: RelayRegistryConnection[],
  decrypt: (value: unknown) => string
): RelayServerConnection | null {
  const remote = connections.find(
    connection =>
      connection?.kind === 'remote' && typeof connection.url === 'string' && connection.url.trim().length > 0
  )

  if (!remote) {
    return null
  }

  const authMode = remote.authMode === 'oauth' ? 'oauth' : 'token'
  const token = authMode === 'token' && remote.token ? decrypt(remote.token) : ''

  if (authMode === 'token' && !token) {
    return null
  }

  return {
    authMode,
    token,
    url: String(remote.url).replace(/\/+$/, '')
  }
}
