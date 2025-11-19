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
                console.error('Failed to load user profile:', err);
            }
        };
        loadUser();
    }, []);

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
                            <p className="text-xs text-light-gray">Pro Subscriber</p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default PageHeader;