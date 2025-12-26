
import React, { useState, useEffect } from 'react';
import Sidebar from './components/Sidebar';
import DecisionCommandCenter from './components/DecisionCommandCenter';  // Renamed from Dashboard
import Community from './components/CommunityEnhanced';
import WarRoom from './components/WarRoom';
import WarRoomLeaderboard from './components/WarRoomLeaderboard';
import Affiliates from './components/Affiliates';
import Leaderboard from './components/Leaderboard';
import Profile from './components/Profile';
import SubscriptionSettings from './components/SubscriptionSettings';
import AffiliateWallet from './components/AffiliateWallet';
import DecisionCapitalProfile from './components/DecisionCapitalProfile';
import Settings from './components/Settings';
import TelegramConnection from './components/TelegramConnection';
import AuthPage from './components/AuthPage';
import GameDetail from './components/GameDetail';
import OnboardingWizard from './components/OnboardingWizard';
import RiskAlert from './components/RiskAlert';
import TrustLoop from './components/TrustLoop';  // NEW: Trust & Performance Loop
import ParlayArchitect from './components/ParlayArchitect';  // PHASE 14: AI Parlay Architect
import type { Page } from './types';
import { getToken, removeToken, verifyToken } from './services/api';
import { useWebSocket } from './utils/useWebSocket';

const App: React.FC = () => {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [isAuthCheckComplete, setIsAuthCheckComplete] = useState(false);
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<'creator' | 'user'>('user'); // Track if user is a creator
  const [riskAlert, setRiskAlert] = useState<{
    isOpen: boolean;
    betCount: number;
    timeframe: string;
    unitSize: number;
    recommendedAction: string;
  }>({
    isOpen: false,
    betCount: 0,
    timeframe: '',
    unitSize: 0,
    recommendedAction: ''
  });

  const { subscribe, unsubscribe } = useWebSocket();

  useEffect(() => {
    // SECURITY: Verify token with backend before granting access
    const checkAuth = async () => {
      const token = getToken();
      let cleanup: (() => void) | undefined;
      
      if (token) {
        try {
          // Verify token is valid and user exists in database
          const user = await verifyToken();
          
          // Token is valid and user exists
          setIsAuthenticated(true);

          // Check if onboarding is complete
          const onboardingComplete = localStorage.getItem('onboarding_complete');
          if (!onboardingComplete) {
            setCurrentPage('onboarding');
          }

          // Load user role from localStorage or API
          const role = (localStorage.getItem('user_role') as 'creator' | 'user') || 'user';
          setUserRole(role);

          // Subscribe to risk alerts WebSocket channel
          const handleRiskAlert = (data: any) => {
            if (data.type === 'TILT_DETECTED') {
              const payload = data.payload || {};
              setRiskAlert({
                isOpen: true,
                betCount: payload.bet_count || 3,
                timeframe: payload.timeframe || '10 minutes',
                unitSize: payload.unit_size || 100,
                recommendedAction: payload.recommended_action || 'Take a 1-hour break and review your strategy.'
              });
            }
          };

          subscribe('risk.alert', handleRiskAlert);
          cleanup = () => {
            unsubscribe('risk.alert', handleRiskAlert);
          };
        } catch (error) {
          // Token is invalid, expired, or user doesn't exist
          console.error('[Auth] Token verification failed:', error);
          setIsAuthenticated(false);
          removeToken();
        }
      }
      
      setIsAuthCheckComplete(true);
      return cleanup;
    };
    
    checkAuth();
  }, [subscribe, unsubscribe]);

  const handleLogout = () => {
    removeToken();
    setIsAuthenticated(false);
    setCurrentPage('dashboard');
  };

  const handleGameClick = (gameId: string) => {
    console.log('[App] Game clicked:', gameId);
    setSelectedGameId(gameId);
    setCurrentPage('gameDetail');
  };

  const handleBackToDashboard = () => {
    setSelectedGameId(null);
    setCurrentPage('dashboard');
  };

  const renderPage = () => {
    switch (currentPage) {
      case 'onboarding':
        return (
          <OnboardingWizard
            onComplete={() => setCurrentPage('dashboard')}
            onSkip={() => setCurrentPage('dashboard')}
          />
        );
      case 'dashboard':
        return <DecisionCommandCenter onAuthError={handleLogout} onGameClick={handleGameClick} />;
      case 'gameDetail':
        return selectedGameId ? (
          <GameDetail gameId={selectedGameId} onBack={handleBackToDashboard} />
        ) : (
          <DecisionCommandCenter onAuthError={handleLogout} onGameClick={handleGameClick} />
        );
      case 'community':
        return <Community />;
      case 'war-room':
        return <WarRoom />;
      case 'war-room-leaderboard':
        return <WarRoomLeaderboard />;
      case 'trust-loop':
        return <TrustLoop />;
      case 'architect':
        return <ParlayArchitect />;
      case 'affiliates':
        return <Affiliates />;
      case 'leaderboard':
        return <Leaderboard />;
      case 'profile':
        return <Profile />;
      case 'billing':
        return <SubscriptionSettings />;
      case 'earnings':
        return <AffiliateWallet />;
      case 'wallet':
        // Renamed to Decision Capital Profile
        return <DecisionCapitalProfile onAuthError={handleLogout} />;
      case 'settings':
        return <Settings />;
      case 'telegram':
        return <TelegramConnection />;
      default:
        return <DecisionCommandCenter onAuthError={handleLogout} onGameClick={handleGameClick} />;
    }
  };

  if (!isAuthCheckComplete) {
    return null; // or a loading spinner
  }

  if (!isAuthenticated) {
    return <AuthPage onAuthSuccess={() => setIsAuthenticated(true)} />;
  }

  return (
    <div className="flex min-h-screen bg-dark-navy text-white font-sans">
      {/* Tilt Protection Modal */}
      <RiskAlert 
        isOpen={riskAlert.isOpen}
        onClose={() => setRiskAlert(prev => ({ ...prev, isOpen: false }))}
        betCount={riskAlert.betCount}
        timeframe={riskAlert.timeframe}
        unitSize={riskAlert.unitSize}
        recommendedAction={riskAlert.recommendedAction}
      />

      {/* Hide sidebar on onboarding page */}
      {currentPage !== 'onboarding' && (
        <Sidebar 
          currentPage={currentPage} 
          setCurrentPage={setCurrentPage}
          onLogout={handleLogout}
          userRole={userRole}
        />
      )}
      <main className={`flex-1 p-6 sm:p-8 overflow-y-auto ${currentPage === 'onboarding' ? 'w-full' : ''}`}>
        {renderPage()}
      </main>
    </div>
  );
};

export default App;
