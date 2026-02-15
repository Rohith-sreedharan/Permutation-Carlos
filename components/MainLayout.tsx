import React, { useState } from 'react';
import Sidebar from './Sidebar';
import Dashboard from './Dashboard';
import DecisionCommandCenter from './DecisionCommandCenter';
import GameDetail from './GameDetail';
import Leaderboard from './Leaderboard';
import Community from './Community';
import AdminPanel from './AdminPanel';
import CreatorProfile from './CreatorProfile';
import type { Page } from '../types';

interface MainLayoutProps {
  onAuthError: () => void;
}

const MainLayout: React.FC<MainLayoutProps> = ({ onAuthError }) => {
  const [currentPage, setCurrentPage] = useState<Page>('dashboard');
  const [selectedGameId, setSelectedGameId] = useState<string | null>(null);
  const [userRole] = useState<'creator' | 'user'>('user');
  const [isAdmin] = useState(false);

  const handleLogout = () => {
    localStorage.removeItem('authToken');
    window.location.reload();
  };

  const handleGameClick = (gameId: string) => {
    setSelectedGameId(gameId);
    // Stay on current page when viewing game detail
  };

  const renderContent = () => {
    // If a game is selected, show GameDetail
    if (selectedGameId) {
      return (
        <div className="p-6">
          <GameDetail 
            gameId={selectedGameId} 
            onBack={() => setSelectedGameId(null)} 
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
      
      case 'admin':
        return isAdmin ? <AdminPanel /> : <Dashboard onAuthError={onAuthError} onGameClick={handleGameClick} />;
      
      case 'profile':
        return (
          <CreatorProfile 
            username="user" 
            onTailParlay={(slipId) => console.log('Tail parlay:', slipId)}
            onBack={() => setCurrentPage('dashboard')}
          />
        );
      
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
      <div className="flex-1 overflow-y-auto">
        {renderContent()}
      </div>
    </div>
  );
};

export default MainLayout;
