import React, { useState } from 'react';
import { apiRequest } from '../services/api';

/**
 * Waitlist Page — Phase 2B.4
 * Public route at /waitlist — no authentication required.
 * Uses the existing /api/waitlist/join backend endpoint.
 */
export default function WaitlistPage() {
  const [email, setEmail] = useState('');
  const [referralCode, setReferralCode] = useState('');
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle');
  const [result, setResult] = useState<{
    position?: number;
    referral_code?: string;
    referrals_needed?: number;
    early_access?: boolean;
  } | null>(null);
  const [errorMessage, setErrorMessage] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;

    setStatus('loading');
    setErrorMessage('');

    try {
      const data = await apiRequest('/api/waitlist/join', {
        method: 'POST',
        body: JSON.stringify({
          email: email.trim().toLowerCase(),
          ...(referralCode.trim() ? { referral_code: referralCode.trim() } : {}),
        }),
      });

      setResult(data);
      setStatus('success');
    } catch (err: any) {
      setStatus('error');
      setErrorMessage(err?.message || 'Something went wrong. Please try again.');
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0f1e] flex flex-col items-center justify-center px-4 py-16">
      {/* Logo / Wordmark */}
      <div className="mb-8 text-center">
        <h1 className="text-4xl font-bold text-white tracking-tight">
          Beat<span className="text-yellow-400">Vegas</span>
        </h1>
        <p className="text-gray-400 mt-2 text-sm">Decision Intelligence for Sports</p>
      </div>

      <div className="w-full max-w-md">
        {status === 'success' && result ? (
          <SuccessState result={result} />
        ) : (
          <FormState
            email={email}
            setEmail={setEmail}
            referralCode={referralCode}
            setReferralCode={setReferralCode}
            onSubmit={handleSubmit}
            loading={status === 'loading'}
            errorMessage={errorMessage}
          />
        )}
      </div>

      {/* Footer links */}
      <div className="mt-6 flex justify-center gap-4 text-xs">
        <a href="/terms" className="text-yellow-400 hover:underline">Terms of Service</a>
        <a href="/privacy" className="text-yellow-400 hover:underline">Privacy Policy</a>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────────────

function FormState({
  email,
  setEmail,
  referralCode,
  setReferralCode,
  onSubmit,
  loading,
  errorMessage,
}: {
  email: string;
  setEmail: (v: string) => void;
  referralCode: string;
  setReferralCode: (v: string) => void;
  onSubmit: (e: React.FormEvent) => void;
  loading: boolean;
  errorMessage: string;
}) {
  return (
    <div className="bg-[#111827] border border-gray-700/50 rounded-xl p-8">
      <h2 className="text-xl font-semibold text-white mb-1">Join the Early Access Waitlist</h2>
      <p className="text-sm text-gray-400 mb-6">
        Get first access to BeatVegas analytics intelligence. Invite friends to move up the list.
      </p>

      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label htmlFor="wl-email" className="block text-xs font-medium text-gray-400 mb-1">
            Email address
          </label>
          <input
            id="wl-email"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
            className="w-full bg-gray-900 border border-gray-600 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-yellow-400 transition-colors"
          />
        </div>

        <div>
          <label htmlFor="wl-referral" className="block text-xs font-medium text-gray-400 mb-1">
            Referral code <span className="text-gray-500">(optional)</span>
          </label>
          <input
            id="wl-referral"
            type="text"
            value={referralCode}
            onChange={(e) => setReferralCode(e.target.value)}
            placeholder="e.g. BV-XXXXXX"
            className="w-full bg-gray-900 border border-gray-600 rounded-lg px-4 py-2.5 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-yellow-400 transition-colors"
          />
        </div>

        {errorMessage && (
          <p className="text-red-400 text-xs">{errorMessage}</p>
        )}

        {/* NCPG disclaimer — must be visible without scrolling */}
        <p className="text-xs text-gray-500 leading-relaxed text-center">
          BeatVegas is a <strong>sports analytics platform</strong>, not a sportsbook.
          If gambling is affecting your life, call{' '}
          <a href="tel:1-800-522-4700" className="text-yellow-400 underline">
            1-800-522-4700
          </a>{' '}
          (NCPG Helpline, 24/7).
        </p>

        <button
          type="submit"
          disabled={loading || !email.trim()}
          className="w-full bg-yellow-400 hover:bg-yellow-300 disabled:opacity-50 disabled:cursor-not-allowed text-black font-semibold py-2.5 rounded-lg text-sm transition-colors"
        >
          {loading ? 'Joining…' : 'Join Waitlist →'}
        </button>
      </form>
    </div>
  );
}

function SuccessState({
  result,
}: {
  result: { position?: number; referral_code?: string; referrals_needed?: number; early_access?: boolean };
}) {
  const [copied, setCopied] = useState(false);
  const referralLink = result.referral_code
    ? `${window.location.origin}/waitlist?ref=${result.referral_code}`
    : null;

  const copyLink = () => {
    if (!referralLink) return;
    navigator.clipboard.writeText(referralLink).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  return (
    <div className="bg-[#111827] border border-yellow-500/30 rounded-xl p-8 text-center">
      <div className="text-3xl mb-3">🎯</div>
      {result.early_access ? (
        <>
          <h2 className="text-xl font-semibold text-yellow-400 mb-2">You're in!</h2>
          <p className="text-sm text-gray-300">Early access has been granted to your account.</p>
        </>
      ) : (
        <>
          <h2 className="text-xl font-semibold text-white mb-2">You're on the list!</h2>
          {result.position && (
            <p className="text-sm text-gray-300 mb-1">
              Your position: <span className="text-yellow-400 font-bold">#{result.position}</span>
            </p>
          )}
          {result.referrals_needed && (
            <p className="text-sm text-gray-400 mb-4">
              Refer <strong className="text-white">{result.referrals_needed}</strong> friend
              {result.referrals_needed !== 1 ? 's' : ''} to unlock early access.
            </p>
          )}
        </>
      )}

      {referralLink && (
        <div className="mt-5">
          <p className="text-xs text-gray-400 mb-2">Your referral link</p>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-gray-900 text-xs text-yellow-300 px-3 py-2 rounded-lg truncate">
              {referralLink}
            </code>
            <button
              onClick={copyLink}
              className="bg-yellow-400 hover:bg-yellow-300 text-black text-xs font-semibold px-3 py-2 rounded-lg transition-colors shrink-0"
            >
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
