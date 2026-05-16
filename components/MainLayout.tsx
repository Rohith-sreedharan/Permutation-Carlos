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
import type { Page } from '../types';

interface MainLayoutProps {
  onAuthError: () => void;
}

const MainLayout: React.FC<MainLayoutProps> = ({ onAuthError }) => {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [userRole] = useState<'creator' | 'user'>('user');
  const [isAdmin] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

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
    <div className="flex h-screen bg-linear-to-br from-darkNavy via-navy to-black relative flex-col md:flex-row w-full overflow-hidden">
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
  );
};

export default MainLayout;
