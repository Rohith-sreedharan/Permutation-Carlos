import React, { useState, useEffect } from 'react';
import AffiliateDisclosure from './AffiliateDisclosure';
import { submitAffiliateInterest, getSubscriptionStatus } from '../services/api';

const AFFILIATE_ELIGIBLE_TIERS = new Set(['beatvegas_platform', 'beatvegas_syndicate', 'platform', 'syndicate', 'telegram_syndicate']);

const BecomeAffiliatePage: React.FC = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [audienceDesc, setAudienceDesc] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [tierLoading, setTierLoading] = useState(true);
  const [isEligible, setIsEligible] = useState(false);

  useEffect(() => {
    getSubscriptionStatus()
      .then(res => {
        const tier = res.tier || res.plan_id || '';
        setIsEligible(
          Boolean(res.platform_access) ||
          Boolean(res.telegram_access) ||
          AFFILIATE_ELIGIBLE_TIERS.has(tier)
        );
      })
      .catch(() => setIsEligible(false))
      .finally(() => setTierLoading(false));
  }, []);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    setStatus(null);
    try {
      await submitAffiliateInterest({
        name,
        email,
        audience_desc: audienceDesc || null,
      });
      setStatus('Thanks for your interest. We review applications and reach out to selected partners.');
      setName('');
      setEmail('');
      setAudienceDesc('');
    } catch (err: any) {
      setError(err.message || 'Failed to submit application');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="min-h-screen bg-linear-to-br from-darkNavy via-navy to-black text-white px-4 py-10">
      <div className="max-w-2xl mx-auto space-y-6">
        <h1 className="text-4xl font-bold font-teko tracking-wide">Become a BeatVegas Affiliate</h1>

        {tierLoading ? (
          <div className="flex justify-center py-16">
            <div className="animate-spin w-8 h-8 border-2 border-gold border-t-transparent rounded-full" />
          </div>
        ) : !isEligible ? (
          /* ── Subscriber-only gate ──────────────────────────────────────── */
          <div className="bg-charcoal rounded-xl border border-yellow-400/30 p-8 text-center space-y-4">
            <div className="text-3xl">🔒</div>
            <h2 className="text-2xl font-bold font-teko text-white">Affiliate Program — Subscribers Only</h2>
            <p className="text-light-gray text-sm leading-relaxed max-w-md mx-auto">
              The BeatVegas Affiliate Program is available to Platform and Syndicate subscribers.
              Upgrade to Platform to join the affiliate program and earn $30 per conversion.
            </p>
            <a
              href="https://beatvegas.app/upgrade"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block bg-yellow-400 text-[#0a0e1a] font-bold px-6 py-3 rounded-lg hover:bg-yellow-300 transition-colors text-sm mt-2"
            >
              Upgrade to Platform — $97/month
            </a>
          </div>
        ) : (
          /* ── Eligible subscriber — show enrollment form ────────────────── */
          <>
            <p className="text-light-gray">Apply to join the program. Submitting this form does not automatically enroll you.</p>

            <div className="bg-charcoal rounded-lg border border-border-gray p-4">
              <AffiliateDisclosure />
            </div>

            <form onSubmit={onSubmit} className="bg-charcoal rounded-lg border border-border-gray p-6 space-y-4">
              <div>
                <label className="block text-sm text-light-gray mb-2">Name</label>
                <input
                  required
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full bg-navy border border-border-gray rounded-lg px-4 py-2 text-white"
                  placeholder="Your full name"
                />
              </div>
              <div>
                <label className="block text-sm text-light-gray mb-2">Email</label>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full bg-navy border border-border-gray rounded-lg px-4 py-2 text-white"
                  placeholder="you@example.com"
                />
              </div>
              <div>
                <label className="block text-sm text-light-gray mb-2">Audience Description</label>
                <textarea
                  value={audienceDesc}
                  onChange={(e) => setAudienceDesc(e.target.value)}
                  rows={4}
                  className="w-full bg-navy border border-border-gray rounded-lg px-4 py-2 text-white"
                  placeholder="Optional: tell us about your audience"
                />
              </div>
              <button
                type="submit"
                disabled={submitting}
                className="bg-gold text-dark-navy font-semibold px-6 py-2 rounded-lg disabled:opacity-60"
              >
                {submitting ? 'Submitting...' : 'Submit Interest'}
              </button>

              {status && <p className="text-neon-green text-sm">{status}</p>}
              {error && <p className="text-bold-red text-sm">{error}</p>}
            </form>
          </>
        )}
      </div>
    </div>
  );
};

export default BecomeAffiliatePage;
