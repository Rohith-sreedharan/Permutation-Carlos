/**
 * Phase 13 — Section 13.18: Subscriber Referral Dashboard Panel
 *
 * Renders:
 *  - Personal referral QR code and shareable link
 *  - Performance stats (referrals, conversions, earnings)
 *  - FTC-compliant affiliate disclosure
 */

import React, { useEffect, useState } from 'react';

interface ReferralLinkData {
  referral_code: string;
  referral_url: string;
  qr_code_base64: string;
  created_at: string;
}

interface ReferralStats {
  total_referred: number;
  converted: number;
  pending_rewards: number;
  paid_rewards: number;
  total_earned_usd: number;
  reward_per_conversion_usd: number;
}

async function fetchReferralLink(): Promise<ReferralLinkData> {
  const res = await fetch('/api/referral/link', {
    headers: { Authorization: `Bearer ${localStorage.getItem('bv_token') ?? ''}` },
  });
  if (!res.ok) throw new Error(`${res.status}`);
  const body = await res.json();
  return body.data as ReferralLinkData;
}

async function fetchReferralStats(): Promise<ReferralStats> {
  const res = await fetch('/api/referral/stats', {
    headers: { Authorization: `Bearer ${localStorage.getItem('bv_token') ?? ''}` },
  });
  if (!res.ok) throw new Error(`${res.status}`);
  const body = await res.json();
  return body.data as ReferralStats;
}

const StatBox: React.FC<{ label: string; value: string | number }> = ({ label, value }) => (
  <div className="bg-darkNavy border border-gold/20 rounded-lg p-4 text-center">
    <div className="text-2xl font-bold text-gold">{value}</div>
    <div className="text-xs text-light-gray/70 mt-1">{label}</div>
  </div>
);

const SubscriberReferralPanel: React.FC = () => {
  const [linkData, setLinkData] = useState<ReferralLinkData | null>(null);
  const [stats, setStats] = useState<ReferralStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true);

    Promise.all([fetchReferralLink(), fetchReferralStats()])
      .then(([link, s]) => {
        if (!alive) return;
        setLinkData(link);
        setStats(s);
      })
      .catch((e) => {
        if (alive) setError(e.message ?? 'Failed to load referral data');
      })
      .finally(() => {
        if (alive) setLoading(false);
      });

    return () => { alive = false; };
  }, []);

  const copyLink = () => {
    if (!linkData?.referral_url) return;
    navigator.clipboard.writeText(linkData.referral_url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40 text-light-gray/50">
        Loading referral data…
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 border border-red-700/40 rounded-xl p-4 text-red-400 text-sm">
        Failed to load referral panel: {error}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-white">Refer a Friend</h2>
        <p className="text-light-gray/70 text-sm mt-1">
          Share your personal link. Earn{' '}
          <span className="text-gold font-semibold">
            ${stats?.reward_per_conversion_usd ?? 10}/conversion
          </span>{' '}
          when referred users subscribe.
        </p>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <StatBox label="Total Referred" value={stats.total_referred} />
          <StatBox label="Converted" value={stats.converted} />
          <StatBox label="Pending Rewards" value={stats.pending_rewards} />
          <StatBox label="Total Earned" value={`$${stats.total_earned_usd.toFixed(2)}`} />
        </div>
      )}

      {/* QR + Link */}
      {linkData && (
        <div className="bg-charcoal border border-gold/20 rounded-xl p-5 flex flex-col sm:flex-row gap-6 items-center">
          {/* QR Code */}
          <div className="flex-shrink-0">
            <img
              src={`data:image/png;base64,${linkData.qr_code_base64}`}
              alt="Your referral QR code"
              className="w-36 h-36 rounded-lg border border-gold/30"
            />
          </div>

          {/* Link + copy */}
          <div className="flex-1 space-y-3 min-w-0">
            <div className="text-sm text-light-gray/70 font-medium uppercase tracking-wider">
              Your referral link
            </div>
            <div className="bg-darkNavy border border-white/10 rounded-lg px-3 py-2 text-sm font-mono text-light-gray break-all">
              {linkData.referral_url}
            </div>
            <button
              type="button"
              onClick={copyLink}
              className="px-4 py-2 bg-gold text-darkNavy text-sm font-bold rounded-lg hover:bg-gold/90 transition-colors"
            >
              {copied ? 'Copied!' : 'Copy Link'}
            </button>
            <div className="text-xs text-light-gray/40">
              Code: <span className="font-mono">{linkData.referral_code}</span>
            </div>
          </div>
        </div>
      )}

      {/* FTC Disclosure */}
      <div className="bg-darkNavy/60 border border-white/5 rounded-lg p-3 text-xs text-light-gray/50">
        <strong className="text-light-gray/70">Referral Disclosure:</strong> You may earn a reward
        when someone subscribes using your link. Rewards are credited after the referred subscriber's
        first 30-day paid period. Results are not guaranteed. This program is subject to BeatVegas
        Terms of Service.
      </div>
    </div>
  );
};

export default SubscriberReferralPanel;
