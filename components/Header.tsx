
import React, { useState } from 'react';
import type { Page } from '../types';

interface HeaderProps {
  currentPage: Page;
  setCurrentPage: (page: Page) => void;
}

const NavLink: React.FC<{
  page: Page;
  currentPage: Page;
  setCurrentPage: (page: Page) => void;
  children: React.ReactNode;
}> = ({ page, currentPage, setCurrentPage, children }) => {
  const isActive = currentPage === page;
  return (
    <button
      onClick={() => setCurrentPage(page)}
      className={`px-3 py-2 rounded-md text-sm font-medium transition-colors ${
        isActive
          ? 'bg-neon-green text-white'
          : 'text-light-gray hover:bg-navy hover:text-white'
      }`}
    >
      {children}
    </button>
  );
};


const Header: React.FC<HeaderProps> = ({ currentPage, setCurrentPage }) => {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <header className="bg-charcoal shadow-md">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <span className="text-2xl font-bold text-neon-green">
                BeatVegas.AI
              </span>
            </div>
          </div>
          <div className="hidden md:block">
            <div className="ml-10 flex items-baseline space-x-4">
              <NavLink page="dashboard" currentPage={currentPage} setCurrentPage={setCurrentPage}>Dashboard</NavLink>
              <NavLink page="leaderboard" currentPage={currentPage} setCurrentPage={setCurrentPage}>Leaderboard</NavLink>
              <NavLink page="community" currentPage={currentPage} setCurrentPage={setCurrentPage}>Community</NavLink>
              <NavLink page="profile" currentPage={currentPage} setCurrentPage={setCurrentPage}>Profile</NavLink>
            </div>
          </div>
          <div className="-mr-2 flex md:hidden">
            <button
              onClick={() => setIsMenuOpen(!isMenuOpen)}
              className="bg-navy inline-flex items-center justify-center p-2 rounded-md text-light-gray hover:text-white hover:bg-navy focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-gray-800 focus:ring-white"
            >
              <span className="sr-only">Open main menu</span>
              {isMenuOpen ? (
                <svg className="block h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="block h-6 w-6" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>
      {isMenuOpen && (
        <div className="md:hidden">
          <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
            <NavLink page="dashboard" currentPage={currentPage} setCurrentPage={setCurrentPage}>Dashboard</NavLink>
            <NavLink page="leaderboard" currentPage={currentPage} setCurrentPage={setCurrentPage}>Leaderboard</NavLink>
            <NavLink page="community" currentPage={currentPage} setCurrentPage={setCurrentPage}>Community</NavLink>
            <NavLink page="profile" currentPage={currentPage} setCurrentPage={setCurrentPage}>Profile</NavLink>
          </div>
        </div>
      )}
    </header>
  );
};

export default Header;