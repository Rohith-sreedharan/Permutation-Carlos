import React from 'react';
import MainLayout from './components/MainLayout';

export default function App() {
  const handleAuthError = () => {
    console.warn('Authentication required - session expired or missing');
    // In production, could redirect to login or show auth modal
  };

  return <MainLayout onAuthError={handleAuthError} />;
}
