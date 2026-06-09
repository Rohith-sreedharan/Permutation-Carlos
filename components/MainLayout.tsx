import React, { useEffect, useState } from 'react';
import Sidebar from './Sidebar';
import Dashboard from './Dashboard';
import GameDetail from './GameDetail';
import Leaderboard from './Leaderboard';
import Community from './Community';
import AdminPanel from './AdminPanel';
import TrustLoop from './TrustLoop';
import ParlayArchitect from './ParlayArchitect';
import Affiliates from './Affiliates';
import Settings from './Settings';
import TelegramConnection from './TelegramConnection';
import WarRoom from './WarRoom';
import WarRoomLeaderboard from './WarRoomLeaderboard';
import SubscriptionPlans from './SubscriptionPlans';
import Profile from './Profile';
import AffiliateWallet from './AffiliateWallet';
import AffiliateRecruitmentPopup from './AffiliateRecruitmentPopup';
import type { Page } from '../types';

// ── Phase 13: Trial Banner ─────────────────────────────────────────────────
// Shown to users with an active affiliate trial. One-click cancel.
// Fetches trial status from /api/trial/status on mount.
interface TrialStatus {
  trial_active: boolean;
  trial_ends_at?: string;
  charge_display?: string;
  stripe_subscription_id?: string;
}

function TrialBanner({ onCancelComplete }: { onCancelComplete: () => void }) {
  const [trialStatus, setTrialStatus] = useState<TrialStatus | null>(null);
  const [cancelling, setCancelling] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
    if (!token) return;

    fetch('/api/trial/status', {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.json())
      .then((data: TrialStatus) => {
        if (data.trial_active) setTrialStatus(data);
      })
      .catch(() => { /* silent — banner is supplementary */ });
  }, []);

  const handleCancel = async () => {
    if (!trialStatus?.stripe_subscription_id) return;
    setCancelling(true);
    const token = localStorage.getItem('authToken') || sessionStorage.getItem('authToken');
    try {
      const resp = await fetch('/api/trial/cancel', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ stripe_subscription_id: trialStatus.stripe_subscription_id }),
      });
      if (resp.ok) {
        setTrialStatus(null);
        onCancelComplete();
      }
    } catch {
      // silent — let user retry
    } finally {
      setCancelling(false);
    }
  };

  if (!trialStatus?.trial_active || dismissed) return null;

  return (
    <div className="w-full bg-[#1e2d0a] border-b border-[#3d5c14] px-4 py-2 flex items-center justify-between gap-4 shrink-0">
      <p className="text-[#9dc94a] text-xs leading-tight">
        <span className="font-bold">Free trial active</span>
        {trialStatus.charge_display ? (
          <> — your card will be charged <strong className="text-white">$97/month</strong> on{' '}
            <strong className="text-white">{trialStatus.charge_display}</strong> unless you cancel first.</>
        ) : null}
      </p>
      <div className="flex items-center gap-3 shrink-0">
        <button
          onClick={handleCancel}
          disabled={cancelling}
          className="text-xs text-[#bc993c] underline hover:text-[#d4aa42] disabled:opacity-50 whitespace-nowrap"
        >
          {cancelling ? 'Cancelling…' : 'Cancel Trial'}
        </button>
        <button
          onClick={() => setDismissed(true)}
          aria-label="Dismiss"
          className="text-[#4a5568] hover:text-[#6b7784] text-sm"
        >
          ×
        </button>
      </div>
    </div>
  );
}

interface MainLayoutProps {
  onAuthError: () => void;
}

const MainLayout: React.FC<MainLayoutProps> = ({ onAuthError }) => {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [userRole] = useState<'creator' | 'user'>('user');
  const [isAdmin] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [trialCancelled, setTrialCancelled] = useState(false);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const gameId = params.get('gameId');
    if (gameId) {
      setSelectedGameId(gameId);
    }
  }, []);

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    window.location.reload();
  };

  const clearSelectedGame = () => {
    setSelectedGameId(null);
    const url = new URL(window.location.href);
    if (url.searchParams.has('gameId')) {
      url.searchParams.delete('gameId');
      window.history.replaceState({}, '', url.toString());
    }
  };

  const handleGameClick = (gameId: string) => {
    setSelectedGameId(gameId);
    const url = new URL(window.location.href);
    url.searchParams.set('gameId', gameId);
    window.history.replaceState({}, '', url.toString());
    // Stay on current page when viewing game detail
  };

  const renderContent = () => {
    // If a game is selected, show GameDetail
    if (selectedGameId) {
      return (
        <div className="p-0 sm:p-6">
          <GameDetail 
            gameId={selectedGameId} 
            onBack={clearSelectedGame} 
          />
        </div>
      );
    }

    // Otherwise show page content
    switch (currentPage) {
      case 'dashboard':
        return <Dashboard onAuthError={onAuthError} onGameClick={handleGameClick} />;
      
      case 'leaderboard':
        return <Leaderboard />;
      
      case 'community':
        return <Community />;
      
      case 'trust-loop':
        return <TrustLoop />;
      
      case 'architect':
        return <ParlayArchitect />;
      
      case 'affiliates':
        return <Affiliates />;
      
      case 'settings':
        return <Settings />;
      
      case 'telegram':
        return <TelegramConnection />;
      
      case 'war-room':
        return <WarRoom />;
      
      case 'war-room-leaderboard':
        return <WarRoomLeaderboard />;
      
      case 'billing':
        return <SubscriptionPlans />;

      case 'earnings':
        return <AffiliateWallet />;
      
      case 'profile':
        return <Profile />;
      
      case 'wallet':
        return <Profile />;
      
      case 'admin':
        return isAdmin ? <AdminPanel /> : <Dashboard onAuthError={onAuthError} onGameClick={handleGameClick} />;
      
      default:
        return <Dashboard onAuthError={onAuthError} onGameClick={handleGameClick} />;
    }
  };

  return (
    <div className="flex h-screen bg-linear-to-br from-darkNavy via-navy to-black relative flex-col w-full overflow-hidden">
      {/* Mobile Top Bar */}
      <div className="md:hidden sticky top-0 z-50 flex items-center justify-between p-3 bg-charcoal/95 backdrop-blur border-b border-white/10 shrink-0 w-full">
        <div className="flex items-center space-x-2">
          <img src="/logo.png" alt="Logo" className="h-8 w-auto object-contain" />
          <h1 className="text-xl font-bold text-white font-teko tracking-wider">BEATVEGAS</h1>
        </div>
        <button 
          onClick={() => setIsSidebarOpen(!isSidebarOpen)} 
          className="text-white text-2xl p-2 rounded-md hover:bg-white/10 focus:outline-none"
          aria-label={isSidebarOpen ? 'Close menu' : 'Open menu'}
        >
          {isSidebarOpen ? '✖' : '☰'}
        </button>
      </div>

      {/* Phase 13: Trial banner — one-click cancel, FTC requirement */}
      {!trialCancelled && (
        <TrialBanner onCancelComplete={() => setTrialCancelled(true)} />
      )}

      {/* Phase 12 WS7: NCPG responsible gaming disclosure — visible without scroll at 375px */}
      <div className="md:hidden shrink-0 w-full bg-black/60 border-b border-white/5 px-3 py-1.5 text-center">
        <p className="text-[10px] text-gray-500 leading-tight">
          Statistical outputs only. Not betting advice.{' '}
          <a href="https://www.ncpgambling.org" target="_blank" rel="noopener noreferrer" className="text-electric-blue underline">
            Problem gambling help: 1-800-522-4700
          </a>
        </p>
      </div>

      {/* Inner row: sidebar + main content — fills remaining height */}
      <div className="flex flex-1 overflow-hidden">
        {/* Overlay for mobile sidebar */}
        {isSidebarOpen && (
          <div 
            className="md:hidden fixed inset-0 bg-black/70 z-40" 
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        {/* Sidebar - responsive wrapper */}
        <div className={`fixed inset-y-0 left-0 z-50 max-w-[85vw] transform ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:relative md:max-w-none md:translate-x-0 transition duration-200 ease-in-out shadow-2xl md:shadow-none`}>
          <Sidebar
            currentPage={currentPage}
            setCurrentPage={(page) => {
               setCurrentPage(page);
               setIsSidebarOpen(false);
            }}
            onLogout={handleLogout}
            userRole={userRole}
            isAdmin={isAdmin}
          />
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-y-auto p-0 sm:p-6 w-full relative z-0">
          {renderContent()}
        </div>
      </div>
      <AffiliateRecruitmentPopup />
    </div>
  );
};

export default MainLayout;
