import React from 'react';

/**
 * Terms of Service — Phase 2B.1
 *
 * Key compliance language:
 *  • Explicitly states BeatVegas is an analytics platform, NOT a sportsbook
 *  • No bet placement, no wagering facilitation, no wallet
 *  • Must be accessible at /terms without authentication
 */
export default function TermsOfService() {
  const lastUpdated = 'June 2025';

  return (
    <div className="min-h-screen bg-[#0a0f1e] text-gray-200 py-12 px-4">
      <div className="max-w-3xl mx-auto">
        <a href="/" className="inline-flex items-center text-sm text-yellow-400 hover:text-yellow-300 mb-8">
          ← Back to BeatVegas
        </a>

        <h1 className="text-3xl font-bold text-white mb-2">Terms of Service</h1>
        <p className="text-sm text-gray-400 mb-10">Last updated: {lastUpdated}</p>

        {/* ── CRITICAL DISCLAIMER ── */}
        <div className="bg-yellow-900/40 border border-yellow-500/50 rounded-lg p-5 mb-10">
          <p className="text-yellow-300 font-semibold text-sm uppercase tracking-wide mb-2">
            Important Notice — Please Read Before Using This Platform
          </p>
          <p className="text-gray-200 text-sm leading-relaxed">
            BeatVegas is a <strong>sports analytics and decision intelligence platform</strong>.
            It is <strong>not a sportsbook</strong>, not a wagering facilitator, and not a betting
            exchange. BeatVegas does not accept bets, does not hold user funds, does not operate
            a wallet, and does not facilitate any wagering transaction of any kind. All content
            on this platform is for <strong>informational and analytical purposes only</strong>.
          </p>
        </div>

        <Section title="1. Acceptance of Terms">
          <p>
            By accessing or using BeatVegas ("Platform"), you agree to be bound by these Terms of
            Service ("Terms"). If you do not agree to these Terms, do not use the Platform.
          </p>
          <p className="mt-3">
            You must be at least 18 years of age to use this Platform. Use of the Platform is
            void where prohibited by applicable law.
          </p>
        </Section>

        <Section title="2. Nature of the Platform — No Wagering">
          <p>
            BeatVegas is an <strong>analytics intelligence platform</strong>. The Platform uses
            Intelligence Cycle analysis, statistical modeling, and algorithmic decision engines to
            generate analytical outputs about sporting events. These outputs include probability
            estimates, edge classifications, and confidence indicators.
          </p>
          <ul className="list-disc pl-5 mt-3 space-y-1 text-sm text-gray-300">
            <li>BeatVegas does <strong>not</strong> accept, process, or facilitate bets or wagers.</li>
            <li>BeatVegas does <strong>not</strong> operate a sportsbook or gambling service.</li>
            <li>BeatVegas does <strong>not</strong> hold user funds or operate any form of wallet.</li>
            <li>BeatVegas does <strong>not</strong> guarantee any financial outcome or profit.</li>
            <li>
              Analytical outputs are <strong>not financial advice</strong> and should not be
              construed as a recommendation to wager any amount of money.
            </li>
          </ul>
          <p className="mt-3 text-gray-300">
            Any decision to engage in sports wagering — whether legal in your jurisdiction or not —
            is made entirely at your own risk and discretion. BeatVegas bears no responsibility for
            any wager placed based on Platform content.
          </p>
        </Section>

        <Section title="3. Eligibility and Geographic Restrictions">
          <p>
            The Platform is available to residents of the United States, excluding its unincorporated
            territories (Puerto Rico, the U.S. Virgin Islands, Guam, the Northern Mariana Islands,
            and American Samoa). Access from outside the United States is prohibited.
          </p>
          <p className="mt-3">
            You represent and warrant that your use of the Platform complies with all laws
            applicable in your jurisdiction.
          </p>
        </Section>

        <Section title="4. Subscription Services">
          <p>
            BeatVegas offers subscription plans with varying levels of analytical access. Subscription
            fees are billed in advance on a recurring basis. You may cancel your subscription at any
            time. Refunds are handled in accordance with our Refund Policy.
          </p>
          <p className="mt-3">
            Subscription fees are <strong>payments for software access only</strong>, not for any
            form of wagering service or gaming product.
          </p>
        </Section>

        <Section title="5. Prohibited Uses">
          <p>You agree not to:</p>
          <ul className="list-disc pl-5 mt-3 space-y-1 text-sm text-gray-300">
            <li>Use the Platform in any jurisdiction where sports analytics services are prohibited.</li>
            <li>Scrape, crawl, or systematically copy Platform data without written permission.</li>
            <li>Attempt to reverse-engineer, decompile, or extract the Platform's algorithms.</li>
            <li>Share account credentials or resell analytical outputs.</li>
            <li>Use automated systems to access the Platform in excess of published rate limits.</li>
            <li>Represent BeatVegas analytical outputs as guaranteed predictions or investment advice.</li>
          </ul>
        </Section>

        <Section title="6. Intellectual Property">
          <p>
            All Platform content — including simulation models, edge classification algorithms,
            analytics outputs, and user interface elements — is the proprietary intellectual
            property of BeatVegas. No license to copy, redistribute, or create derivative works
            is granted.
          </p>
        </Section>

        <Section title="7. Disclaimer of Warranties">
          <p>
            The Platform is provided "as is" and "as available" without any warranty of any kind,
            express or implied. BeatVegas does not warrant that analytical outputs will be accurate,
            complete, or reliable, or that any particular outcome will occur in any sporting event.
          </p>
        </Section>

        <Section title="8. Limitation of Liability">
          <p>
            To the maximum extent permitted by applicable law, BeatVegas shall not be liable for
            any indirect, incidental, special, consequential, or punitive damages, including
            loss of profits, loss of data, or financial losses resulting from reliance on
            Platform content.
          </p>
        </Section>

        <Section title="9. Responsible Use">
          <p>
            If you choose to engage in sports wagering — in jurisdictions where it is legal — we
            strongly encourage responsible behavior:
          </p>
          <ul className="list-disc pl-5 mt-3 space-y-1 text-sm text-gray-300">
            <li>Set strict financial limits before wagering.</li>
            <li>Never wager money you cannot afford to lose.</li>
            <li>Seek help if gambling is negatively affecting your life.</li>
            <li>
              Contact the National Council on Problem Gambling:{' '}
              <a href="tel:1-800-522-4700" className="text-yellow-400 underline">
                1-800-522-4700
              </a>
              {' '}or visit{' '}
              <a href="https://www.ncpgambling.org" target="_blank" rel="noopener noreferrer" className="text-yellow-400 underline">
                ncpgambling.org
              </a>
            </li>
          </ul>
        </Section>

        <Section title="10. Governing Law">
          <p>
            These Terms are governed by the laws of the State of Delaware, United States, without
            regard to conflict-of-law principles.
          </p>
        </Section>

        <Section title="11. Changes to Terms">
          <p>
            We reserve the right to modify these Terms at any time. Continued use of the Platform
            after changes constitutes acceptance of the revised Terms. We will provide notice of
            material changes via email or Platform notification.
          </p>
        </Section>

        <div className="mt-12 pt-8 border-t border-gray-700 text-xs text-gray-500">
          <p>
            © {new Date().getFullYear()} BeatVegas. All rights reserved. BeatVegas is a sports
            analytics platform, not a sportsbook. No wagering services are offered.
          </p>
          <div className="flex gap-4 mt-2">
            <a href="/privacy" className="text-yellow-400 hover:underline">Privacy Policy</a>
            <a href="/waitlist" className="text-yellow-400 hover:underline">Join Waitlist</a>
          </div>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-8">
      <h2 className="text-lg font-semibold text-white mb-3">{title}</h2>
      <div className="text-sm text-gray-300 leading-relaxed space-y-2">{children}</div>
    </div>
  );
}
