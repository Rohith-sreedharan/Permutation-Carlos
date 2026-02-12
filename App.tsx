import React from 'react';
import DecisionCommandCenter from './components/DecisionCommandCenter';

export default function App() {
  const handleAuthError = () => {
    console.warn('Authentication required - session expired or missing');
    // In production, could redirect to login or show auth modal
  };

  return <DecisionCommandCenter onAuthError={handleAuthError} />;
}
