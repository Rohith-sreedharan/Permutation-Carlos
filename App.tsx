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
import { getOnboardingStatus, getToken, removeToken } from './services/api';
// Phase 13 — Affiliate trial landing page
import AffiliateTrial from './components/AffiliateTrial';

// ── Phase 13: Deep link — /ref/:affiliateId ────────────────────────────────
// Phase 13 replaces Phase 12's waitlist redirect.
// Now renders the full 3-day affiliate trial landing page.
// Also sets bv_ref cookie for attribution tracking in case user closes page.
function extractAffiliateFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/ref\/([A-Za-z0-9_-]+)$/);
  if (!match) return null;
  const affiliateId = match[1];
  const maxAge = 30 * 24 * 60 * 60;
  document.cookie = `bv_ref=${encodeURIComponent(affiliateId)}; max-age=${maxAge}; path=/; SameSite=Lax`;
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
};

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  // null = not yet checked, true = complete, false = needs onboarding
  const [onboardingComplete, setOnboardingComplete] = useState<boolean | null>(null);

  useEffect(() => {
    // Phase 12 WS4: Use the Safari-resilient getToken (localStorage + sessionStorage fallback)
    const token = getToken();
    const authed = !!token;
    setIsAuthenticated(authed);

    // Phase 12 WS4: Listen for token expiry events emitted by the API layer.
    // On expiry, wipe auth state and show the login screen cleanly — no broken UI.
    const handleTokenExpiry = () => {
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
    setIsAuthenticated(false);
    setOnboardingComplete(null);
  };

  const handleAuthSuccess = () => {
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

  // Phase 13: /ref/:affiliateId renders affiliate trial landing page
  const affiliateId = extractAffiliateFromPath(pathname);
  if (affiliateId) {
    return <AffiliateTrial affiliateId={affiliateId} />;
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
    return <AuthPage onAuthSuccess={handleAuthSuccess} />;
  }

  // Phase 5A AC-2: Gate dashboard behind onboarding wizard
  if (!onboardingComplete) {
    return <OnboardingWizard onComplete={handleOnboardingComplete} />;
  }

  return <MainLayout onAuthError={handleAuthError} />;
}

