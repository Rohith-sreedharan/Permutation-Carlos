import React, { useState, useEffect } from 'react';
import MainLayout from './components/MainLayout';
import AuthPage from './components/AuthPage';
import OnboardingWizard from './components/OnboardingWizard';
import TermsOfService from './components/TermsOfService';
import PrivacyPolicy from './components/PrivacyPolicy';
import WaitlistPage from './components/WaitlistPage';
import PerformancePage from './components/PerformancePage';
import OpsDashboard from './components/OpsDashboard';
import BecomeAffiliatePage from './components/BecomeAffiliatePage';
import AffiliateApplicantsPanel from './components/AffiliateApplicantsPanel';
import UpgradePage from './components/UpgradePage';
import AffiliateLanding from './components/AffiliateLanding';
import { getOnboardingStatus, getToken, removeToken } from './services/api';

// ── Phase 13: Deep link — /ref/:affiliateId ────────────────────────────────
// /ref/:affiliateId now redirects to /affiliate-landing?ref={affiliateId}.
// Also sets bv_ref cookie (24h trial offer + 30-day attribution).
// Section 7B: fires attribution DB write at CLICK TIME via backend API.
function extractAffiliateFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/ref\/([A-Za-z0-9_-]+)$/);
  if (!match) return null;
  const affiliateId = match[1];
  // 24-hour cookie for trial offer interception
  document.cookie = `bv_ref=${encodeURIComponent(affiliateId)}; max-age=86400; path=/; SameSite=Lax`;
  // Section 7B: record attribution at click time — 30-day window
  fetch(`/api/trial/ref/${encodeURIComponent(affiliateId)}`, { method: 'GET' }).catch(() => {});
  return affiliateId;
}

// Public routes — accessible without authentication
const PUBLIC_ROUTES: Record<string, React.FC> = {
  '/terms': TermsOfService,
  '/privacy': PrivacyPolicy,
  '/waitlist': WaitlistPage,
  '/join': WaitlistPage,          // Phase 12 WS3 alias
  '/performance': PerformancePage,
  '/ops/dashboard': OpsDashboard,
  '/become-affiliate': BecomeAffiliatePage,
  '/ops/affiliate-applicants': AffiliateApplicantsPanel,
  '/upgrade': UpgradePage,        // Section 6 — pricing page
  '/pricing': UpgradePage,        // alias
  '/affiliate-landing': AffiliateLanding, // Section 7C — dual-tier affiliate landing
};

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  // null = not yet checked, true = complete, false = needs onboarding
  const [onboardingComplete, setOnboardingComplete] = useState<boolean | null>(null);
  // Section 10: session expiry flag — shown on AuthPage after 401 redirect
  const [sessionExpiredMsg, setSessionExpiredMsg] = useState(false);

  useEffect(() => {
    // Phase 12 WS4: Use the Safari-resilient getToken (localStorage + sessionStorage fallback)
    const token = getToken();
    const authed = !!token;
    setIsAuthenticated(authed);

    // Phase 12 WS4: Listen for token expiry events emitted by the API layer.
    // On expiry, wipe auth state and show the login screen cleanly — no broken UI.
    const handleTokenExpiry = () => {
      setSessionExpiredMsg(true);
      setIsAuthenticated(false);
      setOnboardingComplete(null);
    };
    window.addEventListener('beatvegas:auth:expired', handleTokenExpiry);

    if (authed) {
      // Phase 5A: check onboarding gate immediately after auth confirmation
      getOnboardingStatus()
        .then(s => setOnboardingComplete(s.onboarding_complete))
        .catch(() => {
          // If status check fails (e.g. network), default to assuming complete
          // so existing users are not locked out on transient errors.
          setOnboardingComplete(true);
        });
    }

    return () => {
      window.removeEventListener('beatvegas:auth:expired', handleTokenExpiry);
    };
  }, []);

  const handleAuthError = () => {
    console.warn('Authentication required - session expired or missing');
    removeToken(); // Phase 12 WS4: clears both localStorage and sessionStorage
    setSessionExpiredMsg(true);
    setIsAuthenticated(false);
    setOnboardingComplete(null);
  };

  const handleAuthSuccess = () => {
    setSessionExpiredMsg(false);
    setIsAuthenticated(true);
    // Re-check onboarding status for newly logged-in user
    getOnboardingStatus()
      .then(s => setOnboardingComplete(s.onboarding_complete))
      .catch(() => setOnboardingComplete(true));
  };

  const handleOnboardingComplete = () => {
    setOnboardingComplete(true);
  };

  // Public routes — no auth gate, rendered immediately
  const pathname = window.location.pathname;

  // Phase 14.5 A-02: /ref/:affiliateId redirects to /affiliate-landing?ref={id}
  const affiliateId = extractAffiliateFromPath(pathname);
  if (affiliateId) {
    window.location.replace(`/affiliate-landing?ref=${encodeURIComponent(affiliateId)}`);
    return null;
  }

  const PublicPage = PUBLIC_ROUTES[pathname];
  if (PublicPage) {
    return <PublicPage />;
  }

  // Show loading while checking auth state (or onboarding state for authed users)
  if (isAuthenticated === null || (isAuthenticated && onboardingComplete === null)) {
    return (
      <div className="min-h-screen bg-[#0a0f1e] flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-gold border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthPage onAuthSuccess={handleAuthSuccess} sessionExpired={sessionExpiredMsg} />;
  }

  // Phase 5A AC-2: Gate dashboard behind onboarding wizard
  if (!onboardingComplete) {
    return <OnboardingWizard onComplete={handleOnboardingComplete} />;
  }

  return <MainLayout onAuthError={handleAuthError} />;
}

