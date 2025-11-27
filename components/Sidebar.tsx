import React from 'react';
import type { Page } from '../types';

interface SidebarProps {
  currentPage: Page;
  setCurrentPage: (page: Page) => void;
  onLogout: () => void;
  userRole?: 'creator' | 'user'; // Pass user role to conditionally show Earnings vs Billing
}

const NavLink: React.FC<{
  page?: Page;
  onClick?: () => void;
  currentPage?: Page;
  setCurrentPage?: (page: Page) => void;
  icon: React.ReactNode;
  children: React.ReactNode;
}> = ({ page, onClick, currentPage, setCurrentPage, icon, children }) => {
  const isActive = page && currentPage === page;
  
  const handleClick = () => {
    if (onClick) {
      onClick();
    } else if (page && setCurrentPage) {
      setCurrentPage(page);
    }
  };

  return (
    <button
      onClick={handleClick}
      className={`flex items-center space-x-3 w-full px-4 py-3 rounded-lg text-left transition-colors ${
        isActive
          ? 'bg-gold text-darkNavy'
          : 'text-light-gray hover:bg-navy hover:text-white'
      }`}
      aria-current={isActive ? 'page' : undefined}
    >
      {icon}
      <span className="font-semibold">{children}</span>
    </button>
  );
};

const Sidebar: React.FC<SidebarProps> = ({ currentPage, setCurrentPage, onLogout, userRole = 'user' }) => {
  return (
    <aside className="w-64 bg-charcoal p-4 flex-col space-y-2 sticky top-0 h-screen hidden sm:flex">
      <div className="text-center py-4 flex flex-col items-center">
        <img 
          src="/logo.png" 
          alt="BeatVegas Logo" 
          className="h-16 w-auto mb-2 object-contain"
        />
        <h1 className="text-4xl font-bold text-white font-teko tracking-wider">BEATVEGAS</h1>
        <p className="text-xs text-light-gray">SPORTS INTELLIGENCE</p>
      </div>
      
      <nav className="flex-1 flex flex-col space-y-2 pt-4">
        <NavLink page="dashboard" currentPage={currentPage} setCurrentPage={setCurrentPage} icon={<DashboardIcon />}>Command Center</NavLink>
        <NavLink page="architect" currentPage={currentPage} setCurrentPage={setCurrentPage} icon={<ArchitectIcon />}>Parlay Architect</NavLink>
        <NavLink page="trust-loop" currentPage={currentPage} setCurrentPage={setCurrentPage} icon={<TrustLoopIcon />}>Trust Loop</NavLink>
        <NavLink page="leaderboard" currentPage={currentPage} setCurrentPage={setCurrentPage} icon={<LeaderboardIcon />}>Leaderboard</NavLink>
        <NavLink page="community" currentPage={currentPage} setCurrentPage={setCurrentPage} icon={<CommunityIcon />}>Community</NavLink>
        <NavLink page="affiliates" currentPage={currentPage} setCurrentPage={setCurrentPage} icon={<AffiliatesIcon />}>Affiliates</NavLink>
        
        <div className="pt-4 border-t border-navy mt-2">
            <p className="px-4 text-xs font-semibold text-light-gray/50 uppercase tracking-wider mb-2">Account</p>
            <NavLink page="profile" currentPage={currentPage} setCurrentPage={setCurrentPage} icon={<ProfileIcon />}>Profile</NavLink>
            
            {/* Conditional: Show Earnings for creators, Billing for everyone */}
            {userRole === 'creator' ? (
              <NavLink page="earnings" currentPage={currentPage} setCurrentPage={setCurrentPage} icon={<EarningsIcon />}>Earnings</NavLink>
            ) : (
              <NavLink page="billing" currentPage={currentPage} setCurrentPage={setCurrentPage} icon={<BillingIcon />}>Billing</NavLink>
            )}
            
            <NavLink page="wallet" currentPage={currentPage} setCurrentPage={setCurrentPage} icon={<RiskProfileIcon />}>Risk Profile</NavLink>
            <NavLink page="settings" currentPage={currentPage} setCurrentPage={setCurrentPage} icon={<SettingsIcon />}>Settings</NavLink>
        </div>
      </nav>

      <div className="mt-auto">
        <NavLink onClick={onLogout} icon={<LogoutIcon />}>Logout</NavLink>
      </div>
    </aside>
  );
};

// --- SVG Icons ---
const IconWrapper: React.FC<{children: React.ReactNode}> = ({ children }) => (
    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">{children}</svg>
);

const DashboardIcon = () => <IconWrapper><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" /></IconWrapper>;
const ArchitectIcon = () => <IconWrapper><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z" /></IconWrapper>;
const TrustLoopIcon = () => <IconWrapper><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" /></IconWrapper>;
const LeaderboardIcon = () => <IconWrapper><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></IconWrapper>;
const CommunityIcon = () => <IconWrapper><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" /></IconWrapper>;
const AffiliatesIcon = () => <IconWrapper><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" /></IconWrapper>;
const ProfileIcon = () => <IconWrapper><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></IconWrapper>;
const BillingIcon = () => <IconWrapper><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></IconWrapper>;
const EarningsIcon = () => <IconWrapper><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></IconWrapper>;
const RiskProfileIcon = () => <IconWrapper><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" /></IconWrapper>;
const SettingsIcon = () => <IconWrapper><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /></IconWrapper>;
const LogoutIcon = () => <IconWrapper><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" /></IconWrapper>;

export default Sidebar;
