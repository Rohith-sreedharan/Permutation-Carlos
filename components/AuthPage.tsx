import React, { useState } from 'react';
import { loginUser, registerUser, verify2FALogin, beginPasskeyLogin, completePasskeyLogin } from '../services/api';
import Swal from 'sweetalert2';

interface AuthPageProps {
  onAuthSuccess: () => void;
}

export default function AuthPage({ onAuthSuccess }: AuthPageProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

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
        localStorage.setItem('token', response.access_token);
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
                localStorage.setItem('token', verifyResponse.access_token);
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
          localStorage.setItem('token', response.access_token);
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
          localStorage.setItem('token', response.access_token);
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
      <div className="absolute inset-0 bg-gradient-to-br from-[#1a1f35] via-[#0a0f1e] to-black opacity-90" />
      
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
        {/* AIBETS logo */}
        <div className="text-center mb-8">
          <h1 className="text-6xl font-black mb-2 bg-gradient-to-r from-gold via-yellow-300 to-gold bg-clip-text text-transparent animate-pulse">
            AIBETS
          </h1>
          <p className="text-sm text-gray-400 tracking-wider uppercase">
            Powered by OMNI AI
          </p>
        </div>

        {/* Card */}
        <div className="bg-gradient-to-b from-navy/80 to-[#0a0f1e]/80 backdrop-blur-xl rounded-2xl shadow-2xl border border-gold/20 p-8">
          {/* Tab selector */}
          <div className="flex mb-8 bg-black/30 rounded-lg p-1">
            <button
              onClick={() => setIsLogin(true)}
              className={`flex-1 py-3 rounded-lg font-semibold transition-all ${
                isLogin
                  ? 'bg-gradient-to-r from-gold to-yellow-500 text-black'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              Sign In
            </button>
            <button
              onClick={() => setIsLogin(false)}
              className={`flex-1 py-3 rounded-lg font-semibold transition-all ${
                !isLogin
                  ? 'bg-gradient-to-r from-gold to-yellow-500 text-black'
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
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-3 bg-black/30 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:border-gold focus:ring-2 focus:ring-gold/20 transition-all"
                placeholder="••••••••"
              />
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
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  className="w-full px-4 py-3 bg-black/30 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:border-gold focus:ring-2 focus:ring-gold/20 transition-all"
                  placeholder="••••••••"
                />
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
              className="w-full bg-gradient-to-r from-gold via-yellow-400 to-gold text-black font-bold py-4 rounded-lg hover:shadow-2xl hover:shadow-gold/50 transition-all transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed"
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
                  className="w-full bg-gradient-to-r from-blue-600 to-blue-500 text-white font-semibold py-4 rounded-lg hover:shadow-xl hover:shadow-blue-500/30 transition-all transform hover:scale-[1.02] disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
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
        </div>

        {/* Bottom tagline */}
        <div className="mt-6 text-center">
          <p className="text-sm text-gray-400">
            Elite sports analytics powered by Monte Carlo simulations
          </p>
        </div>
      </div>
    </div>
  );
}
