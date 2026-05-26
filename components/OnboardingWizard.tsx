/**
 * Phase 5A — OnboardingWizard
 * ============================
 * Three locked screens. No more. No less. (Phase 5 directive §5A.1)
 *
 * Screen 1 — What BeatVegas Is
 * Screen 2 — Classifications Explained (EDGE, LEAN, MARKET_ALIGNED, NO_ACTION, BLOCKED)
 * Screen 3 — Credit System
 *
 * Rules:
 *  - Agentic language throughout. Zero betting / wagering / sportsbook framing.
 *  - No fabricated data shown (AC-5). Empty states only when no real data exists.
 *  - onboarding_complete flag set ONLY after screen 3 is completed via API (AC-2).
 *  - Responsive at 390px mobile viewport (§5A.7).
 */
import React, { useState } from 'react';

const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000';

interface OnboardingWizardProps {
  onComplete: () => void;
}

const TOTAL_SCREENS = 3;

// ── Tooltip helper ───────────────────────────────────────────────────────────
const Tooltip: React.FC<{ text: string; children: React.ReactNode }> = ({ text, children }) => {
  const [visible, setVisible] = useState(false);
  return (
    <span className="relative inline-block">
      <span
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
        onTouchStart={() => setVisible(v => !v)}
        className="cursor-help border-b border-dashed border-gold/60"
      >
        {children}
      </span>
      {visible && (
        <span className="absolute z-50 bottom-full left-1/2 -translate-x-1/2 mb-2 w-56 text-xs text-white bg-charcoal border border-gold/30 rounded px-3 py-2 shadow-lg pointer-events-none">
          {text}
        </span>
      )}
    </span>
  );
};

// ── Screen 1: What BeatVegas Is ──────────────────────────────────────────────
const Screen1: React.FC = () => (
  <div className="space-y-6">
    <div className="text-center">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-gold/10 border border-gold/30 mb-4">
        <svg className="w-8 h-8 text-gold" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15M14.25 3.104c.251.023.501.05.75.082M19.8 15l-1.8 1.8A2.25 2.25 0 0116.4 17.4H7.6a2.25 2.25 0 01-1.6-.663L4.2 15m15.6 0l-3.6-3.6" />
        </svg>
      </div>
      <h2 className="text-2xl font-bold text-white mb-2">What is BeatVegas?</h2>
      <p className="text-lightGold/70 text-sm">Agentic simulation intelligence platform</p>
    </div>

    <div className="space-y-4">
      <div className="bg-navy/60 border border-gold/20 rounded-lg p-4">
        <h3 className="text-gold font-semibold mb-2 flex items-center gap-2">
          <span className="text-lg">&#9889;</span> Not a Sportsbook
        </h3>
        <p className="text-white/80 text-sm leading-relaxed">
          BeatVegas does not place bets. No wagering. No gambling facilitation.
          This is a <strong className="text-gold">simulation intelligence platform</strong> that
          models probability distributions using autonomous agents.
        </p>
      </div>

      <div className="bg-navy/60 border border-blue-500/20 rounded-lg p-4">
        <h3 className="text-blue-400 font-semibold mb-2 flex items-center gap-2">
          <span className="text-lg">&#129302;</span> Autonomous Agents
        </h3>
        <p className="text-white/80 text-sm leading-relaxed">
          Every decision record is produced by a named agent running deterministic simulations.
          No human editorial. No guesswork. Institutional-grade analytics delivered autonomously.
        </p>
      </div>

      <div className="bg-navy/60 border border-purple-500/20 rounded-lg p-4">
        <h3 className="text-purple-400 font-semibold mb-2 flex items-center gap-2">
          <span className="text-lg">&#128202;</span> Decision Intelligence
        </h3>
        <p className="text-white/80 text-sm leading-relaxed">
          BeatVegas surfaces probability gaps between model outputs and market-implied probabilities.
          The platform helps you understand where the simulation diverges from the market.
        </p>
      </div>
    </div>
  </div>
);

// ── Screen 2: Classifications Explained ──────────────────────────────────────
const Screen2: React.FC = () => (
  <div className="space-y-6">
    <div className="text-center">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-blue-500/10 border border-blue-500/30 mb-4">
        <svg className="w-8 h-8 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" />
        </svg>
      </div>
      <h2 className="text-2xl font-bold text-white mb-2">Intelligence Classifications</h2>
      <p className="text-lightGold/70 text-sm">Every decision record carries one of five classifications</p>
    </div>

    <div className="space-y-3">
      <div className="bg-navy/60 border border-green-500/30 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 px-2 py-0.5 bg-green-500/20 text-green-400 text-xs font-bold rounded border border-green-500/40 shrink-0">
            EDGE
          </span>
          <div>
            <p className="text-white/90 text-sm leading-relaxed">
              The simulation model assigns a probability that <em>exceeds</em> the market-implied
              probability by a meaningful threshold. A divergence between the agent's assessment
              and current market pricing.
            </p>
            <p className="text-white/50 text-xs mt-1">
              model_prob &minus; market_implied_prob exceeds threshold
            </p>
          </div>
        </div>
      </div>

      <div className="bg-navy/60 border border-yellow-500/30 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs font-bold rounded border border-yellow-500/40 shrink-0">
            LEAN
          </span>
          <div>
            <p className="text-white/90 text-sm leading-relaxed">
              A directional signal is present. The model diverges from the market,
              but the gap is smaller than the EDGE threshold. Directional, not conclusive.
            </p>
            <p className="text-white/50 text-xs mt-1">
              Smaller gap than EDGE — signal present, not at threshold strength
            </p>
          </div>
        </div>
      </div>

      <div className="bg-navy/60 border border-gray-500/30 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 px-2 py-0.5 bg-gray-500/20 text-gray-400 text-xs font-bold rounded border border-gray-500/40 shrink-0 whitespace-nowrap">
            MARKET_ALIGNED
          </span>
          <div>
            <p className="text-white/90 text-sm leading-relaxed">
              The model agrees with the market's implied probability. No actionable signal.
              The simulation output is consistent with current market pricing.
            </p>
            <p className="text-white/50 text-xs mt-1">
              Model and market are aligned — no divergence detected
            </p>
          </div>
        </div>
      </div>

      <div className="bg-navy/60 border border-blue-400/30 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 px-2 py-0.5 bg-blue-400/20 text-blue-300 text-xs font-bold rounded border border-blue-400/40 shrink-0 whitespace-nowrap">
            NO_ACTION
          </span>
          <div>
            <p className="text-white/90 text-sm leading-relaxed">
              No material gap detected. Market is efficiently priced for this event.
            </p>
            <p className="text-white/50 text-xs mt-1">
              Divergence below minimum threshold — no signal produced
            </p>
          </div>
        </div>
      </div>

      <div className="bg-navy/60 border border-red-500/30 rounded-lg p-4">
        <div className="flex items-start gap-3">
          <span className="mt-0.5 px-2 py-0.5 bg-red-500/20 text-red-400 text-xs font-bold rounded border border-red-500/40 shrink-0">
            BLOCKED
          </span>
          <div>
            <p className="text-white/90 text-sm leading-relaxed">
              Analysis unavailable. Triggered by risk controls, integrity check failure, or missing context.
            </p>
            <p className="text-white/50 text-xs mt-1">
              Agent halted — output suppressed by regulatory or integrity controls
            </p>
          </div>
        </div>
      </div>

      <div className="bg-charcoal/50 rounded p-3 border border-white/10">
        <p className="text-white/50 text-xs text-center">
          Classifications are produced exclusively by autonomous agents. No human editorial input.
        </p>
      </div>
    </div>
  </div>
);

// ── Screen 3: Credit System ──────────────────────────────────────────────────
const Screen3: React.FC = () => (
  <div className="space-y-6">
    <div className="text-center">
      <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-purple-500/10 border border-purple-500/30 mb-4">
        <svg className="w-8 h-8 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
            d="M12 6v12m-3-2.818l.879.659c1.171.879 3.07.879 4.242 0 1.172-.879 1.172-2.303 0-3.182C13.536 12.219 12.768 12 12 12c-.725 0-1.45-.22-2.003-.659-1.106-.879-1.106-2.303 0-3.182s2.9-.879 4.006 0l.415.33M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <h2 className="text-2xl font-bold text-white mb-2">Intelligence Cycles</h2>
      <p className="text-lightGold/70 text-sm">How the credit system works</p>
    </div>

    <div className="space-y-4">
      <div className="bg-navy/60 border border-purple-500/20 rounded-lg p-4">
        <h3 className="text-purple-400 font-semibold mb-2 flex items-center gap-2">
          <span>&#128161;</span> Always Visible
        </h3>
        <p className="text-white/80 text-sm leading-relaxed">
          Your Intelligence Cycle balance is displayed at all times in the sidebar and header.
          You always know exactly how many cycles remain.
        </p>
      </div>

      <div className="bg-navy/60 border border-gold/20 rounded-lg p-4">
        <h3 className="text-gold font-semibold mb-2 flex items-center gap-2">
          <span>&#10003;</span> Cost Confirmed Before Every Action
        </h3>
        <p className="text-white/80 text-sm leading-relaxed">
          The cost of every credit-consuming action is shown before it executes.
          You confirm before any cycles are deducted.{' '}
          <strong className="text-gold">No silent deductions. Ever.</strong>
        </p>
      </div>

      <div className="bg-navy/60 border border-red-500/20 rounded-lg p-4">
        <h3 className="text-red-400 font-semibold mb-2 flex items-center gap-2">
          <span>&#9888;&#65039;</span> Low-Balance Warning
        </h3>
        <p className="text-white/80 text-sm leading-relaxed">
          A warning fires automatically when your balance approaches the minimum threshold.
          No action executes if insufficient credits remain — you will see a clear message
          and an upgrade path instead.
        </p>
      </div>

      <div className="bg-gold/5 border border-gold/30 rounded-lg p-4">
        <h3 className="text-gold font-semibold mb-2 flex items-center gap-2">
          <span>&#128640;</span> Platform Access &mdash; $97/month
        </h3>
        <p className="text-white/80 text-sm leading-relaxed">
          Platform access unlocks full Decision Engine capacity, Parlay Architect intelligence,
          and priority simulation cycles. Upgrade prompt fires automatically at 80% usage.
        </p>
      </div>
    </div>
  </div>
);

// ── Main OnboardingWizard ────────────────────────────────────────────────────
const OnboardingWizard: React.FC<OnboardingWizardProps> = ({ onComplete }) => {
  const [currentScreen, setCurrentScreen] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isLastScreen = currentScreen === TOTAL_SCREENS;

  const handleNext = () => {
    if (currentScreen < TOTAL_SCREENS) {
      setCurrentScreen(s => s + 1);
    }
  };

  const handleBack = () => {
    if (currentScreen > 1) {
      setCurrentScreen(s => s - 1);
    }
  };

  const handleFinish = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const token = localStorage.getItem('authToken');
      const res = await fetch(`${API_BASE_URL}/api/onboarding/complete`, {
        method: 'POST',
        headers: {
          Authorization: token ? `Bearer ${token}` : '',
          'Content-Type': 'application/json',
        },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error((body as any).detail || 'Failed to complete onboarding');
      }
      onComplete();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Something went wrong. Please try again.';
      setError(message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-linear-to-br from-darkNavy via-navy to-black flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Logo header */}
        <div className="text-center mb-6">
          <p className="text-white/40 text-xs uppercase tracking-widest font-teko">BEATVEGAS &mdash; SPORTS INTELLIGENCE</p>
        </div>

        {/* Step indicators */}
        <div className="flex items-center justify-center gap-2 mb-6">
          {Array.from({ length: TOTAL_SCREENS }, (_, i) => i + 1).map(step => (
            <React.Fragment key={step}>
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold border transition-all ${
                  step < currentScreen
                    ? 'bg-gold border-gold text-darkNavy'
                    : step === currentScreen
                    ? 'bg-gold/20 border-gold text-gold'
                    : 'bg-navy/50 border-white/20 text-white/30'
                }`}
              >
                {step < currentScreen ? '\u2713' : step}
              </div>
              {step < TOTAL_SCREENS && (
                <div className={`h-px w-10 transition-all ${step < currentScreen ? 'bg-gold' : 'bg-white/20'}`} />
              )}
            </React.Fragment>
          ))}
        </div>

        {/* Card */}
        <div className="bg-charcoal/80 backdrop-blur border border-white/10 rounded-xl p-6 shadow-2xl">
          {currentScreen === 1 && <Screen1 />}
          {currentScreen === 2 && <Screen2 />}
          {currentScreen === 3 && <Screen3 />}

          {error && (
            <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-sm">
              {error}
            </div>
          )}

          {/* Navigation row */}
          <div className="flex items-center justify-between mt-6 pt-4 border-t border-white/10">
            <button
              onClick={handleBack}
              disabled={currentScreen === 1}
              className="px-4 py-2 text-sm text-white/50 hover:text-white disabled:opacity-0 disabled:pointer-events-none transition-colors"
            >
              &larr; Back
            </button>

            <span className="text-white/30 text-xs">
              {currentScreen}&nbsp;/&nbsp;{TOTAL_SCREENS}
            </span>

            {isLastScreen ? (
              <button
                onClick={handleFinish}
                disabled={submitting}
                className="px-6 py-2 bg-linear-to-r from-gold to-lightGold text-darkNavy text-sm font-bold rounded hover:shadow-lg hover:shadow-gold/30 transition-all disabled:opacity-50"
              >
                {submitting ? 'Activating\u2026' : 'Activate Dashboard \u2192'}
              </button>
            ) : (
              <button
                onClick={handleNext}
                className="px-6 py-2 bg-linear-to-r from-gold to-lightGold text-darkNavy text-sm font-bold rounded hover:shadow-lg hover:shadow-gold/30 transition-all"
              >
                Next &rarr;
              </button>
            )}
          </div>
        </div>

        {/* Regulatory footer */}
        <p className="text-center text-white/20 text-xs mt-4">
          BeatVegas is not a sportsbook. No bet placement. No wagering. Simulation intelligence only.
        </p>
      </div>
    </div>
  );
};

export default OnboardingWizard;
