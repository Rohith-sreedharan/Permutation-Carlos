import React, { useState, useEffect } from 'react';
import { loginUser, registerUser } from '../services/api';

interface AuthPageProps {
  onAuthSuccess: () => void;
}

const AuthPage: React.FC<AuthPageProps> = ({ onAuthSuccess }) => {
  const [mode, setMode] = useState<'signin' | 'signup'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if ((window as any).particlesJS) {
      (window as any).particlesJS('particles-js', {
        particles: {
          number: { value: 60, density: { enable: true, value_area: 800 } },
          color: { value: '#adb5bd' },
          shape: { type: 'circle' },
          opacity: { value: 0.3, random: true },
          size: { value: 3, random: true },
          line_linked: { enable: true, distance: 150, color: '#adb5bd', opacity: 0.2, width: 1 },
          move: { enable: true, speed: 1, direction: 'none', random: false, straight: false, out_mode: 'out', bounce: false },
        },
        interactivity: {
          detect_on: 'canvas',
          events: {
            onhover: { enable: true, mode: 'repulse' },
            onclick: { enable: true, mode: 'push' },
            resize: true,
          },
          modes: {
            repulse: { distance: 80, duration: 0.4 },
            push: { particles_nb: 4 },
          },
        },
        retina_detect: true,
      });
    }
  }, []);

  const handleModeChange = (newMode: 'signin' | 'signup') => {
    setMode(newMode);
    setError(null);
    setEmail('');
    setPassword('');
    setConfirmPassword('');
  };
  
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (mode === 'signup' && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      if (mode === 'signin') {
        await loginUser({ email, password });
        onAuthSuccess();
      } else {
        await registerUser({ email, username: email, password });
        handleModeChange('signin');
        alert('Registration successful! Please sign in.');
      }
    } catch (err: any) {
      setError(err.message || 'An unexpected error occurred.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-navy flex flex-col justify-center items-center p-4 relative overflow-hidden">
      <div id="particles-js" className="absolute top-0 left-0 w-full h-full z-0"></div>
      <div className="relative z-10 flex flex-col justify-center items-center w-full">
        <div className="text-center mb-8">
          <h1 className="text-6xl font-bold text-white font-teko tracking-wider">AIBETS</h1>
          <p className="text-light-gray">AI-Powered Sports Insights</p>
        </div>
        <div className="w-full max-w-md bg-charcoal rounded-lg shadow-lg p-8">
          <div className="flex mb-6 border-b border-navy/50">
            <button
              onClick={() => handleModeChange('signin')}
              className={`w-1/2 py-3 font-teko text-2xl tracking-wide transition-colors ${
                mode === 'signin' ? 'text-white border-b-2 border-electric-blue' : 'text-light-gray hover:text-white'
              }`}
            >
              SIGN IN
            </button>
            <button
              onClick={() => handleModeChange('signup')}
              className={`w-1/2 py-3 font-teko text-2xl tracking-wide transition-colors ${
                mode === 'signup' ? 'text-white border-b-2 border-electric-blue' : 'text-light-gray hover:text-white'
              }`}
            >
              SIGN UP
            </button>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-6">
            {error && <p className="text-bold-red text-sm text-center">{error}</p>}
            <InputField label="Email Address" id="email" type="email" value={email} onChange={e => setEmail(e.target.value)} />
            <InputField label="Password" id="password" type="password" value={password} onChange={e => setPassword(e.target.value)} />
            {mode === 'signup' && (
               <InputField label="Confirm Password" id="confirm-password" type="password" value={confirmPassword} onChange={e => setConfirmPassword(e.target.value)} />
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-electric-blue text-white font-bold py-3 rounded-lg hover:bg-opacity-80 transition-colors focus:outline-none focus:ring-2 focus:ring-electric-blue focus:ring-opacity-50 disabled:bg-gray-500 disabled:cursor-not-allowed"
            >
              {loading ? 'Processing...' : (mode === 'signin' ? 'Sign In' : 'Create Account')}
            </button>

            {mode === 'signin' && (
              <p className="text-center text-sm text-light-gray">
                Forgot your password?
              </p>
            )}
          </form>
        </div>
         <div className="text-center mt-8">
            <p className="text-xs text-light-gray">Powered by</p>
            <p className="text-sm font-bold text-white font-teko tracking-wider">OMNI AI</p>
        </div>
      </div>
    </div>
  );
};

interface InputFieldProps {
  label: string;
  id: string;
  type: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
}

const InputField: React.FC<InputFieldProps> = ({ label, id, type, value, onChange }) => (
    <div>
        <label htmlFor={id} className="block text-sm font-medium text-light-gray mb-2">{label}</label>
        <input
            id={id}
            name={id}
            type={type}
            required
            value={value}
            onChange={onChange}
            autoComplete={type === 'password' ? 'current-password' : 'email'}
            className="w-full bg-navy border border-navy/50 rounded-lg px-4 py-2.5 text-white placeholder-light-gray focus:ring-2 focus:ring-electric-blue focus:outline-none focus:border-electric-blue"
        />
    </div>
);

export default AuthPage;
