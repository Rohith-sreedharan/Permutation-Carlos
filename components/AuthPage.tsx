import React, { useState, useEffect } from 'react';
import { loginUser, registerUser, verify2FALogin, beginPasskeyLogin, completePasskeyLogin } from '../services/api';
import Swal from 'sweetalert2';

const API_BASE_URL = (import.meta as any).env?.VITE_API_BASE_URL || 'http://localhost:8000';
const APPLE_CLIENT_ID = (import.meta as any).env?.VITE_APPLE_CLIENT_ID || '';

interface AuthPageProps {
  onAuthSuccess: () => void;
}

export default function AuthPage({ onAuthSuccess }: AuthPageProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [appleAvailable, setAppleAvailable] = useState(!!APPLE_CLIENT_ID);

  useEffect(() => {
    // Initialise Apple Sign In SDK once it has loaded
    const init = () => {
      const apple = (window as any).AppleID;
      if (apple && APPLE_CLIENT_ID) {
        try {
          apple.auth.init({
            clientId: APPLE_CLIENT_ID,
            scope: 'name email',
            redirectURI: window.location.origin,
            usePopup: true,
          });
          setAppleAvailable(true);
        } catch (_) {
          // SDK not ready — silently skip; button stays hidden
        }
      }
    };

    // If the script is already loaded, init immediately
    if ((window as any).AppleID) {
      init();
    } else {
      // Otherwise wait for DOMContentLoaded / script onload
      window.addEventListener('AppleIDSignInOnSuccess', init);
      const timer = setTimeout(init, 1500);
      return () => {
        window.removeEventListener('AppleIDSignInOnSuccess', init);
        clearTimeout(timer);
      };
    }
  }, []);

  const handleAppleSignIn = async () => {
    setError('');
    setLoading(true);
    try {
      const apple = (window as any).AppleID;
      if (!apple) throw new Error('Apple Sign In is not available in this browser.');
      const result = await apple.auth.signIn();
      const id_token = result?.authorization?.id_token;
      if (!id_token) throw new Error('Apple Sign In did not return a token. Please try again.');

      const resp = await fetch(`${API_BASE_URL}/api/v1/auth/apple`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id_token }),
      });
      const data = await resp.json();
      if (!resp.ok) {
        throw new Error(data.detail || 'Apple Sign In failed. Please try again.');
      }
      if (data.access_token) {
        localStorage.setItem('authToken', data.access_token);
        onAuthSuccess();
      } else {
        throw new Error('Sign in failed. Please try again.');
      }
    } catch (err: any) {
      // Apple SDK throws {error: 'popup_closed_by_user'} when user cancels — don't show an error
      if (err?.error === 'popup_closed_by_user' || err?.error === 'user_cancelled_authorize') {
        // User dismissed — silent
      } else {
        setError(err.message || 'Apple Sign In failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleBiometricLogin = async () => {
    if (!email) {
      setError('Please enter your email first');
      return;
    }

    setError('');
    setLoading(true);

    try {
      // Check if browser supports WebAuthn
      if (!window.PublicKeyCredential) {
        throw new Error('Your browser does not support biometric authentication');
      }

      // Start passkey login
      const options = await beginPasskeyLogin(email);

      // Convert challenge from base64
      const challenge = Uint8Array.from(atob(options.challenge), c => c.charCodeAt(0));

      // Get credential from authenticator
      const credential = await navigator.credentials.get({
        publicKey: {
          challenge,
          rpId: 'localhost',
          userVerification: 'preferred',
          timeout: 60000,
        }
      }) as any;

      if (!credential) {
        throw new Error('Authentication cancelled');
      }

      // Prepare credential data for server
      const credentialData = {
        id: credential.id,
        rawId: btoa(String.fromCharCode(...new Uint8Array(credential.rawId))),
        response: {
          clientDataJSON: btoa(String.fromCharCode(...new Uint8Array(credential.response.clientDataJSON))),
          authenticatorData: btoa(String.fromCharCode(...new Uint8Array(credential.response.authenticatorData))),
          signature: btoa(String.fromCharCode(...new Uint8Array(credential.response.signature))),
        },
        type: credential.type,
      };

      // Complete login
      const response = await completePasskeyLogin(email, credentialData);
      
      if (response.access_token) {
        localStorage.setItem('authToken', response.access_token);
        onAuthSuccess();
      } else {
        throw new Error('Login failed');
      }
    } catch (err: any) {
      setError(err.message || 'Biometric login failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (isLogin) {
        // Login
        const response = await loginUser({ email, password });
        
        // Check if 2FA is required
        if (response.requires_2fa && response.temp_token) {
          setLoading(false);
          
          // Show 2FA prompt
          const result = await Swal.fire({
            title: 'Two-Factor Authentication',
            html: '<input type="text" id="2fa-code" class="swal2-input" placeholder="Enter 6-digit code" maxlength="6" style="background: #1a2332; color: white; border: 1px solid #334155;">',
            showCancelButton: true,
            confirmButtonText: 'Verify',
            confirmButtonColor: '#00ff88',
            cancelButtonColor: '#ff4444',
            background: '#0f1419',
            color: '#ffffff',
            preConfirm: () => {
              const code = (document.getElementById('2fa-code') as HTMLInputElement).value;
              if (!code || code.length !== 6) {
                Swal.showValidationMessage('Please enter a 6-digit code');
                return false;
              }
              return code;
            }
          });
          
          if (result.isConfirmed && result.value) {
            setLoading(true);
            try {
              const verifyResponse = await verify2FALogin(response.temp_token, result.value);
              if (verifyResponse.access_token) {
                localStorage.setItem('authToken', verifyResponse.access_token);
                onAuthSuccess();
              }
            } catch (err: any) {
              setError(err.message || 'Invalid verification code');
              setLoading(false);
            }
          }
          return;
        }
        
        // Normal login without 2FA
        if (response.access_token) {
          localStorage.setItem('authToken', response.access_token);
          onAuthSuccess();
        } else {
          setError('Login failed. Please try again.');
        }
      } else {
        // Register
        if (password !== confirmPassword) {
          setError('Passwords do not match');
          setLoading(false);
          return;
        }
        const response = await registerUser({ email, username: username || email.split('@')[0], password });
        if (response.access_token) {
          localStorage.setItem('authToken', response.access_token);
          onAuthSuccess();
        } else {
          setError('Registration failed. Please try again.');
        }
      }
    } catch (err: any) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#0a0f1e] relative overflow-hidden flex items-center justify-center">
      {/* Animated background gradient */}
      <div className="absolute inset-0 bg-linear-to-br from-[#1a1f35] via-[#0a0f1e] to-black opacity-90" />
      
      {/* Floating particles */}
      <div className="absolute inset-0 overflow-hidden">
        {[...Array(30)].map((_, i) => (
          <div
            key={i}
            className="absolute w-1 h-1 bg-gold rounded-full animate-pulse"
            style={{
              left: `${Math.random() * 100}%`,
              top: `${Math.random() * 100}%`,
              animationDelay: `${Math.random() * 3}s`,
              opacity: Math.random() * 0.5 + 0.2,
            }}
          />
        ))}
      </div>

      {/* Diagonal grid overlay */}
      <div 
        className="absolute inset-0 opacity-5"
        style={{
          backgroundImage: `linear-gradient(45deg, #FFD700 1px, transparent 1px),
                           linear-gradient(-45deg, #FFD700 1px, transparent 1px)`,
          backgroundSize: '30px 30px'
        }}
      />

      {/* Auth card */}
      <div className="relative z-10 w-full max-w-md mx-4">
        {/* Brand header */}
        <div className="text-center mb-8">
          <h1 className="text-6xl font-black mb-2 bg-linear-to-r from-gold via-yellow-300 to-gold bg-clip-text text-transparent animate-pulse">
            BEATVEGAS
          </h1>
          <p className="text-sm text-gray-400 tracking-wider uppercase">
            Sports Intelligence
          </p>
        </div>

        {/* Card */}
        <div className="bg-linear-to-b from-navy/80 to-[#0a0f1e]/80 backdrop-blur-xl rounded-2xl shadow-2xl border border-gold/20 p-8">
          {/* Tab selector */}
          <div className="flex mb-8 bg-black/30 rounded-lg p-1">
            <button
              onClick={() => setIsLogin(true)}
              className={`flex-1 py-3 rounded-lg font-semibold transition-all ${
                isLogin
                  ? 'bg-linear-to-r from-gold to-yellow-500 text-black'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => setIsLogin(false)}
              className={`flex-1 py-3 rounded-lg font-semibold transition-all ${
                !isLogin
                  ? 'bg-linear-to-r from-gold to-yellow-500 text-black'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Sign Up
            </button>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-3 bg-black/30 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:border-gold focus:ring-2 focus:ring-gold/20 transition-all"
                placeholder="you@example.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full px-4 py-3 pr-16 bg-black/30 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:border-gold focus:ring-2 focus:ring-gold/20 transition-all"
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-300 hover:text-white"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? 'Hide' : 'Show'}
                </button>
              </div>
            </div>

            {!isLogin && (
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Username
                </label>
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full px-4 py-3 bg-black/30 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:border-gold focus:ring-2 focus:ring-gold/20 transition-all"
                  placeholder="username (optional)"
                />
              </div>
            )}

            {!isLogin && (
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Confirm Password
                </label>
                <div className="relative">
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    className="w-full px-4 py-3 pr-16 bg-black/30 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:border-gold focus:ring-2 focus:ring-gold/20 transition-all"
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword((v) => !v)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-300 hover:text-white"
                    aria-label={showConfirmPassword ? 'Hide confirm password' : 'Show confirm password'}
                  >
                    {showConfirmPassword ? 'Hide' : 'Show'}
                  </button>
                </div>
              </div>
            )}

            {error && (
              <div className="bg-red-900/20 border border-red-500/50 rounded-lg p-3 text-red-400 text-sm">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-linear-to-r from-gold via-yellow-400 to-gold text-black font-bold py-4 rounded-lg hover:shadow-2xl hover:shadow-gold/50 transition-all transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="flex items-center justify-center">
                  <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Processing...
                </span>
              ) : (
                isLogin ? 'Sign In' : 'Create Account'
              )}
            </button>

            {/* Biometric Login - Only show on login, not signup */}
            {isLogin && window.PublicKeyCredential && (
              <>
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-gray-700"></div>
                  </div>
                  <div className="relative flex justify-center text-sm">
                    <span className="px-2 bg-[#0f1419] text-gray-400">or</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={handleBiometricLogin}
                  disabled={loading || !email}
                  className="w-full bg-linear-to-r from-blue-600 to-blue-500 text-white font-semibold py-4 rounded-lg hover:shadow-xl hover:shadow-blue-500/30 transition-all transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  <span className="text-xl">🔐</span>
                  Sign In with Face ID / Touch ID
                </button>

                {!email && (
                  <p className="text-xs text-gray-500 text-center -mt-2">
                    Enter your email first to use biometric login
                  </p>
                )}
              </>
            )}
          </form>

          {/* Footer */}
          <div className="mt-6 text-center">
            <p className="text-xs text-gray-500">
              By continuing, you agree to our Terms of Service
            </p>
          </div>

          {/* Phase 12 WS2 — Apple Sign In */}
          {appleAvailable && (
            <div className="mt-4">
              <div className="relative mb-4">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-gray-700"></div>
                </div>
                <div className="relative flex justify-center text-sm">
                  <span className="px-2 bg-[#0f1419] text-gray-400">or continue with</span>
                </div>
              </div>
              <button
                type="button"
                onClick={handleAppleSignIn}
                disabled={loading}
                aria-label="Sign in with Apple"
                className="w-full bg-white text-black font-semibold py-3 rounded-lg hover:bg-gray-100 transition-all flex items-center justify-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed min-h-11"
              >
                {/* Apple logo SVG */}
                <svg viewBox="0 0 814 1000" className="w-5 h-5 fill-black" xmlns="http://www.w3.org/2000/svg">
                  <path d="M788.1 340.9c-5.8 4.5-108.2 62.2-108.2 190.5 0 148.4 130.3 200.9 134.2 202.2-.6 3.2-20.7 71.9-68.7 141.9-42.8 61.6-87.5 123.1-155.5 123.1s-85.5-39.5-164-39.5c-76 0-103.7 40.8-165.9 40.8s-105-37.3-150.3-119.9C15.3 737.1 0 569.4 0 512.3c0-220.4 131.1-337.1 260.1-337.1 69.2 0 126.4 45.7 169.3 45.7 41.3 0 106.1-48.3 183.1-48.3 29.2 0 130.1 2.6 198.3 99.2zm-234-181.5c31.1-36.9 53.1-88.1 53.1-139.3 0-7.1-.6-14.3-1.9-20.1-50.6 1.9-110.8 33.7-147.1 75.8-28.5 32.4-55.1 83.6-55.1 135.5 0 7.8 1.3 15.6 1.9 18.1 3.2.6 8.4 1.3 13.6 1.3 45.4 0 102.5-30.4 135.5-71.3z"/>
                </svg>
                Sign in with Apple
              </button>
            </div>
          )}
        </div>

        {/* Bottom tagline */}
        <div className="mt-6 text-center">
          <p className="text-sm text-gray-400">
            Elite sports analytics powered by the BeatVegas Decision Engine
          </p>
        </div>
      </div>
    </div>
  );
}
