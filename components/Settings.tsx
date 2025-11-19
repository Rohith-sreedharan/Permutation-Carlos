import React, { useState, useEffect } from 'react';
import { getUserSettings, updateUserSettings } from '../services/api';
import { swalSuccess, swalError } from '../utils/swal';
import LoadingSpinner from './LoadingSpinner';

const Settings: React.FC = () => {
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        setLoading(true);
        const data = await getUserSettings();
        setSettings(data);
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
      await swalSuccess('Theme Updated', `Switched to ${theme} theme.`);
    } catch (err: any) {
      setSettings(settings); // revert
      await swalError('Update Failed', err.message || 'Failed to update theme');
    } finally {
      setSaving(false);
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
        <div className="space-y-4">
          <SettingToggle 
            label="Email Notifications"
            description="Receive updates and alerts via email"
            checked={settings.email_notifications ?? true}
            onChange={(value) => handleToggle('email_notifications', value)}
            disabled={saving}
          />
          <SettingToggle 
            label="SMS Notifications"
            description="Receive important alerts via SMS"
            checked={settings.sms_notifications ?? false}
            onChange={(value) => handleToggle('sms_notifications', value)}
            disabled={saving}
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
          <button className="w-full text-left px-4 py-3 bg-navy rounded-lg text-white hover:bg-navy/80 transition-colors">
            Change Password
          </button>
          <button className="w-full text-left px-4 py-3 bg-navy rounded-lg text-white hover:bg-navy/80 transition-colors">
            Two-Factor Authentication
          </button>
          <button className="w-full text-left px-4 py-3 bg-bold-red/20 rounded-lg text-bold-red hover:bg-bold-red/30 transition-colors">
            Delete Account
          </button>
        </div>
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