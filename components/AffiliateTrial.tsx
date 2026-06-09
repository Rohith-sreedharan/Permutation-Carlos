/**
 * Phase 13 — Affiliate Trial Landing Page
 * =========================================
 * Route: /ref/:affiliateId
 *
 * Stripe.js Elements integration:
 * - Stripe.js loaded in index.html (<script src="https://js.stripe.com/v3/">)
 * - window.Stripe(VITE_STRIPE_PUBLISHABLE_KEY) initialised on mount
 * - stripe.elements() mounts a CardElement into #stripe-card-element div
 * - stripe.createPaymentMethod() called on submit — returns real pm_xxx ID
 * - pm_xxx + stripe_customer_id POSTed to /api/trial/affiliate/start
 * - Backend calls stripe.PaymentMethod.retrieve(pm_xxx) to get card fingerprint
 * - Fingerprint used for deduplication (Part 2 of spec)
 *
 * SECURITY:
 * - No raw card data ever touches our code — all card handling by Stripe.js
 * - display_name HTML-encoded by backend, rendered as React text (no innerHTML)
 * - All values from JSON response, never from raw URL parameters
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { getToken } from '../services/api';

// Stripe.js global type — loaded via <script> in index.html
declare global {
  interface Window {
    Stripe?: (key: string) => StripeInstance;
  }
}
interface StripeInstance {
  elements: (opts?: object) => StripeElements;
  createPaymentMethod: (opts: object) => Promise<{ paymentMethod?: { id: string }; error?: { message: string } }>;
  createCustomer?: (opts: object) => Promise<{ customer?: { id: string }; error?: { message: string } }>;
}
interface StripeElements {
  create: (type: string, opts?: object) => StripeElement;
}
interface StripeElement {
  mount: (selector: string | HTMLElement) => void;
  unmount: () => void;
  on: (event: string, handler: (event: unknown) => void) => void;
}

const STRIPE_PK = (import.meta as unknown as Record<string, Record<string, string>>).env?.VITE_STRIPE_PUBLISHABLE_KEY || '';

interface TrialPageData {
  affiliate_id: string;
  display_name: string;
  trial_duration_hours: number;
  platform_price: string;
  charge_disclosure: string;
  charge_display: string;
  trial_ends_at_utc: string;
  timezone_used: string;
  timezone_note: string;
  offer_expires_at_utc: string;
  turnstile_site_key: string;
}

interface AffiliateTrialProps {
  affiliateId: string;
}

type ViewState =
  | 'loading'
  | 'form'
  | 'processing'
  | 'success'
  | 'already_used'
  | 'expired'
  | 'error';

function formatCountdown(expiryMs: number): string {
  if (!Number.isFinite(expiryMs) || expiryMs <= 0) return '';
  const diff = Math.max(0, expiryMs - Date.now());
  if (diff === 0) return 'Expired';
  const m = Math.ceil(diff / 60000);  // round up so "1 minute" shows until 0
  return m === 1 ? '1 minute' : `${m} minutes`;
}

export default function AffiliateTrial({ affiliateId }: AffiliateTrialProps) {
  const [view, setView] = useState<ViewState>('loading');
  const [pageData, setPageData] = useState<TrialPageData | null>(null);
  const [countdown, setCountdown] = useState<string>('');
  const [expiryMs, setExpiryMs] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [trialResult, setTrialResult] = useState<{ trial_ends_at: string; charge_display: string } | null>(null);
  const [nearExpiry, setNearExpiry] = useState(false);
  const [cardError, setCardError] = useState<string>('');
  const [cardComplete, setCardComplete] = useState(false);

  // Stripe.js refs
  const stripeRef = useRef<StripeInstance | null>(null);
  const cardElementRef = useRef<StripeElement | null>(null);
  const cardMountRef = useRef<HTMLDivElement | null>(null);

  // ── Load page data from backend ───────────────────────────────────────
  useEffect(() => {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    fetch(`/api/trial/affiliate/${encodeURIComponent(affiliateId)}?tz=${encodeURIComponent(tz)}`)
      .then(r => r.json())
      .then((data: TrialPageData) => {
        setPageData(data);
        // Use server-computed expiry anchored to clicked_at_utc in bv_ref cookie —
        // accurate remaining time, not a fixed countdown from page load.
        const expiryTime = new Date(data.offer_expires_at_utc).getTime();
        setExpiryMs(expiryTime);
        setCountdown(formatCountdown(expiryTime));
        setView('form');
      })
      .catch(() => {
        setView('error');
        setErrorMessage('Unable to load this offer. Please try again later.');
      });
  }, [affiliateId]);

  // ── Mount Stripe CardElement once form is visible ─────────────────────────
  useEffect(() => {
    if (view !== 'form') return;
    if (!cardMountRef.current) return;

    // Wait for Stripe.js to load (it's async in index.html)
    const initStripe = () => {
      if (!window.Stripe) {
        setTimeout(initStripe, 100);
        return;
      }

      const pk = STRIPE_PK;
      if (!pk) {
        console.warn('[AffiliateTrial] VITE_STRIPE_PUBLISHABLE_KEY not set — Stripe Elements not mounted');
        return;
      }

      const stripe = window.Stripe(pk);
      stripeRef.current = stripe;

      const elements = stripe.elements({
        // Match the BeatVegas dark theme
        appearance: {
          theme: 'night',
          variables: {
            colorPrimary: '#bc993c',
            colorBackground: '#0c141f',
            colorText: '#f2f3ec',
            colorDanger: '#e53e3e',
            fontFamily: 'Roboto, sans-serif',
            borderRadius: '8px',
          },
        },
      });

      const card = elements.create('card', {
        hidePostalCode: false,
        style: {
          base: {
            color: '#f2f3ec',
            fontFamily: 'Roboto, sans-serif',
            fontSize: '16px',
            '::placeholder': { color: '#4a5568' },
          },
          invalid: { color: '#e53e3e' },
        },
      });

      cardElementRef.current = card;

      if (cardMountRef.current) {
        card.mount(cardMountRef.current);
      }

      card.on('change', (event: unknown) => {
        const e = event as { error?: { message: string }; complete?: boolean };
        setCardError(e.error?.message || '');
        setCardComplete(e.complete || false);
      });

      console.log('[AffiliateTrial] Stripe CardElement mounted');
    };

    initStripe();

    return () => {
      if (cardElementRef.current) {
        try { cardElementRef.current.unmount(); } catch { /* ignore */ }
        cardElementRef.current = null;
      }
    };
  }, [view]);

  // ── Countdown ticker (60-second update — informational only) ──────────────
  useEffect(() => {
    if (!expiryMs) return;
    const interval = setInterval(() => {
      const diff = Math.max(0, expiryMs - Date.now());
      const remaining = formatCountdown(expiryMs);
      setCountdown(remaining);
      // Show gentle near-expiry prompt at 5 minutes remaining
      if (diff <= 5 * 60 * 1000 && diff > 0) setNearExpiry(true);
      if (remaining === 'Expired') {
        setView('expired');
        clearInterval(interval);
      }
    }, 60000);
    return () => clearInterval(interval);
  }, [expiryMs]);

  // ── Form submission ────────────────────────────────────────────────
  const handleStartTrial = useCallback(async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!pageData || !stripeRef.current || !cardElementRef.current) {
      setErrorMessage('Card entry not ready. Please wait a moment and try again.');
      return;
    }
    setErrorMessage('');

    const authToken = getToken();

    // Device fingerprint (OWASP-safe: no sensitive fields, browser-observable only)
    const deviceFingerprint = [
      navigator.userAgent,
      screen.width,
      screen.height,
      Intl.DateTimeFormat().resolvedOptions().timeZone,
    ].join('|');

    try {
      // ── Step 1: Create PaymentMethod via Stripe.js ─────────────────────────
      // card data NEVER leaves Stripe's servers — we get back a pm_xxx token
      // NOTE: setView('processing') is called AFTER createPaymentMethod so the
      // CardElement iframe stays mounted during tokenisation. Unmounting it first
      // causes Stripe to lose the iframe communication channel (network error).
      const { paymentMethod, error: pmError } = await stripeRef.current.createPaymentMethod({
        type: 'card',
        card: cardElementRef.current,
      });

      if (pmError || !paymentMethod) {
        setErrorMessage(pmError?.message || 'Card verification failed. Please check your details.');
        return;
      }

      // Now safe to show processing state (card element no longer needed)
      setView('processing');

      // Log pm_xxx to console for evidence capture (dev/staging)
      console.log('[AffiliateTrial] PaymentMethod created:', paymentMethod.id);

      // ── Step 2: Get Turnstile token (if site key present) ────────────────
      const turnstileToken = (document.querySelector('[name="cf-turnstile-response"]') as HTMLInputElement)?.value || '';

      // ── Step 3: POST to backend ────────────────────────────────────────
      // stripe_customer_id is created/retrieved server-side from stripe_customer_id
      // in the user's account. For new users the backend creates it via Stripe API.
      const resp = await fetch('/api/trial/affiliate/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
        },
        body: JSON.stringify({
          affiliate_id: affiliateId,
          payment_method_id: paymentMethod.id,  // real pm_xxx from Stripe.js
          device_fingerprint: deviceFingerprint,
          turnstile_token: turnstileToken,
        }),
      });

      const result = await resp.json();

      if (resp.status === 409) {
        setView('already_used');
        return;
      }

      if (!resp.ok) {
        setView('form');
        setErrorMessage(result.detail || 'Unable to start trial. Please try again.');
        return;
      }

      setTrialResult({
        trial_ends_at: result.trial_ends_at,
        charge_display: result.charge_display,
      });
      setView('success');

      // Redirect to dashboard after 3s
      setTimeout(() => { window.location.href = '/'; }, 3000);

    } catch {
      setView('form');
      setErrorMessage('A network error occurred. Please try again.');
    }
  }, [affiliateId, pageData]);

  // ───────────────────────────────────────────────────────────────────────────────
  // Render states
  // ───────────────────────────────────────────────────────────────────────────────

  if (view === 'loading') {
    return (
      <div className="min-h-screen bg-[#0c141f] flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-[#bc993c] border-t-transparent rounded-full" />
      </div>
    );
  }

  if (view === 'already_used') {
    return (
      <div className="min-h-screen bg-[#0c141f] flex items-center justify-center p-6">
        <div className="max-w-md w-full text-center">
          <img src="/logo.png" alt="BeatVegas" className="w-32 mx-auto mb-8" />
          <div className="bg-[#1e2d3d] rounded-2xl p-8">
            <div className="text-4xl mb-4">⚠️</div>
            <h2 className="text-white text-xl font-bold mb-3">Trial Already Used</h2>
            <p className="text-[#afb6bb] text-sm leading-relaxed mb-6">
              A trial for this account has already been used. Each account is eligible
              for one trial period.
            </p>
            <a href="/" className="block w-full bg-[#bc993c] text-[#0c141f] py-3 rounded-xl font-bold text-center">
              Back to BeatVegas
            </a>
          </div>
        </div>
      </div>
    );
  }

  if (view === 'expired') {
    return (
      <div className="min-h-screen bg-[#0c141f] flex items-center justify-center p-6">
        <div className="max-w-md w-full text-center">
          <img src="/logo.png" alt="BeatVegas" className="w-32 mx-auto mb-8" />
          <div className="bg-[#1e2d3d] rounded-2xl p-8">
            <div className="text-4xl mb-4">⏱️</div>
            <h2 className="text-white text-xl font-bold mb-3">Offer Expired</h2>
            <p className="text-[#afb6bb] text-sm leading-relaxed mb-6">
              This offer has expired. Scan the QR code again for a fresh trial.
            </p>
            <a href="/" className="block w-full bg-[#bc993c] text-[#0c141f] py-3 rounded-xl font-bold text-center">
              Back to BeatVegas
            </a>
          </div>
        </div>
      </div>
    );
  }

  if (view === 'success') {
    return (
      <div className="min-h-screen bg-[#0c141f] flex items-center justify-center p-6">
        <div className="max-w-md w-full text-center">
          <img src="/logo.png" alt="BeatVegas" className="w-32 mx-auto mb-8" />
          <div className="bg-[#1e2d3d] rounded-2xl p-8">
            <div className="text-4xl mb-4">✅</div>
            <h2 className="text-[#bc993c] text-2xl font-bold mb-3">Trial Started!</h2>
            <p className="text-white text-sm leading-relaxed mb-2">Your 3-day free trial has started.</p>
            <p className="text-[#afb6bb] text-sm mb-6">
              Your card will be charged <strong className="text-white">$97/month</strong>{' '}
              on <strong className="text-white">{trialResult?.charge_display}</strong>{' '}
              unless you cancel first.
            </p>
            <p className="text-[#afb6bb] text-xs">Redirecting to your dashboard…</p>
          </div>
        </div>
      </div>
    );
  }

  // ── Main form (includes Stripe CardElement mount) ──────────────────────────

  return (
    <div className="min-h-screen bg-[#0c141f] flex items-center justify-center p-6">
      <div className="max-w-md w-full">

        <div className="text-center mb-8">
          <img src="/logo.png" alt="BeatVegas" className="w-32 mx-auto mb-4" />
        </div>

        {/* Countdown timer — informational only (FINDING-13-03 compliant) */}
        {/* 12px, rgba(255,255,255,0.6), no urgency language, no red, no animation */}
        {countdown && countdown !== 'Expired' && (
          <div className="text-center mb-4">
            <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.6)' }}>
              Offer valid for {countdown}
            </span>
          </div>
        )}
        {nearExpiry && countdown && (
          <div className="text-center mb-2">
            <span style={{ fontSize: '12px', color: 'rgba(255,255,255,0.6)' }}>
              Complete your sign-up now to claim your free trial
            </span>
          </div>
        )}

        <div className="bg-[#131c2b] border border-[#1e2d3d] rounded-2xl p-8">

          {/* Headline — Part 3.1 */}
          <h1 className="text-[#bc993c] text-3xl font-black text-center mb-2">3 Days Free</h1>

          {/* Referral attribution — HTML-encoded by backend, rendered as React text */}
          <p className="text-[#afb6bb] text-sm text-center mb-6">
            Referred by{' '}
            <span className="text-white font-semibold">
              {pageData?.display_name ?? 'a BeatVegas subscriber'}
            </span>
          </p>

          {/* Charge timing disclosure — Part 3.4, FTC Negative Option Rule 2024 */}
          {pageData?.charge_disclosure && (
            <div className="bg-[#0c141f] border border-[#1e2d3d] rounded-xl p-4 mb-6 text-center">
              <p className="text-[#afb6bb] text-xs leading-relaxed">{pageData.charge_disclosure}</p>
              {pageData.timezone_note && (
                <p className="text-[#6b7784] text-xs mt-1">{pageData.timezone_note}</p>
              )}
            </div>
          )}

          <form onSubmit={handleStartTrial} className="space-y-4">

            {/* Stripe CardElement mount point — card data handled entirely by Stripe.js */}
            <div
              className="bg-[#0c141f] border border-[#1e2d3d] rounded-xl p-4 min-h-[54px]"
              id="stripe-card-element"
              ref={cardMountRef}
            />

            {/* Stripe card error */}
            {cardError && (
              <p className="text-red-400 text-xs px-1">{cardError}</p>
            )}

            {/* Cloudflare Turnstile — Part 11.4 (invisible on modern browsers) */}
            {pageData?.turnstile_site_key && (
              <div
                className="cf-turnstile"
                data-sitekey={pageData.turnstile_site_key}
                data-theme="dark"
                data-size="invisible"
              />
            )}

            {/* Form-level error */}
            {errorMessage && (
              <p className="text-red-400 text-xs px-1">{errorMessage}</p>
            )}

            {/* CTA — Part 3.1: 48px, gold, full width */}
            <button
              type="submit"
              disabled={view === 'processing' || !cardComplete}
              className="w-full bg-[#bc993c] hover:bg-[#d4aa42] disabled:opacity-50
                         text-[#0c141f] font-black text-lg py-[14px] rounded-xl
                         transition-colors duration-150"
              style={{ minHeight: '48px' }}
            >
              {view === 'processing' ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="animate-spin w-5 h-5 border-2 border-[#0c141f] border-t-transparent rounded-full" />
                  Starting…
                </span>
              ) : (
                'START FREE ACCESS'
              )}
            </button>

            <p className="text-[#6b7784] text-xs text-center">
              No charge until{' '}
              <span className="text-[#afb6bb]">{pageData?.charge_display}</span>.
              Cancel any time before then and pay nothing.
            </p>
          </form>

          {/* FTC affiliate disclosure — Part 3.5 */}
          <div className="mt-6 pt-6 border-t border-[#1e2d3d]">
            <p className="text-[#6b7784] text-xs leading-relaxed">
              This page includes an affiliate referral. BeatVegas may pay a commission
              to the referring subscriber. This does not affect your subscription price.
            </p>
          </div>
        </div>

        {/* NCPG footer */}
        <div className="mt-6 text-center">
          <p className="text-[#4a5568] text-xs">
            BeatVegas provides statistical simulation outputs only — not betting advice.
          </p>
          <p className="text-[#4a5568] text-xs mt-1">
            Problem gambling help:{' '}
            <a href="tel:18005224700" className="text-[#6b7784]">1-800-522-4700</a>
            {' '}|{' '}
            <a href="https://www.ncpgambling.org" target="_blank" rel="noopener noreferrer" className="text-[#6b7784]">
              ncpgambling.org
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
