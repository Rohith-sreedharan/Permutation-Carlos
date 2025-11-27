import React, { useState, useEffect } from 'react';
import { getChatMessages, getTopAnalysts, sendChatMessage } from '../services/api';
import type { ChatMessage, TopAnalyst } from '../types';
import LoadingSpinner from './LoadingSpinner';
import PageHeader from './PageHeader';
import { swalSuccess, swalError } from '../utils/swal';

const Community: React.FC = () => {
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [analysts, setAnalysts] = useState<TopAnalyst[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);
    const [newMessage, setNewMessage] = useState<string>('');
    const [sending, setSending] = useState<boolean>(false);

    useEffect(() => {
        loadData();
        // Poll for new messages every 10 seconds
        const interval = setInterval(loadData, 10000);
        return () => clearInterval(interval);
    }, []);

    const loadData = async () => {
        try {
            setLoading(true);
            const [chatData, analystData] = await Promise.all([getChatMessages(), getTopAnalysts()]);
            setMessages(chatData);
            setAnalysts(analystData);
            setError(null);
        } catch (err) {
            setError('Failed to fetch community data.');
            console.error(err);
        } finally {
            setLoading(false);
        }
    };

    const handleSendMessage = async () => {
        if (!newMessage.trim() || sending) return;

        try {
            setSending(true);
            await sendChatMessage(newMessage, 'nba_general');
            setNewMessage('');
            await loadData(); // Refresh messages
            await swalSuccess('Message Sent', 'Your message has been posted to the community.');
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

    if (error) {
        return <div className="text-center text-bold-red">{error}</div>;
    }

    return (
        <div className="space-y-6 h-full flex flex-col">
            <PageHeader title="Community Hub" />
            {loading ? <LoadingSpinner /> : (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1">
                    {/* Chat Section */}
                    <div className="lg:col-span-2 bg-charcoal rounded-lg p-6 flex flex-col h-[75vh]">
                       <h3 className="text-xl font-bold text-white font-teko mb-4">#NBA General Chat</h3>
                       <div className="flex-1 space-y-4 overflow-y-auto pr-2">
                            {messages.map(msg => (
                                <div key={msg.id} className={`flex items-start space-x-3 ${msg.announcement ? 'bg-navy/50 p-3 rounded-lg' : ''}`}>
                                    <img src={msg.user.avatarUrl} alt={msg.user.username} className="w-10 h-10 rounded-full" />
                                    <div className="flex-1">
                                        <div className="flex items-baseline space-x-2">
                                            <p className="font-bold text-white">{msg.user.username}</p>
                                            <p className="text-xs text-light-gray">{msg.timestamp}</p>
                                            {msg.user.is_admin && <span className="text-xs font-bold text-electric-blue bg-electric-blue/20 px-2 py-0.5 rounded-full">Admin</span>}
                                        </div>
                                        <p className="text-white">{msg.message}</p>
                                    </div>
                                </div>
                            ))}
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
                    {/* Top Analysts Section */}
                    <div className="lg:col-span-1 bg-charcoal rounded-lg p-6">
                        <h3 className="text-xl font-bold text-white font-teko mb-4">Top Analysts</h3>
                        <div className="space-y-4">
                            {analysts.map(analyst => (
                                <div key={analyst.id} className="flex items-center justify-between">
                                    <div className="flex items-center space-x-3">
                                        <span className="font-bold text-light-gray w-4">{analyst.rank}.</span>
                                        <img src={analyst.avatarUrl} alt={analyst.username} className="w-10 h-10 rounded-full" />
                                        <p className="font-semibold text-white">{analyst.username}</p>
                                    </div>
                                    <span className="font-bold text-neon-green">+{analyst.units.toFixed(1)} Units</span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

export default Community;