import React, { useState, useEffect } from 'react';
import { getTopAnalysts } from '../services/api';
import type { TopAnalyst } from '../types';
import LoadingSpinner from './LoadingSpinner';
import PageHeader from './PageHeader';
import { swalSuccess, swalError } from '../utils/swal';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

interface Channel {
    id: string;
    name: string;
    emoji: string;
    description: string;
}

interface CommunityMessage {
    message_id: string;
    channel_id: string;
    user_id: string;
    username: string;
    content: string;
    ts: string;
    message_type: string;
    is_bot: boolean;
    user_rank?: string;
    user_badges?: string[];
}

const CommunityEnhanced: React.FC = () => {
    const [messages, setMessages] = useState<CommunityMessage[]>([]);
    const [analysts, setAnalysts] = useState<TopAnalyst[]>([]);
    const [channels, setChannels] = useState<Channel[]>([]);
    const [selectedChannel, setSelectedChannel] = useState<string>('general');
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [newMessage, setNewMessage] = useState<string>('');
    const [sending, setSending] = useState<boolean>(false);

    useEffect(() => {
        loadChannels();
        loadData();
        // Poll for new messages every 5 seconds for real-time feel
        const interval = setInterval(loadData, 5000);
        return () => clearInterval(interval);
    }, [selectedChannel]);

    const loadChannels = async () => {
        try {
            const response = await fetch(`${API_BASE_URL}/api/community/channels`);
            const data = await response.json();
            setChannels(data.channels);
        } catch (err) {
            console.error('Failed to load channels:', err);
        }
    };

    const loadData = async () => {
        try {
            const [messagesResponse, analystData] = await Promise.all([
                fetch(`${API_BASE_URL}/api/community/messages?channel=${selectedChannel}&limit=50`),
                getTopAnalysts().catch(() => [])
            ]);
            
            if (messagesResponse.ok) {
                const data = await messagesResponse.json();
                setMessages(data.messages || []);
            }
            
            setAnalysts(analystData);
            setError(null);
        } catch (err) {
            console.error('Failed to fetch community data:', err);
        } finally {
            setLoading(false);
        }
    };

    const handleSendMessage = async () => {
        if (!newMessage.trim() || sending) return;

        try {
            setSending(true);
            const token = localStorage.getItem('authToken');
            const response = await fetch(`${API_BASE_URL}/api/community/messages`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    channel: selectedChannel,
                    content: newMessage
                })
            });

            if (response.ok) {
                setNewMessage('');
                await loadData(); // Refresh messages
                await swalSuccess('Message Sent', 'Your message has been posted!');
            } else {
                throw new Error('Failed to send message');
            }
        } catch (err: any) {
            await swalError('Send Failed', err.message || 'Failed to send message');
            console.error(err);
        } finally {
            setSending(false);
        }
    };

    const handleKeyPress = (e: React.KeyboardEvent) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    };

    const getRankColor = (rank?: string) => {
        switch (rank?.toLowerCase()) {
            case 'legend': return 'text-purple-400';
            case 'diamond': return 'text-cyan-400';
            case 'platinum': return 'text-gray-300';
            case 'gold': return 'text-yellow-400';
            case 'silver': return 'text-gray-400';
            default: return 'text-amber-600';
        }
    };

    const getRankBadge = (rank?: string) => {
        if (!rank) return null;
        return (
            <span className={`text-xs font-bold ${getRankColor(rank)} uppercase`}>
                {rank}
            </span>
        );
    };

    const formatTimestamp = (ts: string) => {
        if (!ts) return 'recently';
        const date = new Date(ts);
        if (isNaN(date.getTime())) return 'recently'; // Fix Invalid Date
        const now = new Date();
        const diff = now.getTime() - date.getTime();
        const minutes = Math.floor(diff / 60000);
        
        if (minutes < 1) return 'just now';
        if (minutes < 60) return `${minutes}m ago`;
        const hours = Math.floor(minutes / 60);
        if (hours < 24) return `${hours}h ago`;
        return date.toLocaleDateString();
    };

    const renderMessage = (msg: CommunityMessage) => {
        const isBot = msg.is_bot;
        const isMonteCarlo = msg.message_type === 'monte_carlo_alert';
        const isAlert = ['injury_alert', 'line_movement', 'volatility_alert'].includes(msg.message_type);
        
        // Tier ring colors based on user rank
        const getTierRing = (rank?: string) => {
            if (!rank) return 'ring-2 ring-gray-500';
            switch (rank.toLowerCase()) {
                case 'legend': return 'ring-2 ring-gold shadow-lg shadow-gold/50';
                case 'diamond': return 'ring-2 ring-purple-400 shadow-lg shadow-purple-400/50';
                case 'platinum': return 'ring-2 ring-electric-blue shadow-lg shadow-electric-blue/50';
                case 'gold': return 'ring-2 ring-gold';
                case 'silver': return 'ring-2 ring-gray-300';
                default: return 'ring-2 ring-gray-600';
            }
        };
        
        return (
            <div 
                key={msg.message_id} 
                className={`p-4 rounded-lg ${
                    isMonteCarlo ? 'bg-electric-blue/10 border border-electric-blue/30' :
                    isAlert ? 'bg-bold-red/10 border border-bold-red/30' :
                    isBot ? 'bg-navy/50' :
                    'hover:bg-navy/30'
                } transition-colors`}
            >
                <div className="flex items-start space-x-3">
                    {isBot ? (
                        <div className="w-10 h-10 rounded-full bg-electric-blue flex items-center justify-center text-white text-xl">
                            🎯
                        </div>
                    ) : (
                        <div className={`w-10 h-10 rounded-full bg-navy flex items-center justify-center text-white font-bold ${getTierRing(msg.user_rank)}`}>
                            {msg.username ? msg.username.charAt(0).toUpperCase() : '?'}
                        </div>
                    )}
                    <div className="flex-1">
                        <div className="flex items-baseline space-x-2 mb-1">
                            <p className={`font-bold ${isBot ? 'text-electric-blue' : 'text-white'}`}>
                                {msg.username}
                            </p>
                            {msg.user_rank && getRankBadge(msg.user_rank)}
                            {msg.user_badges && msg.user_badges.length > 0 && (
                                <div className="flex space-x-1">
                                    {msg.user_badges.slice(0, 3).map(badge => (
                                        <span key={badge} className="text-xs" title={badge}>
                                            {badge === 'verified_capper' ? '✅' :
                                             badge === 'streak_master' ? '🔥' :
                                             badge === 'sharp_bettor' ? '💎' :
                                             badge === 'parlay_king' ? '👑' : '🏅'}
                                        </span>
                                    ))}
                                </div>
                            )}
                            <p className="text-xs text-light-gray">{formatTimestamp(msg.ts)}</p>
                        </div>
                        <div className="text-white whitespace-pre-wrap">{msg.content}</div>
                    </div>
                </div>
            </div>
        );
    };

    if (error) {
        return <div className="text-center text-bold-red">{error}</div>;
    }

    return (
        <div className="space-y-6 h-full flex flex-col">
            <PageHeader title="🔥 Community War Room" />
            {loading && messages.length === 0 ? <LoadingSpinner /> : (
                <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 flex-1">
                    {/* Channels Sidebar */}
                    <div className="lg:col-span-1 bg-charcoal rounded-lg p-4 h-[75vh] overflow-y-auto">
                        <h3 className="text-lg font-bold text-white font-teko mb-3">CHANNELS</h3>
                        <div className="space-y-1">
                            {channels.map(channel => (
                                <button
                                    key={channel.id}
                                    onClick={() => setSelectedChannel(channel.id)}
                                    title={channel.description}
                                    className={`w-full text-left px-3 py-2 rounded-lg transition-colors group relative ${
                                        selectedChannel === channel.id
                                            ? 'bg-electric-blue text-white'
                                            : 'text-light-gray hover:bg-navy/50 hover:text-white'
                                    }`}
                                >
                                    <div className="flex items-center">
                                        <span className="text-lg mr-2">{channel.emoji}</span>
                                        <span className="font-medium text-sm">{channel.name}</span>
                                    </div>
                                    {/* Tooltip on hover */}
                                    <div className="absolute left-full ml-2 top-0 w-48 bg-navy/95 border border-gold/30 rounded-lg p-2 text-xs text-light-gray opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-50 shadow-xl">
                                        {channel.description}
                                    </div>
                                </button>
                            ))}
                        </div>
                    </div>

                    {/* Chat Section */}
                    <div className="lg:col-span-2 bg-charcoal rounded-lg p-6 flex flex-col h-[75vh]">
                       <div className="flex items-center justify-between mb-4 pb-3 border-b border-navy/50">
                           <div>
                               <h3 className="text-xl font-bold text-white font-teko leading-none">
                                   {channels.find(c => c.id === selectedChannel)?.emoji || '💬'} 
                                   {' '}{channels.find(c => c.id === selectedChannel)?.name || 'General'}
                               </h3>
                               <p className="text-xs text-light-gray/70 mt-1">
                                   {channels.find(c => c.id === selectedChannel)?.description || ''}
                               </p>
                           </div>
                           <div className="flex items-center space-x-2 bg-neon-green/10 px-3 py-1 rounded-full">
                               <div className="w-2 h-2 bg-neon-green rounded-full animate-pulse shadow-lg shadow-neon-green/50"></div>
                               <span className="text-xs font-bold text-neon-green">LIVE</span>
                           </div>
                       </div>
                       
                       <div className="flex-1 space-y-3 overflow-y-auto pr-2">
                            {messages.length === 0 ? (
                                <div className="text-center text-light-gray py-12 bg-navy/20 rounded-lg border border-gold/10">
                                    <p className="text-5xl mb-4">💬</p>
                                    <p className="text-white font-bold text-lg mb-2">Channel Ready</p>
                                    <p className="text-sm text-light-gray/80 max-w-sm mx-auto">
                                        {selectedChannel === 'general' ? 'Start the conversation — share your picks, insights, or questions.' :
                                         selectedChannel.includes('nba') ? 'NBA game threads and sim alerts will appear here as games approach.' :
                                         selectedChannel.includes('nfl') ? 'NFL analysis and line movement updates post here automatically.' :
                                         selectedChannel === 'props' ? 'Player prop mispricings unlock 24-48 hours before games.' :
                                         selectedChannel === 'parlay' ? 'Build multi-leg parlays with AI-optimized edges.' :
                                         selectedChannel === 'winning-tickets' ? 'Winning bet celebrations appear here automatically.' :
                                         'Be the first to post in this channel!'}
                                    </p>
                                </div>
                            ) : (
                                messages.map(renderMessage)
                            )}
                       </div>
                       
                       <div className="mt-4 flex items-center space-x-2 border-t border-navy/50 pt-4">
                            <input 
                                type="text" 
                                placeholder="Type your message..." 
                                value={newMessage}
                                onChange={(e) => setNewMessage(e.target.value)}
                                onKeyPress={handleKeyPress}
                                disabled={sending}
                                className="flex-1 bg-navy border-none rounded-lg px-4 py-2 text-white placeholder-light-gray focus:ring-2 focus:ring-electric-blue disabled:opacity-50" 
                            />
                            <button 
                                onClick={handleSendMessage}
                                disabled={!newMessage.trim() || sending}
                                className="bg-electric-blue text-white font-semibold px-6 py-2 rounded-lg hover:bg-opacity-80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {sending ? '...' : 'Send'}
                            </button>
                       </div>
                    </div>

                    {/* Leaderboard Section */}
                    <div className="lg:col-span-1 bg-charcoal rounded-lg p-6 h-[75vh] overflow-y-auto">
                        <h3 className="text-xl font-bold text-white font-teko mb-4">🏆 LEADERBOARD</h3>
                        <div className="space-y-3">
                            {analysts.length > 0 ? analysts.map(analyst => (
                                <div key={analyst.id} className="flex items-center justify-between p-2 rounded-lg hover:bg-navy/50 transition-colors">
                                    <div className="flex items-center space-x-3">
                                        <span className="font-bold text-electric-blue w-6">{analyst.rank}.</span>
                                        <div>
                                            <p className="font-semibold text-white">{analyst.username}</p>
                                            <p className="text-xs text-light-gray">
                                                {analyst.units > 0 ? `+${analyst.units.toFixed(1)}` : analyst.units.toFixed(1)} units
                                            </p>
                                        </div>
                                    </div>
                                    <span className={`font-bold ${analyst.units > 0 ? 'text-neon-green' : 'text-bold-red'}`}>
                                        {analyst.units > 0 ? '📈' : '📉'}
                                    </span>
                                </div>
                            )) : (
                                <p className="text-light-gray text-sm text-center py-4">
                                    No leaderboard data yet
                                </p>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default CommunityEnhanced;
