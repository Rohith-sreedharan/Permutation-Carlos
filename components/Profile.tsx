
import React from 'react';

const Profile: React.FC = () => {
  return (
    <div>
      <h1 className="text-4xl font-bold text-white font-teko mb-6">My Profile</h1>
      <div className="bg-charcoal rounded-lg shadow-lg p-8 text-center">
        <img 
          src="https://i.pravatar.cc/150?u=a042581f4e29026704d" 
          alt="User Avatar"
          className="w-24 h-24 rounded-full mx-auto mb-4 border-4 border-neon-green"
        />
        <h2 className="text-2xl font-semibold text-white">User123</h2>
        <p className="text-light-gray">user123@email.com</p>
        <div className="mt-6 border-t border-navy pt-6">
          <p className="text-white">User stats and streaks will be displayed here.</p>
          <p className="text-light-gray mt-2">This page is currently under construction.</p>
        </div>
      </div>
    </div>
  );
};

export default Profile;