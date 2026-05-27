import React, { useState, useEffect } from 'react';
import MainLayout from './components/MainLayout';
import AuthPage from './components/AuthPage';
import OnboardingWizard from './components/OnboardingWizard';
import TermsOfService from './components/TermsOfService';
import PrivacyPolicy from './components/PrivacyPolicy';
import WaitlistPage from './components/WaitlistPage';
import PerformancePage from './components/PerformancePage';
import OpsDashboard from './components/OpsDashboard';
import { getOnboardingStatus } from './services/api';

// Public routes — accessible without authentication
const PUBLIC_ROUTES: Record<string, React.FC> = {
  '/terms': TermsOfService,
  '/privacy': PrivacyPolicy,
  '/waitlist': WaitlistPage,
  '/performance': PerformancePage,
  '/ops/dashboard': OpsDashboard,
};

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  // null = not yet checked, true = complete, false = needs onboarding
  const [onboardingComplete, setOnboardingComplete] = useState<boolean | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    const authed = !!token;
    setIsAuthenticated(authed);

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
  }, []);

  const handleAuthError = () => {
    console.warn('Authentication required - session expired or missing');
    localStorage.removeItem('authToken');
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

