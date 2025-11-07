import React from 'react';

interface PageHeaderProps {
    title: string;
    children?: React.ReactNode;
}

const PageHeader: React.FC<PageHeaderProps> = ({ title, children }) => {
    return (
        <div className="flex flex-col sm:flex-row justify-between sm:items-center space-y-4 sm:space-y-0">
            <h1 className="text-4xl font-bold text-white font-teko">{title}</h1>
            <div className="flex items-center space-x-4">
                {children}
                <div className="flex items-center space-x-3">
                    <img src="https://i.pravatar.cc/150?u=AlexRyder" alt="User Avatar" className="w-10 h-10 rounded-full" />
                    <div>
                        <p className="font-semibold text-white">Alex Ryder</p>
                        <p className="text-xs text-light-gray">Pro Subscriber</p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default PageHeader;