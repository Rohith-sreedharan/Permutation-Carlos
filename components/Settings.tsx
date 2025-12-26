import React, { useState, useEffect } from 'react';
import { getUserSettings, updateUserSettings, changePassword, enable2FA, verify2FA, disable2FA, get2FAStatus, deleteAccount, beginPasskeyRegistration, completePasskeyRegistration, listPasskeys, deletePasskey } from '../services/api';
import { swalSuccess, swalError } from '../utils/swal';
import LoadingSpinner from './LoadingSpinner';
import Swal from 'sweetalert2';

const Settings: React.FC = () => {
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [twoFactorEnabled, setTwoFactorEnabled] = useState(false);
  const [passkeys, setPasskeys] = useState<any[]>([]);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        setLoading(true);
        const data = await getUserSettings();
        setSettings(data);
        
        // Load 2FA status
        const status = await get2FAStatus();
        setTwoFactorEnabled(status.enabled);
        
        // Load passkeys
        const passkeyData = await listPasskeys();
        setPasskeys(passkeyData.passkeys || []);
        
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to load settings');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadSettings();
  }, []);

  const handleToggle = async (key: string, value: boolean) => {
    const updatedSettings = { ...settings, [key]: value };
    setSettings(updatedSettings);
    
    try {
      setSaving(true);
      await updateUserSettings({ [key]: value });
      await swalSuccess('Settings Updated', 'Your preferences have been saved.');
    } catch (err: any) {
      setSettings(settings); // revert
      await swalError('Update Failed', err.message || 'Failed to update settings');
    } finally {
      setSaving(false);
    }
  };

  const handleThemeChange = async (theme: string) => {
    const updatedSettings = { ...settings, theme };
    setSettings(updatedSettings);
    
    try {
      setSaving(true);
      await updateUserSettings({ theme });
      await swalSuccess('Theme Updated', 'Refreshing page to apply theme...');
      // Reload page to apply theme
      setTimeout(() => window.location.reload(), 1000);
    } catch (err: any) {
      setSettings(settings); // revert
      await swalError('Update Failed', err.message || 'Failed to update theme');
    } finally {
      setSaving(false);
    }
  };

  const handleChangePassword = async () => {
    const result = await Swal.fire({
      title: 'Change Password',
      html: `
        <input type="password" id="current-password" class="swal2-input" placeholder="Current Password" style="background: #1a2332; color: white; border: 1px solid #334155;">
        <input type="password" id="new-password" class="swal2-input" placeholder="New Password" style="background: #1a2332; color: white; border: 1px solid #334155;">
        <input type="password" id="confirm-password" class="swal2-input" placeholder="Confirm New Password" style="background: #1a2332; color: white; border: 1px solid #334155;">
      `,
      showCancelButton: true,
      confirmButtonText: 'Change Password',
      confirmButtonColor: '#00ff88',
      cancelButtonColor: '#ff4444',
      background: '#0f1419',
      color: '#ffffff',
      preConfirm: () => {
        const current = (document.getElementById('current-password') as HTMLInputElement).value;
        const newPass = (document.getElementById('new-password') as HTMLInputElement).value;
        const confirm = (document.getElementById('confirm-password') as HTMLInputElement).value;
        
        if (!current || !newPass || !confirm) {
          Swal.showValidationMessage('All fields are required');
          return false;
        }
        
        if (newPass !== confirm) {
          Swal.showValidationMessage('New passwords do not match');
          return false;
        }
        
        if (newPass.length < 8) {
          Swal.showValidationMessage('Password must be at least 8 characters');
          return false;
        }
        
        return { current, newPass };
      }
    });
    
    if (result.isConfirmed && result.value) {
      try {
        await changePassword(result.value.current, result.value.newPass);
        await swalSuccess('Password Changed', 'Your password has been updated successfully.');
      } catch (err: any) {
        await swalError('Failed', err.message || 'Failed to change password');
      }
    }
  };

  const handleEnable2FA = async () => {
    try {
      const response = await enable2FA();
      
      // Show QR code
      const result = await Swal.fire({
        title: 'Enable Two-Factor Authentication',
        html: `
          <p style="margin-bottom: 1rem; color: #cbd5e1;">Scan this QR code with your authenticator app (Google Authenticator, Authy, etc.)</p>
          <img src="${response.qr_code_url}" style="max-width: 100%; margin-bottom: 1rem;" />
          <p style="font-size: 0.875rem; color: #94a3b8; margin-bottom: 1rem;">Or enter this code manually: <strong style="color: #00ff88;">${response.secret}</strong></p>
          <input type="text" id="verification-code" class="swal2-input" placeholder="Enter 6-digit code" maxlength="6" style="background: #1a2332; color: white; border: 1px solid #334155;">
        `,
        showCancelButton: true,
        confirmButtonText: 'Verify & Enable',
        confirmButtonColor: '#00ff88',
        cancelButtonColor: '#ff4444',
        background: '#0f1419',
        color: '#ffffff',
        preConfirm: () => {
          const code = (document.getElementById('verification-code') as HTMLInputElement).value;
          if (!code || code.length !== 6) {
            Swal.showValidationMessage('Please enter a 6-digit code');
            return false;
          }
          return code;
        }
      });
      
      if (result.isConfirmed && result.value) {
        await verify2FA(result.value);
        setTwoFactorEnabled(true);
        await swalSuccess('2FA Enabled', 'Two-factor authentication has been enabled successfully.');
      }
    } catch (err: any) {
      await swalError('Failed', err.message || 'Failed to enable 2FA');
    }
  };

  const handleDisable2FA = async () => {
    const result = await Swal.fire({
      title: 'Disable Two-Factor Authentication',
      html: '<input type="password" id="password" class="swal2-input" placeholder="Enter your password" style="background: #1a2332; color: white; border: 1px solid #334155;">',
      showCancelButton: true,
      confirmButtonText: 'Disable 2FA',
      confirmButtonColor: '#ff4444',
      cancelButtonColor: '#888',
      background: '#0f1419',
      color: '#ffffff',
      preConfirm: () => {
        const password = (document.getElementById('password') as HTMLInputElement).value;
        if (!password) {
          Swal.showValidationMessage('Password is required');
          return false;
        }
        return password;
      }
    });
    
    if (result.isConfirmed && result.value) {
      try {
        await disable2FA(result.value);
        setTwoFactorEnabled(false);
        await swalSuccess('2FA Disabled', 'Two-factor authentication has been disabled.');
      } catch (err: any) {
        await swalError('Failed', err.message || 'Failed to disable 2FA');
      }
    }
  };

  const handleDeleteAccount = async () => {
    const result = await Swal.fire({
      title: '⚠️ Delete Account',
      html: `
        <p style="color: #ff4444; font-weight: bold; margin-bottom: 1rem;">This action is PERMANENT and cannot be undone!</p>
        <p style="margin-bottom: 1rem; color: #cbd5e1;">All your data, bets, and settings will be deleted.</p>
        <input type="password" id="password" class="swal2-input" placeholder="Enter your password" style="background: #1a2332; color: white; border: 1px solid #334155;">
        <input type="text" id="confirmation" class="swal2-input" placeholder="Type DELETE to confirm" style="background: #1a2332; color: white; border: 1px solid #334155;">
      `,
      showCancelButton: true,
      confirmButtonText: 'Delete My Account',
      confirmButtonColor: '#ff4444',
      cancelButtonColor: '#888',
      background: '#0f1419',
      color: '#ffffff',
      preConfirm: () => {
        const password = (document.getElementById('password') as HTMLInputElement).value;
        const confirmation = (document.getElementById('confirmation') as HTMLInputElement).value;
        
        if (!password || !confirmation) {
          Swal.showValidationMessage('All fields are required');
          return false;
        }
        
        if (confirmation !== 'DELETE') {
          Swal.showValidationMessage('Please type DELETE to confirm');
          return false;
        }
        
        return { password, confirmation };
      }
    });
    
    if (result.isConfirmed && result.value) {
      try {
        await deleteAccount(result.value.password, result.value.confirmation);
        await swalSuccess('Account Deleted', 'Your account has been deleted. Redirecting...');
        // Clear token and redirect to login
        localStorage.removeItem('authToken');
        setTimeout(() => window.location.href = '/auth', 1500);
      } catch (err: any) {
        await swalError('Failed', err.message || 'Failed to delete account');
      }
    }
  };

  const handleRegisterPasskey = async () => {
    try {
      // Check if browser supports WebAuthn
      if (!window.PublicKeyCredential) {
        await swalError('Not Supported', 'Your browser does not support biometric authentication.');
        return;
      }
      
      // Start registration
      const options = await beginPasskeyRegistration();
      
      // Convert challenge and user ID from base64
      const challenge = Uint8Array.from(atob(options.challenge), c => c.charCodeAt(0));
      const userId = Uint8Array.from(atob(options.user.id), c => c.charCodeAt(0));
      
      // Create credential
      const credential = await navigator.credentials.create({
        publicKey: {
          challenge,
          rp: options.rp,
          user: {
            id: userId,
            name: options.user.name,
            displayName: options.user.displayName,
          },
          pubKeyCredParams: options.pubKeyCredParams,
          timeout: options.timeout,
          attestation: 'none',
          authenticatorSelection: options.authenticatorSelection,
        }
      }) as any;
      
      if (!credential) {
        throw new Error('Failed to create credential');
      }
      
      // Prepare credential for server
      const credentialData = {
        id: credential.id,
        rawId: btoa(String.fromCharCode(...new Uint8Array(credential.rawId))),
        response: {
          clientDataJSON: btoa(String.fromCharCode(...new Uint8Array(credential.response.clientDataJSON))),
          attestationObject: btoa(String.fromCharCode(...new Uint8Array(credential.response.attestationObject))),
          transports: credential.response.getTransports?.() || ['internal'],
        },
        type: credential.type,
      };
      
      // Complete registration
      await completePasskeyRegistration(credentialData);
      
      // Refresh passkey list
      const passkeyData = await listPasskeys();
      setPasskeys(passkeyData.passkeys || []);
      
      await swalSuccess('Passkey Registered', 'Biometric authentication has been enabled successfully!');
    } catch (err: any) {
      console.error('Passkey error:', err);
      await swalError('Failed', err.message || 'Failed to register passkey');
    }
  };

  const handleDeletePasskey = async (credentialId: string) => {
    const result = await Swal.fire({
      title: 'Delete Passkey?',
      text: 'This will remove this biometric authentication method.',
      showCancelButton: true,
      confirmButtonText: 'Delete',
      confirmButtonColor: '#ff4444',
      cancelButtonColor: '#888',
      background: '#0f1419',
      color: '#ffffff',
    });
    
    if (result.isConfirmed) {
      try {
        await deletePasskey(credentialId);
        const passkeyData = await listPasskeys();
        setPasskeys(passkeyData.passkeys || []);
        await swalSuccess('Deleted', 'Passkey has been removed.');
      } catch (err: any) {
        await swalError('Failed', err.message || 'Failed to delete passkey');
      }
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <div className="text-center text-bold-red p-8">{error}</div>;
  }

  if (!settings) {
    return <div className="text-center text-light-gray p-8">No settings available</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-4xl font-bold text-white font-teko mb-6">Settings</h1>
      
      {/* Notifications Section */}
      <div className="bg-charcoal rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-bold text-white mb-4">Notifications</h3>
        
        {/* Warning Banner */}
        <div className="bg-amber-500/10 border border-amber-500/50 rounded-lg p-4 mb-4">
          <p className="text-sm text-amber-400">
            ⚠️ <strong>Service Not Configured:</strong> Email and SMS notifications require backend integration (Twilio, SendGrid, or MSG91). 
            These settings are currently non-functional. Contact support for setup.
          </p>
        </div>

        <div className="space-y-4">
          <SettingToggle 
            label="Email Notifications"
            description="⚠️ Not configured - requires email service integration"
            checked={settings.email_notifications ?? true}
            onChange={(value) => handleToggle('email_notifications', value)}
            disabled={true}
          />
          <SettingToggle 
            label="SMS Notifications"
            description="⚠️ Not configured - requires SMS service integration (Twilio/MSG91)"
            checked={settings.sms_notifications ?? false}
            onChange={(value) => handleToggle('sms_notifications', value)}
            disabled={true}
          />
        </div>
      </div>

      {/* Appearance Section */}
      <div className="bg-charcoal rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-bold text-white mb-4">Appearance</h3>
        <div>
          <label className="block text-sm font-medium text-light-gray mb-2">Theme</label>
          <div className="flex space-x-3">
            <button
              onClick={() => handleThemeChange('dark')}
              disabled={saving}
              className={`flex-1 py-3 rounded-lg font-semibold transition-colors ${
                settings.theme === 'dark' 
                  ? 'bg-electric-blue text-white' 
                  : 'bg-navy text-light-gray hover:bg-navy/80'
              } disabled:opacity-50`}
            >
              🌙 Dark
            </button>
            <button
              onClick={() => handleThemeChange('light')}
              disabled={saving}
              className={`flex-1 py-3 rounded-lg font-semibold transition-colors ${
                settings.theme === 'light' 
                  ? 'bg-electric-blue text-white' 
                  : 'bg-navy text-light-gray hover:bg-navy/80'
              } disabled:opacity-50`}
            >
              ☀️ Light
            </button>
          </div>
        </div>
      </div>

      {/* Account Section */}
      <div className="bg-charcoal rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-bold text-white mb-4">Account</h3>
        <div className="space-y-3">
          <button 
            onClick={handleChangePassword}
            className="w-full text-left px-4 py-3 bg-navy rounded-lg text-white hover:bg-navy/80 transition-colors"
          >
            Change Password
          </button>
          
          {twoFactorEnabled ? (
            <button 
              onClick={handleDisable2FA}
              className="w-full text-left px-4 py-3 bg-navy rounded-lg text-white hover:bg-navy/80 transition-colors flex items-center justify-between"
            >
              <span>Two-Factor Authentication</span>
              <span className="text-neon-green text-sm">✓ Enabled</span>
            </button>
          ) : (
            <button 
              onClick={handleEnable2FA}
              className="w-full text-left px-4 py-3 bg-navy rounded-lg text-white hover:bg-navy/80 transition-colors flex items-center justify-between"
            >
              <span>Two-Factor Authentication</span>
              <span className="text-light-gray text-sm">Not enabled</span>
            </button>
          )}
          
          <button 
            onClick={handleDeleteAccount}
            className="w-full text-left px-4 py-3 bg-bold-red/20 rounded-lg text-bold-red hover:bg-bold-red/30 transition-colors"
          >
            Delete Account
          </button>
        </div>
      </div>

      {/* Biometric / Passkey Section */}
      <div className="bg-charcoal rounded-lg shadow-lg p-6">
        <h3 className="text-xl font-bold text-white mb-4">🔐 Biometric Authentication</h3>
        <p className="text-sm text-light-gray mb-2">
          Use Face ID, Touch ID, or Windows Hello for passwordless login
        </p>
        
        {/* Domain Warning */}
        {window.location.hostname === '127.0.0.1' && (
          <div className="bg-amber-500/10 border border-amber-500/50 rounded-lg p-3 mb-4">
            <p className="text-xs text-amber-400">
              ⚠️ <strong>Use localhost instead:</strong> Biometric authentication requires <code className="bg-black/30 px-1">localhost</code> in your browser URL. 
              Change <code className="bg-black/30 px-1">127.0.0.1:3000</code> to <code className="bg-black/30 px-1">localhost:3000</code>
            </p>
          </div>
        )}
        
        {passkeys.length > 0 ? (
          <div className="space-y-3">
            {passkeys.map((passkey, index) => (
              <div key={index} className="flex items-center justify-between p-4 bg-navy/50 rounded-lg">
                <div>
                  <p className="font-semibold text-white">
                    {passkey.transports.includes('usb') ? '🔑' : '📱'} Passkey {index + 1}
                  </p>
                  <p className="text-xs text-light-gray">
                    Added {new Date(passkey.created_at).toLocaleDateString()}
                  </p>
                </div>
                <button
                  onClick={() => handleDeletePasskey(passkey.id)}
                  className="px-3 py-1 bg-bold-red/20 text-bold-red rounded hover:bg-bold-red/30 transition-colors text-sm"
                >
                  Remove
                </button>
              </div>
            ))}
            <button
              onClick={handleRegisterPasskey}
              className="w-full px-4 py-3 bg-navy/50 rounded-lg text-neon-green hover:bg-navy/80 transition-colors border border-neon-green/30"
            >
              + Add Another Passkey
            </button>
          </div>
        ) : (
          <button
            onClick={handleRegisterPasskey}
            className="w-full px-4 py-3 bg-gradient-to-r from-neon-green/20 to-electric-blue/20 rounded-lg text-white hover:from-neon-green/30 hover:to-electric-blue/30 transition-colors border border-neon-green/30"
          >
            🚀 Enable Biometric Login (Face ID / Touch ID)
          </button>
        )}
      </div>
    </div>
  );
};

interface SettingToggleProps {
  label: string;
  description: string;
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}

const SettingToggle: React.FC<SettingToggleProps> = ({ label, description, checked, onChange, disabled }) => (
  <div className="flex items-center justify-between p-4 bg-navy/50 rounded-lg">
    <div>
      <p className="font-semibold text-white">{label}</p>
      <p className="text-sm text-light-gray">{description}</p>
    </div>
    <button
      onClick={() => onChange(!checked)}
      disabled={disabled}
      className={`relative w-14 h-8 rounded-full transition-colors duration-200 ${
        checked ? 'bg-neon-green' : 'bg-gray-600'
      } disabled:opacity-50`}
    >
      <span
        className={`absolute top-1 left-1 w-6 h-6 bg-white rounded-full transition-transform duration-200 ${
          checked ? 'transform translate-x-6' : ''
        }`}
      />
    </button>
  </div>
);

export default Settings;