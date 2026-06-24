import React from 'react';

/**
 * Privacy Policy — Phase 2B.2
 *
 * Compliance requirements:
 *  • CCPA compliant (California Consumer Privacy Act)
 *  • Data retention period stated
 *  • PII handling documented
 *  • Data deletion process documented
 *  • Accessible at /privacy without authentication
 */
export default function PrivacyPolicy() {
  const lastUpdated = 'June 2025';

  return (
    <div className="min-h-screen bg-[#0a0f1e] text-gray-200 py-12 px-4">
      <div className="max-w-3xl mx-auto">
        <a href="/" className="inline-flex items-center text-sm text-yellow-400 hover:text-yellow-300 mb-8">
          ← Back to BeatVegas
        </a>

        <h1 className="text-3xl font-bold text-white mb-2">Privacy Policy</h1>
        <p className="text-sm text-gray-400 mb-10">Last updated: {lastUpdated}</p>

        <Section title="1. Overview">
          <p>
            BeatVegas ("we," "us," or "our") operates a sports analytics platform. This Privacy
            Policy describes how we collect, use, store, and protect your personal information,
            and explains your rights under applicable law including the California Consumer Privacy
            Act (CCPA) and applicable federal privacy laws.
          </p>
        </Section>

        <Section title="2. Information We Collect">
          <SubSection label="Account Information">
            When you register, we collect: email address, username, password (stored as a
            bcrypt hash — we never store your plaintext password), and optionally your
            subscription tier preferences.
          </SubSection>
          <SubSection label="Usage Data">
            Automatically collected: IP address, browser type, pages visited, feature interactions,
            game analysis views, and timestamps. This data is used to improve the platform and
            enforce our geographic access policy.
          </SubSection>
          <SubSection label="Payment Information">
            Payment is processed by Stripe. We do not store full credit card numbers on our servers.
            We store only Stripe customer IDs and subscription status metadata.
          </SubSection>
          <SubSection label="Analytics Preferences">
            Your saved preferences, tier selections, and platform interaction history (e.g., games
            analyzed, parlay configurations) are stored to personalize your experience.
          </SubSection>
        </Section>

        <Section title="3. How We Use Your Information">
          <ul className="list-disc pl-5 space-y-1 text-sm text-gray-300">
            <li>To provide and maintain the analytics platform.</li>
            <li>To authenticate your identity and secure your account (JWT tokens, 2FA).</li>
            <li>To process subscription payments and billing.</li>
            <li>To enforce geographic access restrictions (US-only).</li>
            <li>To detect and prevent fraud, abuse, and security incidents.</li>
            <li>To send service-related communications (not marketing, unless you opt in).</li>
            <li>To aggregate anonymized analytics for platform improvement (no individual tracking sold).</li>
          </ul>
        </Section>

        <Section title="4. Data Retention">
          <p>We retain your personal data as follows:</p>
          <div className="mt-3 rounded-lg border border-gray-700 overflow-hidden text-sm">
            <table className="w-full">
              <thead className="bg-gray-800 text-gray-300">
                <tr>
                  <th className="text-left p-3">Data Type</th>
                  <th className="text-left p-3">Retention Period</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-700">
                <tr>
                  <td className="p-3">Account information (email, username)</td>
                  <td className="p-3">Until account deletion + 30 days</td>
                </tr>
                <tr>
                  <td className="p-3">Authentication logs</td>
                  <td className="p-3">90 days</td>
                </tr>
                <tr>
                  <td className="p-3">Usage / activity data</td>
                  <td className="p-3">12 months</td>
                </tr>
                <tr>
                  <td className="p-3">IP / geographic access logs</td>
                  <td className="p-3">30 days</td>
                </tr>
                <tr>
                  <td className="p-3">Payment records (Stripe metadata)</td>
                  <td className="p-3">7 years (tax / legal requirement)</td>
                </tr>
                <tr>
                  <td className="p-3">Security incident logs</td>
                  <td className="p-3">2 years</td>
                </tr>
                <tr>
                  <td className="p-3">Analytical preference data</td>
                  <td className="p-3">Until account deletion + 30 days</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-gray-300">
            After the retention period expires, data is permanently deleted or irreversibly anonymized.
          </p>
        </Section>

        <Section title="5. Data Sharing">
          <p>We do not sell your personal information. We share data only with:</p>
          <ul className="list-disc pl-5 mt-3 space-y-1 text-sm text-gray-300">
            <li><strong>Stripe</strong> — payment processing (their Privacy Policy governs payment data).</li>
            <li><strong>MongoDB Atlas</strong> — cloud database hosting (SOC 2 Type II certified).</li>
            <li><strong>Law enforcement</strong> — only when legally required by valid court order.</li>
          </ul>
          <p className="mt-3 text-gray-300">
            We do not share your data with advertising networks, data brokers, or analytics companies
            for commercial purposes.
          </p>
        </Section>

        <Section title="6. Your Rights (CCPA + General)">
          <p>You have the right to:</p>
          <ul className="list-disc pl-5 mt-3 space-y-1 text-sm text-gray-300">
            <li><strong>Access:</strong> Request a copy of all personal data we hold about you.</li>
            <li><strong>Deletion:</strong> Request permanent deletion of your account and associated data.</li>
            <li><strong>Correction:</strong> Request correction of inaccurate personal data.</li>
            <li><strong>Portability:</strong> Receive your data in a structured, machine-readable format.</li>
            <li><strong>Opt-out of sale:</strong> We do not sell your data. No opt-out required.</li>
            <li><strong>Non-discrimination:</strong> We will not deny services or charge different prices based on the exercise of your privacy rights.</li>
          </ul>
        </Section>

        <Section title="7. How to Delete Your Account">
          <p>To permanently delete your account and all associated personal data:</p>
          <ol className="list-decimal pl-5 mt-3 space-y-2 text-sm text-gray-300">
            <li>Log into your BeatVegas account.</li>
            <li>Navigate to <strong>Settings → Account → Delete Account</strong>.</li>
            <li>Confirm deletion. Your account will be scheduled for permanent deletion within <strong>30 days</strong>.</li>
          </ol>
          <p className="mt-3 text-gray-300">
            Alternatively, you may email <a href="mailto:privacy@beatvegas.app" className="text-yellow-400 underline">privacy@beatvegas.app</a> with
            the subject line "Account Deletion Request" from your registered email address.
          </p>
          <p className="mt-3 text-gray-400 text-xs">
            Note: Payment records may be retained for up to 7 years as required by law. Anonymized
            aggregate analytics data is not subject to deletion requests.
          </p>
        </Section>

        <Section title="8. Security">
          <p>
            We implement industry-standard security measures including:
          </p>
          <ul className="list-disc pl-5 mt-3 space-y-1 text-sm text-gray-300">
            <li>All data in transit encrypted via TLS 1.2+ (HTTPS enforced via HSTS).</li>
            <li>Passwords hashed with bcrypt (never stored in plaintext).</li>
            <li>Access tokens use signed JWTs with expiry (no plaintext tokens).</li>
            <li>Two-factor authentication (2FA) available on all accounts.</li>
            <li>Geographic access restrictions (US-only enforcement via MaxMind GeoIP).</li>
            <li>Rate limiting on all API endpoints.</li>
            <li>Continuous security monitoring via internal Sentinel system.</li>
          </ul>
        </Section>

        <Section title="9. Cookies">
          <p>
            BeatVegas does not currently use third-party tracking cookies. We use browser
            localStorage for session management (authentication token storage) and user
            preference persistence. No cross-site tracking identifiers are used.
          </p>
        </Section>

        <Section title="10. Children's Privacy">
          <p>
            The Platform is not directed at children under 18. We do not knowingly collect personal
            information from minors. If you believe a minor has registered, please contact us at{' '}
            <a href="mailto:privacy@beatvegas.app" className="text-yellow-400 underline">
              privacy@beatvegas.app
            </a>{' '}
            and we will promptly delete the account.
          </p>
        </Section>

        <Section title="11. Contact Us">
          <p>
            For privacy inquiries, data access requests, or deletion requests:
          </p>
          <ul className="list-none mt-3 space-y-1 text-sm text-gray-300">
            <li>Email: <a href="mailto:privacy@beatvegas.app" className="text-yellow-400 underline">privacy@beatvegas.app</a></li>
            <li>Response time: Within 45 days of receiving a verifiable request (CCPA requirement).</li>
          </ul>
        </Section>

        <div className="mt-12 pt-8 border-t border-gray-700 text-xs text-gray-500">
          <p>
            © {new Date().getFullYear()} BeatVegas. All rights reserved. BeatVegas is a sports
            analytics platform, not a sportsbook. No wagering services are offered.
          </p>
          <div className="flex gap-4 mt-2">
            <a href="/terms" className="text-yellow-400 hover:underline">Terms of Service</a>
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

function SubSection({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mt-3">
      <p className="font-medium text-gray-200 mb-1">{label}</p>
      <p className="text-gray-300 text-sm leading-relaxed">{children}</p>
    </div>
  );
}
