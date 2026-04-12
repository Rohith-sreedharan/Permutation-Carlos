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
        <div className="p-6">
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
    <div className="flex h-screen bg-linear-to-br from-darkNavy via-navy to-black">
      {/* Sidebar */}
      <Sidebar
        currentPage={currentPage}
        setCurrentPage={setCurrentPage}
        onLogout={handleLogout}
        userRole={userRole}
        isAdmin={isAdmin}
      />

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto p-6">
        {renderContent()}
      </div>
    </div>
  );
};

export default MainLayout;
