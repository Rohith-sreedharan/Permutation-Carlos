import React, { useState, useEffect } from 'react';
import LoadingSpinner from './LoadingSpinner';
import { getSubscriptionStatus , API_BASE_URL } from '../services/api';
import {
  BILLING_PAGE_COPY,
  PLAN_IDS,
  type PlanId,
} from '../uiCopy/products';



interface BillingState {
  plan_id: PlanId | null;
  platform_access: boolean;
  telegram_access: boolean;
  engine_cycles_limit: number;
  status: 'ACTIVE' | 'PAST_DUE' | 'CANCELLED' | 'TRIAL';
  next_billing_date: string;
  billing_period_end: string;
  overage_charges_current_period: number;
  cycles_remaining?: number;
  parlay_tokens_remaining?: number;
  paymentMethod?: {
    last4: string;
    brand: string;
  };
}

function normalizeBillingState(data: any): BillingState {
  const rawPlanId = data?.plan_id;
  const planId: PlanId | null = rawPlanId === PLAN_IDS.BEATVEGAS_PLATFORM
    ? PLAN_IDS.BEATVEGAS_PLATFORM
    : rawPlanId === PLAN_IDS.TELEGRAM_SYNDICATE
      ? PLAN_IDS.TELEGRAM_SYNDICATE
      : null;

  const normalizedStatus = (data?.status || 'active').toUpperCase();
  const status: BillingState['status'] =
    normalizedStatus === 'PAST_DUE'
      ? 'PAST_DUE'
      : normalizedStatus === 'CANCELLED' || normalizedStatus === 'CANCELED'
        ? 'CANCELLED'
        : normalizedStatus === 'TRIAL'
          ? 'TRIAL'
          : 'ACTIVE';

  const nextBillingDate = data?.next_billing_date || data?.renewalDate || new Date().toISOString();

  return {
    plan_id: planId,
    platform_access: Boolean(data?.platform_access),
    telegram_access: Boolean(data?.telegram_access),
    engine_cycles_limit: Number(data?.engine_cycles_limit ?? 0),
    status,
    next_billing_date: nextBillingDate,
    billing_period_end: data?.billing_period_end || nextBillingDate,
    overage_charges_current_period: Number(data?.overage_charges_current_period || 0),
    cycles_remaining: Number(data?.engine_cycles_remaining ?? data?.cycles_remaining ?? 0),
    parlay_tokens_remaining: Number(data?.parlay_tokens_remaining ?? 0),
    paymentMethod: data?.paymentMethod,
  };
}

const SubscriptionSettings: React.FC = () => {
  const [billing, setBilling] = useState<BillingState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const data = await getSubscriptionStatus();
        setBilling(normalizeBillingState(data));
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to load subscription');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    load();
  }, []);

  const handleManageSubscription = async () => {
    try {
      const token = localStorage.getItem('authToken');
      if (!token) {
        setError('Please log in to manage your subscription');
        return;
      }
      const response = await fetch(`${API_BASE_URL}/api/stripe/customer-portal`, {
        method: 'GET',
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (!response.ok) {
        const data = await response.json();
        setError(data.detail || 'Failed to access customer portal');
        return;
      }
      const data = await response.json();
      if (data.url) {
        window.location.href = data.url;
      } else {
        setError('No portal URL returned');
      }
    } catch (err: any) {
      console.error('Error accessing customer portal:', err);
      setError('Failed to access customer portal');
    }
  };

  if (loading) return <LoadingSpinner />;
  if (error) return <div className="text-center text-bold-red p-8">{error}</div>;

  const bc = BILLING_PAGE_COPY;
  const planId = billing?.plan_id;
  const isTelegram = planId === PLAN_IDS.TELEGRAM_SYNDICATE;
  const isPlatform = planId === PLAN_IDS.BEATVEGAS_PLATFORM;
  const cyclesRemaining = billing?.cycles_remaining ?? 0;
  const tokensRemaining = billing?.parlay_tokens_remaining ?? 0;
  const overageCharges = billing?.overage_charges_current_period ?? 0;
  const capRemaining = Math.max(0, 200 - overageCharges);
  const resetDate = billing?.billing_period_end
    ? new Date(billing.billing_period_end).toLocaleDateString()
    : '—';
  const nextBillingDate = billing?.next_billing_date
    ? new Date(billing.next_billing_date).toLocaleDateString()
    : '—';

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-white">{bc.pageTitle}</h1>
        <p className="text-light-gray mt-1">{bc.subheadline}</p>
      </div>

      {/* Telegram Syndicate plan */}
      {isTelegram && (
        <div className="bg-charcoal border border-navy rounded-xl p-6 space-y-4">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div className="space-y-1">
              <p className="text-xs text-light-gray uppercase tracking-wide">{bc.TELEGRAM_PLAN.label}</p>
              <h2 className="text-2xl font-bold text-white">{bc.TELEGRAM_PLAN.name}</h2>
              <p className="text-lg font-semibold text-electric-blue">{bc.TELEGRAM_PLAN.price}</p>
              <p className="text-sm text-light-gray">
                Next billing: <span className="text-white">{nextBillingDate}</span>
              </p>
              {billing?.status && (
                <p className="text-sm text-light-gray">
                  {bc.TELEGRAM_PLAN.statusLabel}:{' '}
                  <span className={`font-semibold ${billing.status === 'ACTIVE' ? 'text-neon-green' : 'text-bold-red'}`}>
                    {billing.status.charAt(0) + billing.status.slice(1).toLowerCase()}
                  </span>
                </p>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <button
                onClick={() => window.location.href = '/upgrade'}
                className="px-5 py-2 rounded-lg font-semibold bg-electric-blue hover:bg-electric-blue/90 text-white transition-all"
              >
                {bc.TELEGRAM_PLAN.ctaUpgrade}
              </button>
              <button
                onClick={() => setShowCancelConfirm(true)}
                className="px-5 py-2 rounded-lg text-sm text-light-gray hover:text-white border border-navy hover:border-light-gray/50 transition-all"
              >
                {bc.TELEGRAM_PLAN.ctaCancel}
              </button>
            </div>
          </div>
          <div className="border-t border-navy pt-4 grid md:grid-cols-2 gap-4 text-sm">
            <div>
              <p className="text-xs font-semibold text-white uppercase tracking-wide mb-2">Included</p>
              <p className="text-light-gray">{bc.TELEGRAM_PLAN.included}</p>
            </div>
            <div>
              <p className="text-xs font-semibold text-light-gray/50 uppercase tracking-wide mb-2">Not included</p>
              <p className="text-light-gray/50">{bc.TELEGRAM_PLAN.notIncluded}</p>
            </div>
          </div>
        </div>
      )}

      {/* Platform plan */}
      {isPlatform && (
        <div className="bg-charcoal border border-gold/30 rounded-xl p-6 space-y-4">
          <div className="flex items-start justify-between flex-wrap gap-4">
            <div className="space-y-1">
              <p className="text-xs text-light-gray uppercase tracking-wide">{bc.PLATFORM_PLAN.label}</p>
              <h2 className="text-2xl font-bold text-white">{bc.PLATFORM_PLAN.name}</h2>
              <p className="text-lg font-semibold text-gold">{bc.PLATFORM_PLAN.price}</p>
              <p className="text-sm text-light-gray">
                Next billing: <span className="text-white">{nextBillingDate}</span>
              </p>
              {billing?.status && (
                <p className="text-sm text-light-gray">
                  {bc.PLATFORM_PLAN.statusLabel}:{' '}
                  <span className={`font-semibold ${billing.status === 'ACTIVE' ? 'text-neon-green' : 'text-bold-red'}`}>
                    {billing.status.charAt(0) + billing.status.slice(1).toLowerCase()}
                  </span>
                </p>
              )}
            </div>
            <div className="flex flex-col gap-2">
              <button
                onClick={handleManageSubscription}
                className="px-5 py-2 rounded-lg font-semibold bg-electric-blue hover:bg-electric-blue/90 text-white transition-all"
              >
                {bc.PLATFORM_PLAN.ctaHistory}
              </button>
              <button
                onClick={() => setShowCancelConfirm(true)}
                className="px-5 py-2 rounded-lg text-sm text-light-gray hover:text-white border border-navy hover:border-light-gray/50 transition-all"
              >
                {bc.PLATFORM_PLAN.ctaCancel}
              </button>
            </div>
          </div>

          <div className="border-t border-navy pt-4 space-y-3">
            <p className="text-xs font-semibold text-white uppercase tracking-wide">Usage this period</p>
            <div className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-light-gray">{bc.PLATFORM_PLAN.cyclesLabel}</span>
                <span className="text-white font-medium">{cyclesRemaining.toLocaleString()} / 100,000 remaining</span>
              </div>
              <div className="w-full h-1.5 bg-navy rounded-full">
                <div className="h-1.5 bg-electric-blue rounded-full" style={{ width: `${Math.min(100, (cyclesRemaining / 100_000) * 100)}%` }} />
              </div>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-light-gray">{bc.PLATFORM_PLAN.tokensLabel}</span>
                <span className="text-white font-medium">{tokensRemaining.toLocaleString()} / 1,500 remaining</span>
              </div>
              <div className="w-full h-1.5 bg-navy rounded-full">
                <div className="h-1.5 bg-gold rounded-full" style={{ width: `${Math.min(100, (tokensRemaining / 1_500) * 100)}%` }} />
              </div>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-light-gray">{bc.PLATFORM_PLAN.overageLabel}</span>
              <span className="text-white font-medium">${overageCharges.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-light-gray">{bc.PLATFORM_PLAN.overageCapLabel}</span>
              <span className="text-white font-medium">$200.00</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-light-gray">{bc.PLATFORM_PLAN.capRemaining}</span>
              <span className="text-white font-medium">${capRemaining.toFixed(2)}</span>
            </div>
            <div className="flex justify-between text-sm">
              <span className="text-light-gray">Resets</span>
              <span className="text-white font-medium">{resetDate}</span>
            </div>
          </div>
        </div>
      )}

      {/* Payment Method */}
      {billing?.paymentMethod && (
        <div className="bg-charcoal border border-navy rounded-xl p-6">
          <h3 className="text-lg font-bold text-white mb-4">Payment Method</h3>
          <div className="flex items-center justify-between p-4 bg-navy/50 rounded-lg">
            <div className="flex items-center gap-4">
              <div className="w-12 h-8 bg-white rounded flex items-center justify-center">
                <span className="text-xs font-bold text-navy uppercase">{billing.paymentMethod.brand}</span>
              </div>
              <div>
                <p className="font-semibold text-white">•••• •••• •••• {billing.paymentMethod.last4}</p>
                <p className="text-sm text-light-gray">Primary payment method</p>
              </div>
            </div>
            <button onClick={handleManageSubscription} className="text-electric-blue hover:underline text-sm font-semibold">
              Update
            </button>
          </div>
        </div>
      )}

      {/* Cancellation confirm */}
      {showCancelConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/80" onClick={() => setShowCancelConfirm(false)} />
          <div className="relative bg-charcoal border border-navy rounded-xl p-8 max-w-md w-full space-y-4">
            <h3 className="text-xl font-bold text-white">{bc.CANCELLATION.title}</h3>
            <p className="text-sm text-light-gray">{bc.CANCELLATION.accessNote(resetDate)}</p>
            <p className="text-sm text-light-gray">{bc.CANCELLATION.afterNote}</p>
            <p className="text-xs text-light-gray/60">{bc.CANCELLATION.noRefundNote}</p>
            <div className="flex flex-col gap-2 pt-2">
              <button
                onClick={handleManageSubscription}
                className="w-full py-3 rounded-lg font-bold bg-bold-red/80 hover:bg-bold-red text-white transition-all"
              >
                {bc.CANCELLATION.ctaConfirm}
              </button>
              <button
                onClick={() => setShowCancelConfirm(false)}
                className="w-full py-2 rounded-lg text-sm text-light-gray hover:text-white border border-navy transition-all"
              >
                {bc.CANCELLATION.ctaKeep}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Compliance Notice */}
      <div className="bg-navy/30 border border-electric-blue/20 rounded-lg p-4">
        <p className="text-xs text-light-gray">
          <span className="text-electric-blue font-semibold">Analysis Platform:</span> BeatVegas provides sports analytics and intelligence. We do not accept wagers or hold funds for betting purposes. All payments are for subscription access only.
        </p>
      </div>
    </div>
  );
};

export default SubscriptionSettings;
