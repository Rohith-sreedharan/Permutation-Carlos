import React, { useState, useEffect } from 'react';
import MainLayout from './components/MainLayout';
import AuthPage from './components/AuthPage';
import TermsOfService from './components/TermsOfService';
import PrivacyPolicy from './components/PrivacyPolicy';
import WaitlistPage from './components/WaitlistPage';

// Public routes — accessible without authentication
const PUBLIC_ROUTES: Record<string, React.FC> = {
  '/terms': TermsOfService,
  '/privacy': PrivacyPolicy,
  '/waitlist': WaitlistPage,
};

export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);

  useEffect(() => {
    const token = localStorage.getItem('authToken');
    setIsAuthenticated(!!token);
  }, []);

  const handleAuthError = () => {
    console.warn('Authentication required - session expired or missing');
    localStorage.removeItem('authToken');
    setIsAuthenticated(false);
  };

  const handleAuthSuccess = () => {
    setIsAuthenticated(true);
  };

  // Public routes — no auth gate, rendered immediately
  const pathname = window.location.pathname;
  const PublicPage = PUBLIC_ROUTES[pathname];
  if (PublicPage) {
    return <PublicPage />;
  }

  // Show loading while checking auth state
  if (isAuthenticated === null) {
    return (
      <div className="min-h-screen bg-[#0a0f1e] flex items-center justify-center">
        <div className="animate-spin w-8 h-8 border-2 border-gold border-t-transparent rounded-full" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <AuthPage onAuthSuccess={handleAuthSuccess} />;
  }

  return <MainLayout onAuthError={handleAuthError} />;
}

