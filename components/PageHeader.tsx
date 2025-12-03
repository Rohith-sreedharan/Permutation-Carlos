import React, { useState, useEffect } from 'react';
import { getUserProfile } from '../services/api';

interface PageHeaderProps {
    title: string;
    children?: React.ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({ title, children }) => {
    const [user, setUser] = useState<any>(null);

    useEffect(() => {
        const loadUser = async () => {
            try {
                const profile = await getUserProfile();
                setUser(profile);
            } catch (err) {
                // Silently fail - profile is optional for now
                console.log('Profile not loaded (auth not implemented)');
            }
        };
        loadUser();
    }, []);

    // Format tier name for display
    const getTierDisplay = (tier: string) => {
        const tierMap: Record<string, string> = {
            'free': 'Free Tier',
            'starter': 'Starter',
            'core': 'Core',
            'pro': 'Pro',
            'elite': 'Elite 👑',
            'sharps_room': 'Sharps Room',
            'founder': 'Founder 👑'
        };
        return tierMap[tier?.toLowerCase()] || 'Starter';
    };

    return (
        <div className="flex flex-col sm:flex-row justify-between sm:items-center space-y-4 sm:space-y-0">
            <h1 className="text-4xl font-bold text-white font-teko">{title}</h1>
            <div className="flex items-center space-x-4">
                {children}
                {user && (
                    <div className="flex items-center space-x-3">
                        <img src={user.avatarUrl} alt="User Avatar" className="w-10 h-10 rounded-full" />
                        <div>
                            <p className="font-semibold text-white">{user.username}</p>
                            <p className="text-xs text-light-gray">{getTierDisplay(user.tier)}</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default PageHeader;