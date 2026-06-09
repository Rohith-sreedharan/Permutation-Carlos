import React, { useEffect, useMemo, useState } from 'react';
import api, { getSubscriptionStatus } from '../services/api';
import {
  PARLAY_ARCHITECT_COPY,
  PARLAY_GATE_COPY,
  PARLAY_LIMITS,
  PRICE_DISPLAY,
  PRODUCT_LIMITS,
  canExecuteParlayRun,
  getRunPreview,
} from '../uiCopy/products';

interface Leg {
  event: string;
  line: string;
  bet_type: string;
  probability: number;
  confidence: number;
  ev: number;
}

interface ParlayResponse {
  parlay_id: string;
  sport: string;
  leg_count: number;
  risk_profile: string;
  legs: Leg[];
  parlay_odds: number;
  parlay_probability: number;
  expected_value: number;
}

interface ParlayArchitectProps {
  platformAccess?: boolean;
  telegramAccess?: boolean;
  engineCyclesLimit?: number;
  cyclesRemaining?: number;
  tokensRemaining?: number;
  overageChargesCurrentPeriod?: number;
  billingPeriodEnd?: string;
  isTrialUser?: boolean;
  onUpgradeToPlatform?: () => void;
  onViewBilling?: () => void;
  onReturnDashboard?: () => void;
}

const sportOptions = [
  { value: 'basketball_nba', label: 'NBA' },
  { value: 'basketball_ncaab', label: 'NCAAB' },
  { value: 'americanfootball_nfl', label: 'NFL' },
  { value: 'americanfootball_ncaaf', label: 'NCAAF' },
  { value: 'baseball_mlb', label: 'MLB' },
  { value: 'icehockey_nhl', label: 'NHL' },
  { value: 'all', label: 'Cross-Sport' },
] as const;

const riskProfiles = [
  { value: 'high_confidence', label: 'High Confidence' },
  { value: 'balanced', label: 'Balanced' },
  { value: 'high_volatility', label: 'High Volatility' },
] as const;

function formatDate(dateValue?: string): string {
  if (!dateValue) return 'next billing period';
  const date = new Date(dateValue);
  if (!Number.isFinite(date.getTime())) return dateValue;
  return date.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

const ParlayArchitect: React.FC<ParlayArchitectProps> = ({
  platformAccess,
  telegramAccess,
  engineCyclesLimit,
  cyclesRemaining,
  tokensRemaining,
  overageChargesCurrentPeriod,
  billingPeriodEnd,
  isTrialUser,
  onUpgradeToPlatform,
  onViewBilling,
  onReturnDashboard,
}) => {
  const [resolvedPlatformAccess, setResolvedPlatformAccess] = useState<boolean | undefined>(platformAccess);
  const [resolvedTelegramAccess, setResolvedTelegramAccess] = useState<boolean | undefined>(telegramAccess);
  const [resolvedEngineCyclesLimit, setResolvedEngineCyclesLimit] = useState<number | undefined>(engineCyclesLimit);
  const [resolvedIsTrialUser, setResolvedIsTrialUser] = useState<boolean>(isTrialUser ?? false);
  const [sport, setSport] = useState<string>('basketball_nba');
  const [legCount, setLegCount] = useState<number>(PARLAY_LIMITS.MIN_LEGS);
  const [riskProfile, setRiskProfile] = useState<string>('balanced');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [parlayData, setParlayData] = useState<ParlayResponse | null>(null);

  useEffect(() => {
    setResolvedPlatformAccess(platformAccess);
    setResolvedTelegramAccess(telegramAccess);
    setResolvedEngineCyclesLimit(engineCyclesLimit);
  }, [platformAccess, telegramAccess, engineCyclesLimit]);

  useEffect(() => {
    if (platformAccess !== undefined && telegramAccess !== undefined && engineCyclesLimit !== undefined) return;

    const hydrateEntitlements = async () => {
      try {
        const status = await getSubscriptionStatus();
        setResolvedPlatformAccess(Boolean(status.platform_access));
        setResolvedTelegramAccess(Boolean(status.telegram_access));
        setResolvedEngineCyclesLimit(Number(status.engine_cycles_limit ?? 0));
        setResolvedIsTrialUser(Boolean(status.is_trial));
      } catch {
        setResolvedPlatformAccess(false);
        setResolvedTelegramAccess(false);
        setResolvedEngineCyclesLimit(0);
      }
    };

    hydrateEntitlements();
  }, [platformAccess, telegramAccess, engineCyclesLimit]);

  const effectiveCycleLimit = resolvedEngineCyclesLimit ?? 0;
  const remainingCycles = cyclesRemaining ?? effectiveCycleLimit;
  const remainingTokens = tokensRemaining ?? PRODUCT_LIMITS.PARLAY_TOKENS_MONTHLY;
  const overageCharges = overageChargesCurrentPeriod ?? 0;

  const preview = useMemo(() => getRunPreview(legCount, remainingTokens), [legCount, remainingTokens]);
  const canRun = useMemo(
    () =>
      canExecuteParlayRun({
        platformAccess: Boolean(resolvedPlatformAccess),
        engineCyclesLimit: effectiveCycleLimit,
        overageChargesCurrentPeriod: overageCharges,
        legCount,
        tokensRemaining: remainingTokens,
      }),
    [resolvedPlatformAccess, effectiveCycleLimit, overageCharges, legCount, remainingTokens],
  );

  const cyclePct = Math.max(0, Math.min(100, (remainingCycles / PRODUCT_LIMITS.INTELLIGENCE_CYCLES_MONTHLY) * 100));
  const tokenPct = Math.max(0, Math.min(100, (remainingTokens / PRODUCT_LIMITS.PARLAY_TOKENS_MONTHLY) * 100));

  const runActionLabel = useMemo(() => {
    if (preview.hasOverage) {
      return PARLAY_ARCHITECT_COPY.runPreview.partial.confirmLabel(preview.overageChargeFormatted);
    }
    return PARLAY_ARCHITECT_COPY.runPreview.sufficient.confirmLabel;
  }, [preview]);

  const generateParlay = async () => {
    if (!canRun.allowed) return;

    try {
      setIsGenerating(true);
      setError(null);
      setParlayData(null);
      const userId = localStorage.getItem('user_id') || undefined;
      const response = await api.post('/api/architect/generate', {
        sport_key: sport,
        leg_count: legCount,
        risk_profile: riskProfile,
        user_id: userId,
        multi_sport: sport === 'all',
      });
      setParlayData(response.data as ParlayResponse);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || 'Unable to run optimization right now.');
    } finally {
      setIsGenerating(false);
    }
  };

  const renderGate = () => {
    if (!resolvedPlatformAccess && !resolvedTelegramAccess) {
      // Trial user gate — distinct messaging with Subscribe Now CTA + Continue Trial link
      if (resolvedIsTrialUser) {
        return (
          <div className="bg-charcoal border border-gold/40 rounded-xl p-6 text-center">
            <div className="text-3xl mb-3">🏆</div>
            <h3 className="text-xl font-bold text-gold mb-2">Parlay Architect — Platform Feature</h3>
            <p className="text-light-gray mb-1">
              Parlay Architect is available to Platform subscribers. Your current trial gives you
              access to Telegram Syndicate signals.
            </p>
            <p className="text-light-gray/70 text-sm mb-5">
              Upgrade now to unlock 6-leg parlay optimization during your trial window.
            </p>
            <div className="flex flex-col sm:flex-row gap-3 justify-center">
              <button
                type="button"
                onClick={onUpgradeToPlatform}
                className="px-5 py-2.5 bg-gold text-darkNavy font-bold rounded-lg hover:bg-gold/90 transition-colors"
              >
                Subscribe Now — {PRICE_DISPLAY.BEATVEGAS_PLATFORM}
              </button>
              <button
                type="button"
                onClick={onReturnDashboard}
                className="px-5 py-2.5 bg-transparent border border-light-gray/30 text-light-gray rounded-lg hover:border-light-gray/60 transition-colors"
              >
                Continue Trial
              </button>
            </div>
          </div>
        );
      }
      return (
        <div className="bg-charcoal border border-electric-blue/30 rounded-xl p-5 text-center">
          <h3 className="text-xl font-bold text-white mb-2">Subscription Required</h3>
          <p className="text-light-gray mb-4">{PARLAY_ARCHITECT_COPY.subheadline}</p>
          <button
            type="button"
            onClick={onUpgradeToPlatform}
            className="px-4 py-2 bg-electric-blue text-white font-semibold rounded-lg hover:bg-electric-blue/90"
          >
            Get Platform Access - {PRICE_DISPLAY.BEATVEGAS_PLATFORM}
          </button>
          <div className="mt-3">
            <button
              type="button"
              onClick={onReturnDashboard}
              className="text-light-gray/60 text-sm underline hover:text-light-gray transition-colors"
            >
              Continue Trial
            </button>
          </div>
        </div>
      );
    }

    if (!resolvedPlatformAccess) {
      return (
        <div className="bg-charcoal border border-electric-blue/30 rounded-xl p-5">
          <h3 className="text-xl font-bold text-white mb-2">Parlay Architect - Platform Only</h3>
          <p className="text-light-gray mb-4">Build up to 6-leg decision combinations from engine outputs.</p>
          <button
            type="button"
            onClick={onUpgradeToPlatform}
            className="px-4 py-2 bg-electric-blue text-white font-semibold rounded-lg hover:bg-electric-blue/90"
          >
            Upgrade to Platform
          </button>
        </div>
      );
    }

    if (canRun.reason === 'CYCLES_EXHAUSTED') {
      return (
        <div className="bg-charcoal border border-bold-red/40 rounded-xl p-5">
          <h3 className="text-xl font-bold text-bold-red mb-2">{PARLAY_GATE_COPY.CYCLES_EXHAUSTED.title}</h3>
          <p className="text-light-gray mb-2">{PARLAY_GATE_COPY.CYCLES_EXHAUSTED.body}</p>
          <p className="text-light-gray/80 text-sm mb-4">
            {PARLAY_GATE_COPY.CYCLES_EXHAUSTED.resetLabel} {formatDate(billingPeriodEnd)}
          </p>
          <div className="flex gap-3">
            <button type="button" onClick={onViewBilling} className="px-4 py-2 bg-electric-blue text-white rounded-lg">
              {PARLAY_GATE_COPY.CYCLES_EXHAUSTED.cta}
            </button>
            <button type="button" onClick={onReturnDashboard} className="px-4 py-2 bg-navy text-light-gray rounded-lg">
              {PARLAY_GATE_COPY.CYCLES_EXHAUSTED.ctaSecondary}
            </button>
          </div>
        </div>
      );
    }

    if (canRun.reason === 'OVERAGE_CAP_REACHED') {
      return (
        <div className="bg-charcoal border border-bold-red/40 rounded-xl p-5">
          <h3 className="text-xl font-bold text-bold-red mb-2">{PARLAY_GATE_COPY.OVERAGE_CAP_REACHED.title}</h3>
          <p className="text-light-gray mb-2">{PARLAY_GATE_COPY.OVERAGE_CAP_REACHED.body}</p>
          <p className="text-light-gray/80 text-sm mb-4">
            {PARLAY_GATE_COPY.OVERAGE_CAP_REACHED.resetNote(formatDate(billingPeriodEnd))}
          </p>
          <div className="flex gap-3">
            <button type="button" onClick={onViewBilling} className="px-4 py-2 bg-electric-blue text-white rounded-lg">
              {PARLAY_GATE_COPY.OVERAGE_CAP_REACHED.cta}
            </button>
            <button type="button" onClick={onReturnDashboard} className="px-4 py-2 bg-navy text-light-gray rounded-lg">
              {PARLAY_GATE_COPY.OVERAGE_CAP_REACHED.ctaSecondary}
            </button>
          </div>
        </div>
      );
    }

    return null;
  };

  return (
    <div className="min-h-screen bg-darkNavy px-4 py-8">
      <div className="max-w-5xl mx-auto space-y-6">
        <header className="text-center">
          <h1 className="text-4xl font-bold text-gold mb-2">{PARLAY_ARCHITECT_COPY.pageTitle}</h1>
          <p className="text-lightGold">{PARLAY_ARCHITECT_COPY.subheadline}</p>
          <p className="text-lightGold/70 text-sm mt-2">{PARLAY_ARCHITECT_COPY.legGuidance}</p>
        </header>

        {(resolvedPlatformAccess || resolvedTelegramAccess) && (
          <section className="bg-charcoal border border-gold/20 rounded-xl p-5 space-y-4">
            <div>
              <div className="flex justify-between text-sm text-lightGold mb-1">
                <span>Intelligence Cycles</span>
                <span>
                  {remainingCycles.toLocaleString()} / {PRODUCT_LIMITS.INTELLIGENCE_CYCLES_MONTHLY.toLocaleString()}
                </span>
              </div>
              <div className="w-full bg-navy h-2 rounded-full overflow-hidden">
                <div className="h-2 bg-neon-green" style={{ width: `${cyclePct}%` }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between text-sm text-lightGold mb-1">
                <span>Parlay Tokens</span>
                <span>
                  {remainingTokens.toLocaleString()} / {PRODUCT_LIMITS.PARLAY_TOKENS_MONTHLY.toLocaleString()}
                </span>
              </div>
              <div className="w-full bg-navy h-2 rounded-full overflow-hidden">
                <div className="h-2 bg-electric-blue" style={{ width: `${tokenPct}%` }} />
              </div>
            </div>
            <p className="text-xs text-lightGold/60">Reset date: {formatDate(billingPeriodEnd)}</p>
          </section>
        )}

        {renderGate()}

        {resolvedPlatformAccess && canRun.allowed && (
          <section className="bg-charcoal border border-gold/20 rounded-xl p-6 space-y-5">
            <div>
              <label className="block text-lightGold font-semibold mb-2">Sport</label>
              <div className="flex flex-wrap gap-2">
                {sportOptions.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setSport(option.value)}
                    className={`px-4 py-2 rounded-lg text-sm font-semibold ${
                      sport === option.value ? 'bg-gold text-darkNavy' : 'bg-navy/70 text-lightGold border border-gold/20'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-lightGold font-semibold mb-2">
                {PARLAY_ARCHITECT_COPY.legSelectLabel}: <span className="text-gold">{legCount}</span>
              </label>
              <input
                type="range"
                min={PARLAY_LIMITS.MIN_LEGS}
                max={PARLAY_LIMITS.MAX_LEGS}
                value={legCount}
                onChange={(event) => setLegCount(Number(event.target.value))}
                className="w-full"
              />
              <div className="flex justify-between text-xs text-lightGold/70 mt-1">
                <span>{PARLAY_LIMITS.MIN_LEGS} legs</span>
                <span>{PARLAY_LIMITS.MAX_LEGS} legs</span>
              </div>
            </div>

            <div>
              <label className="block text-lightGold font-semibold mb-2">Risk Profile</label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                {riskProfiles.map((profile) => (
                  <button
                    key={profile.value}
                    type="button"
                    onClick={() => setRiskProfile(profile.value)}
                    className={`px-4 py-3 rounded-lg text-sm font-semibold ${
                      riskProfile === profile.value
                        ? 'bg-electric-blue text-white'
                        : 'bg-navy/70 text-lightGold border border-gold/20'
                    }`}
                  >
                    {profile.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-navy/40 border border-gold/20 rounded-lg p-4 text-sm text-lightGold space-y-1">
              <p>Run preview:</p>
              <p>Tokens used: {preview.tokenCost}</p>
              <p>Cycles used: {preview.cycleCost}</p>
              {!preview.hasOverage && <p>Tokens after run: {preview.tokensAfter}</p>}
              {preview.hasOverage && (
                <>
                  <p>{PARLAY_GATE_COPY.TOKEN_PARTIAL.yourRemainingNote(remainingTokens)}</p>
                  <p>{PARLAY_GATE_COPY.TOKEN_PARTIAL.shortfallNote(preview.tokenShortfall)}</p>
                  <p>Estimated overage: {preview.overageChargeFormatted}</p>
                </>
              )}
              {preview.isFullOverage && (
                <>
                  <p>{PARLAY_GATE_COPY.TOKEN_EXHAUSTED.body}</p>
                  <p>{PARLAY_GATE_COPY.TOKEN_EXHAUSTED.overageNote}</p>
                </>
              )}
            </div>

            <button
              type="button"
              onClick={generateParlay}
              disabled={isGenerating}
              className={`w-full py-3 rounded-lg font-bold ${
                isGenerating
                  ? 'bg-navy text-lightGold/60 cursor-not-allowed'
                  : 'bg-linear-to-r from-gold to-lightGold text-darkNavy hover:shadow-lg'
              }`}
            >
              {isGenerating ? 'Running optimization...' : runActionLabel}
            </button>
          </section>
        )}

        {error && <section className="bg-deepRed/20 border border-deepRed rounded-lg p-4 text-deepRed">{error}</section>}

        {parlayData && (
          <section className="bg-charcoal border border-gold/20 rounded-xl p-6 space-y-4">
            <h2 className="text-2xl font-bold text-gold">{PARLAY_ARCHITECT_COPY.postRun.noOverage}</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="bg-navy/50 rounded-lg p-3">
                <p className="text-xs text-lightGold/70">Legs</p>
                <p className="text-lightGold font-semibold">{parlayData.leg_count}</p>
              </div>
              <div className="bg-navy/50 rounded-lg p-3">
                <p className="text-xs text-lightGold/70">Parlay odds</p>
                <p className="text-lightGold font-semibold">
                  {parlayData.parlay_odds > 0 ? '+' : ''}
                  {parlayData.parlay_odds}
                </p>
              </div>
              <div className="bg-navy/50 rounded-lg p-3">
                <p className="text-xs text-lightGold/70">Expected value</p>
                <p className="text-lightGold font-semibold">
                  {parlayData.expected_value > 0 ? '+' : ''}
                  {parlayData.expected_value.toFixed(1)}%
                </p>
              </div>
            </div>
            <div className="space-y-2">
              {parlayData.legs.map((leg, index) => (
                <div key={`${parlayData.parlay_id}-${index}`} className="bg-navy/40 border border-gold/10 rounded-lg p-3">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-lightGold font-semibold">
                      Leg {index + 1}: {leg.event}
                    </p>
                    <p className="text-lightGold/80 text-sm">{(leg.probability * 100).toFixed(1)}%</p>
                  </div>
                  <p className="text-lightGold/70 text-sm mt-1">
                    {leg.line} • {leg.bet_type}
                  </p>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
};

export default ParlayArchitect;
