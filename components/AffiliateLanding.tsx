import React, { useEffect, useState } from 'react';

// Section 7C — Affiliate landing page at /affiliate-landing
// Dual-tier: Syndicate ($39) + Platform (3-day free trial, then $97)
// Shown when bv_ref cookie is active AND user clicks the affiliate ref link.

function getAffiliateName(): string {
  // bv_ref cookie holds affiliateId; we try to fetch display name
  // Falls back to "a BeatVegas subscriber"
  const match = document.cookie.match(/(?:^|;\s*)bv_ref=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

function getAffiliateCookie(): string {
  const match = document.cookie.match(/(?:^|;\s*)bv_ref=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : '';
}

function getTrialEndDate(): string {
  const d = new Date();
  d.setDate(d.getDate() + 3);
  return d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric', timeZone: 'America/New_York' }) + ' EDT';
}

export default function AffiliateLanding() {
  const [displayName, setDisplayName] = useState('a BeatVegas subscriber');
  const affiliateId = getAffiliateCookie();
  const trialEndDate = getTrialEndDate();

  useEffect(() => {
    if (!affiliateId) return;
    fetch(`/api/trial/affiliate/${encodeURIComponent(affiliateId)}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data?.display_name) setDisplayName(data.display_name);
      })
      .catch(() => {});
  }, [affiliateId]);

  const syndicate_url = 'https://beatvegas.app/checkout/syndicate';
  const platform_url  = 'https://beatvegas.app/checkout/platform-trial';

  return (
    <div className="min-h-screen bg-[#0a0f1e] flex flex-col items-center justify-start py-12 px-4">
      <div className="w-full max-w-3xl space-y-8">
        {/* Header */}
        <div className="text-center space-y-2">
          <h1 className="text-4xl font-black text-white">
            <span className="bg-gradient-to-r from-yellow-400 to-yellow-300 bg-clip-text text-transparent">BEAT</span>VEGAS
          </h1>
          <p className="text-light-gray text-sm">
            Referred by <span className="text-white font-semibold">{displayName}</span>
          </p>
          <p className="text-light-gray">Choose your plan:</p>
        </div>

        {/* Dual-tier cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Syndicate */}
          <div className="bg-[#0d1220] border border-border-gray rounded-2xl p-7 flex flex-col">
            <p className="text-xs font-bold uppercase tracking-widest text-electric-blue mb-2">Syndicate</p>
            <div className="flex items-baseline gap-1 mb-1">
              <span className="text-3xl font-black text-white">$39</span>
              <span className="text-sm text-light-gray">/month</span>
            </div>
            <ul className="mt-5 space-y-2.5 flex-1 text-sm text-light-gray">
              <li className="flex items-start gap-2"><span className="text-neon-green mt-0.5">✓</span>Telegram Syndicate channel</li>
              <li className="flex items-start gap-2"><span className="text-neon-green mt-0.5">✓</span>10 analyses/month</li>
              <li className="flex items-start gap-2"><span className="text-neon-green mt-0.5">✓</span>Dashboard access</li>
              <li className="flex items-start gap-2"><span className="text-neon-green mt-0.5">✓</span>Cancel any time</li>
              <li className="flex items-start gap-2"><span className="text-light-gray/30 mt-0.5">✗</span><span className="text-light-gray/50">Parlay Architect</span></li>
            </ul>
            <a
              href={syndicate_url}
              className="mt-7 block w-full text-center border border-yellow-400 text-yellow-400 font-bold py-3 rounded-lg hover:bg-yellow-400/10 transition-colors text-sm"
            >
              Subscribe $39/month
            </a>
          </div>

          {/* Platform */}
          <div className="bg-[#0f1525] border border-yellow-400 rounded-2xl p-7 flex flex-col">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-bold uppercase tracking-widest text-yellow-400">Platform</p>
              <span className="text-xs font-bold text-[#0a0e1a] bg-yellow-400 px-2 py-0.5 rounded-full">3 Days Free</span>
            </div>
            <div className="flex items-baseline gap-1 mb-1">
              <span className="text-3xl font-black text-white">$97</span>
              <span className="text-sm text-light-gray">/month after trial</span>
            </div>
            <ul className="mt-5 space-y-2.5 flex-1 text-sm text-light-gray">
              <li className="flex items-start gap-2"><span className="text-neon-green mt-0.5">✓</span>Full platform access</li>
              <li className="flex items-start gap-2"><span className="text-neon-green mt-0.5">✓</span>100 analyses/month</li>
              <li className="flex items-start gap-2"><span className="text-neon-green mt-0.5">✓</span>Parlay Architect</li>
              <li className="flex items-start gap-2"><span className="text-neon-green mt-0.5">✓</span>Telegram included</li>
              <li className="flex items-start gap-2"><span className="text-neon-green mt-0.5">✓</span>Cancel any time</li>
            </ul>
            <a
              href={platform_url}
              className="mt-7 block w-full text-center bg-yellow-400 text-[#0a0e1a] font-bold py-3 rounded-lg hover:bg-yellow-300 transition-colors text-sm"
            >
              Start Free Trial
            </a>
            <p className="text-xs text-light-gray/50 text-center mt-2">
              No charge until {trialEndDate}. Cancel any time.
            </p>
          </div>
        </div>

        {/* Disclosure + NCPG footer */}
        <div className="text-center space-y-2 border-t border-border-gray/20 pt-6">
          <p className="text-xs text-light-gray/50">
            FTC Disclosure: Affiliate referral. Commission paid to referring subscriber.
          </p>
          <p className="text-xs text-light-gray/50">
            BeatVegas provides statistical simulation outputs only — not betting advice.
          </p>
          <p className="text-xs text-light-gray/40">
            Problem gambling help: 1-800-522-4700 |{' '}
            <a href="https://www.ncpgambling.org" target="_blank" rel="noopener noreferrer" className="underline hover:text-light-gray">
              ncpgambling.org
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}
