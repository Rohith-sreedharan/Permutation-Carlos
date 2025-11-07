
import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import Dashboard from './components/Dashboard';
import Community from './components/Community';
import Affiliates from './components/Affiliates';
import Leaderboard from './components/Leaderboard';
import Profile from './components/Profile';
import Wallet from './components/Wallet';
import Settings from './components/Settings';
import AuthPage from './components/AuthPage';
import type { Page } from './types';
import { getToken, removeToken } from './services/api';

const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isAuthCheckComplete, setIsAuthCheckComplete] = useState(false);

  useEffect(() => {
    // Check for an existing token on initial load
    const token = getToken();
    if (token) {
      setIsAuthenticated(true);
    }
    setIsAuthCheckComplete(true);
  }, []);

  const handleLogout = () => {
    removeToken();
    setIsAuthenticated(false);
    setCurrentPage('dashboard');
  };

  const renderPage = () => {
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard onAuthError={handleLogout} />;
      case 'community':
        return <Community />;
      case 'affiliates':
        return <Affiliates />;
      case 'leaderboard':
        return <Leaderboard />;
      case 'profile':
        return <Profile />;
      case 'wallet':
        return <Wallet />;
      case 'settings':
        return <Settings />;
      default:
        return <Dashboard onAuthError={handleLogout} />;
    }
  };

  if (!isAuthCheckComplete) {
    return null; // or a loading spinner
  }

  if (!isAuthenticated) {
    return <AuthPage onAuthSuccess={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="flex min-h-screen bg-navy text-white font-sans">
      <Sidebar 
        currentPage={currentPage} 
        setCurrentPage={setCurrentPage}
        onLogout={handleLogout} 
      />
      <main className="flex-1 p-6 sm:p-8 overflow-y-auto">
        {renderPage()}
      </main>
    </div>
  );
};

export default App;
