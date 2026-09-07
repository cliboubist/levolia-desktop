import { useEffect, useState } from 'react'

import { getLevoliaGoogleAuthUrl, getLevoliaGoogleStatus, submitLevoliaGoogleCode } from '@/api/levolia-google'
import { BrandMark } from '@/components/brand-mark'
import { Button } from '@/components/ui/button'
import { useI18n } from '@/i18n'
import { AlertCircle, Check, Loader2 } from '@/lib/icons'

/**
 * LevoliaGoogleCard — optional post-connection step.
 *
 * Shown once the gateway is up, only when the server has Google credentials
 * provisioned for this client and no Google account is authorized yet. "Later"
 * hides it for good on this computer; the connection can still be made from
 * the settings. Never blocks the app.
 */
const DISMISS_KEY = 'levolia.google.dismissed'

function readDismissed(): boolean {
  try {
    return window.localStorage.getItem(DISMISS_KEY) === '1'
  } catch {
    return false
  }
}

function writeDismissed(): void {
  try {
    window.localStorage.setItem(DISMISS_KEY, '1')
  } catch {
    // Storage unavailable: the card simply reappears next launch.
  }
}

type Phase = 'hidden' | 'offer' | 'connecting' | 'done' | 'error'

export function LevoliaGoogleCard({ enabled }: { enabled: boolean }) {
  const { t } = useI18n()
  const copy = t.levoliaGoogle
  const [phase, setPhase] = useState<Phase>('hidden')
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!enabled || readDismissed()) {
      return
    }

    let cancelled = false

    getLevoliaGoogleStatus()
      .then(status => {
        if (!cancelled && status.available && !status.authorized) {
          setPhase('offer')
        }
      })
      .catch(() => {
        // Older or unreachable server: no Google step.
      })

    return () => {
      cancelled = true
    }
  }, [enabled])

  if (phase === 'hidden') {
    return null
  }

  const dismiss = () => {
    writeDismissed()
    setPhase('hidden')
  }

  const connect = async () => {
    setPhase('connecting')
    setError(null)

    try {
      const { url } = await getLevoliaGoogleAuthUrl()
      const consent = window.hermesDesktop?.levoliaGoogleConsent

      if (!consent) {
        throw new Error('Desktop bridge unavailable')
      }

      const result = await consent(url)

      if (!result?.code) {
        if (result?.error === 'closed') {
          setError(copy.cancelled)
          setPhase('error')

          return
        }

        throw new Error(result?.error || 'no-code')
      }

      const outcome = await submitLevoliaGoogleCode(result.code)

      if (!outcome.ok) {
        throw new Error(outcome.detail || 'exchange-failed')
      }

      writeDismissed()
      setPhase('done')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setPhase('error')
    }
  }

  return (
    <div className="fixed inset-x-0 bottom-6 z-(--z-setup) flex justify-center px-4 pointer-events-none">
      <div className="pointer-events-auto w-full max-w-xl rounded-xl border border-(--stroke-nous) bg-card p-5 shadow-nous">
        <div className="flex items-start gap-4">
          <BrandMark className="size-10 shrink-0" />
          <div className="min-w-0 flex-1">
            {phase === 'done' ? (
              <>
                <div className="flex items-center gap-2 text-sm font-semibold">
                  <Check className="size-4 text-emerald-500" />
                  <span>{copy.connectedTitle}</span>
                </div>
                <p className="mt-1 text-sm text-muted-foreground">{copy.connectedBody}</p>
              </>
            ) : (
              <>
                <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{copy.optional}</div>
                <h3 className="mt-0.5 text-base font-semibold tracking-tight">{copy.title}</h3>
                <p className="mt-1 text-sm leading-5 text-muted-foreground">{copy.body}</p>
                {phase === 'error' && error ? (
                  <div className="mt-2 flex items-start gap-2 text-sm text-destructive">
                    <AlertCircle className="mt-0.5 size-4 shrink-0" />
                    <span>
                      {copy.failedTitle}. {error}
                    </span>
                  </div>
                ) : null}
              </>
            )}
          </div>
        </div>

        <div className="mt-4 flex items-center justify-end gap-2">
          {phase === 'done' ? (
            <Button onClick={() => setPhase('hidden')} size="sm">
              {t.common.close}
            </Button>
          ) : (
            <>
              <Button disabled={phase === 'connecting'} onClick={dismiss} size="sm" variant="ghost">
                {copy.later}
              </Button>
              <Button disabled={phase === 'connecting'} onClick={() => void connect()} size="sm">
                {phase === 'connecting' ? <Loader2 className="size-4 animate-spin" /> : null}
                {phase === 'connecting' ? copy.connecting : copy.connect}
              </Button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
