import React, { useState, useEffect } from 'react';
import { getUserProfile } from '../services/api';
import LoadingSpinner from './LoadingSpinner';

const Profile: React.FC = () => {
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadProfile = async () => {
      try {
        setLoading(true);
        const data = await getUserProfile();
        setProfile(data);
        setError(null);
      } catch (err: any) {
        setError(err.message || 'Failed to load profile');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    loadProfile();
  }, []);

  if (loading) {
    return <LoadingSpinner />;
  }

  if (error) {
    return <div className="text-center text-bold-red p-8">{error}</div>;
  }

  if (!profile) {
    return <div className="text-center text-light-gray p-8">No profile data available</div>;
  }

  return (
    <div>
      <h1 className="text-4xl font-bold text-white font-teko mb-6">My Profile</h1>
      <div className="bg-charcoal rounded-lg shadow-lg p-8 text-center">
        <img 
          src={profile.avatarUrl} 
          alt="User Avatar"
          className="w-24 h-24 rounded-full mx-auto mb-4 border-4 border-neon-green"
        />
        <h2 className="text-2xl font-semibold text-white">{profile.username}</h2>
        <p className="text-light-gray">{profile.email}</p>
        <div className="mt-6 border-t border-navy pt-6 grid grid-cols-2 gap-6">
          <div>
            <p className="text-sm text-light-gray">Total Score</p>
            <p className="text-2xl font-bold text-white">{profile.score?.toLocaleString() || 0}</p>
          </div>
          <div>
            <p className="text-sm text-light-gray">Win Streaks</p>
            <p className="text-2xl font-bold text-neon-green">🔥 {profile.streaks || 0}</p>
          </div>
        </div>
        <div className="mt-4 pt-4 border-t border-navy">
          <p className="text-xs text-light-gray">Member since</p>
          <p className="text-sm text-white">{profile.created_at ? new Date(profile.created_at).toLocaleDateString() : 'N/A'}</p>
        </div>
        
        {/* Referral CTA */}
        <div className="mt-6 pt-6 border-t border-navy">
          <div className="bg-linear-to-r from-neon-green/10 to-electric-blue/10 rounded-lg p-6 border border-neon-green/30">
            <h3 className="text-xl font-bold text-neon-green mb-2 font-teko">
              Beat Vegas Together
            </h3>
            <p className="text-sm text-light-gray mb-4">
              Share your edge. Invite friends and earn rewards when they join the winning side.
            </p>
            <button 
              className="bg-neon-green text-charcoal font-bold py-3 px-6 rounded-lg hover:bg-electric-blue hover:text-white transition-all duration-300 transform hover:scale-105 shadow-lg"
              onClick={() => {
                // TODO: Implement referral logic
                alert('Referral feature coming soon!');
              }}
            >
              Refer a Friend
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Profile;