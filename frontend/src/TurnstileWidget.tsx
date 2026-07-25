import { useEffect, useRef } from 'react'

declare global {
  interface Window {
    turnstile?: {
      render: (container: HTMLElement, options: Record<string, unknown>) => string
      remove: (widgetId: string) => void
    }
  }
}

const SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY ?? ''

interface TurnstileWidgetProps {
  onVerify: (token: string) => void
  onExpire?: () => void
}

/**
 * Thin wrapper around Cloudflare's imperative Turnstile widget. Mount a
 * fresh instance (change the `key` prop) to get a new token after a failed
 * or completed upload attempt — tokens are single-use.
 */
export function TurnstileWidget({ onVerify, onExpire }: TurnstileWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const widgetIdRef = useRef<string | null>(null)
  const onVerifyRef = useRef(onVerify)
  const onExpireRef = useRef(onExpire)
  onVerifyRef.current = onVerify
  onExpireRef.current = onExpire

  useEffect(() => {
    if (!SITE_KEY || !containerRef.current) return undefined

    let cancelled = false
    let pollInterval: ReturnType<typeof setInterval> | undefined

    function renderWidget() {
      if (cancelled || !window.turnstile || !containerRef.current) return
      widgetIdRef.current = window.turnstile.render(containerRef.current, {
        sitekey: SITE_KEY,
        callback: (token: string) => onVerifyRef.current(token),
        'expired-callback': () => onExpireRef.current?.(),
        theme: 'dark',
      })
    }

    if (window.turnstile) {
      renderWidget()
    } else {
      pollInterval = setInterval(() => {
        if (window.turnstile) {
          if (pollInterval) clearInterval(pollInterval)
          renderWidget()
        }
      }, 100)
    }

    return () => {
      cancelled = true
      if (pollInterval) clearInterval(pollInterval)
      if (widgetIdRef.current && window.turnstile) {
        window.turnstile.remove(widgetIdRef.current)
      }
    }
  }, [])

  if (!SITE_KEY) {
    return <p className="text-xs text-neutral-600">Turnstile isn't configured for this environment.</p>
  }

  return <div ref={containerRef} />
}
