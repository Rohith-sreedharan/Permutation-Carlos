import React, { useState, useEffect } from 'react';
import { AlertCircle, Lock, Zap, TrendingUp, Users, Eye } from 'lucide-react';
import PageHeader from './PageHeader';
import LoadingSpinner from './LoadingSpinner';
import { swalSuccess, swalError } from '../utils/swal';
import { verifyToken } from '../services/api';

interface GameRoom {
  room_id: string;
  sport: string;
  home_team: string;
  away_team: string;
  commence_time: string;
  status: 'scheduled' | 'live' | 'completed' | 'archived';
}

interface MarketThread {
  thread_id: string;
  market_type: string;
  post_count: number;
  last_activity: string;
  is_locked: boolean;
}

interface Post {
  post_id: string;
  username: string;
  user_rank: string;
  post_type: string;
  created_at: string;
  views: number;
  replies: number;
  is_flagged?: boolean;
  market_type?: string;
  line?: string;
  confidence?: string;
  reason?: string;
  result?: string;
  screenshot_url?: string;
  model_context?: any;
  signal_id?: string;
}

const WarRoom: React.FC = () => {
  const [rooms, setRooms] = useState<GameRoom[]>([]);
  const [selectedRoom, setSelectedRoom] = useState<GameRoom | null>(null);
  const [selectedThread, setSelectedThread] = useState<MarketThread | null>(null);
  const [threads, setThreads] = useState<MarketThread[]>([]);
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [postingMode, setPostingMode] = useState<string | null>(null);
  const [userTier, setUserTier] = useState('free');

  useEffect(() => {
    loadRooms();
    loadUserTier();
  }, []);

  const loadUserTier = async () => {
    try {
      const user = await verifyToken();
      setUserTier(user?.tier || 'free');
    } catch (err) {
      console.error('Failed to load user tier:', err);
      setUserTier('free');
    }
  };

  useEffect(() => {
    if (selectedRoom) {
      loadThreads(selectedRoom.room_id);
    }
  }, [selectedRoom]);

  useEffect(() => {
    if (selectedThread) {
      loadPosts(selectedThread.thread_id);
    }
  }, [selectedThread]);

  const loadRooms = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/war-room/game-rooms?status=live');
      const data = await response.json();
      setRooms(data.rooms);
      if (data.rooms.length > 0) {
        setSelectedRoom(data.rooms[0]);
      }
      setLoading(false);
    } catch (err) {
      console.error('Failed to load rooms:', err);
      setLoading(false);
    }
  };

  const loadThreads = async (roomId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/war-room/game-rooms/${roomId}`);
      const data = await response.json();
      setThreads(data.threads);
      if (data.threads.length > 0) {
        setSelectedThread(data.threads[0]);
      }
    } catch (err) {
      console.error('Failed to load threads:', err);
    }
  };

  const loadPosts = async (threadId: string) => {
    try {
      const response = await fetch(`http://localhost:8000/api/war-room/threads/${threadId}/posts`);
      const data = await response.json();
      setPosts(data.posts);
    } catch (err) {
      console.error('Failed to load posts:', err);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <div className="space-y-6 flex flex-col bg-gradient-to-b from-charcoal to-midnight p-6 min-h-screen">
      <PageHeader title="War Room — Live Intelligence" />

      {/* Channel Banner */}
      <div className="bg-navy/50 border-l-4 border-electric-blue p-4 rounded-lg mb-4">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-bold text-electric-blue font-teko">
              {selectedThread?.market_type.toUpperCase()} THREAD
            </h3>
            <p className="text-sm text-light-gray mt-1">
              <strong>What belongs here:</strong> Market discussion tied to this specific game + line
            </p>
            <p className="text-sm text-light-gray">
              <strong>Required format:</strong> Game | Market | Line | Confidence | Reason (max 240 chars)
            </p>
            <p className="text-sm text-light-gray">
              <strong>No hype language:</strong> Auto-block of "lock", "guarantee", "free money"
            </p>
          </div>
          {selectedThread?.is_locked && (
            <div className="flex items-center space-x-2 bg-red-500/20 px-3 py-1 rounded-full">
              <Lock size={16} className="text-red-400" />
              <span className="text-xs font-bold text-red-400">LOCKED</span>
            </div>
          )}
        </div>
      </div>

      {/* Main Layout: Rooms | Threads | Posts */}
      <div className="grid grid-cols-12 gap-4 h-[calc(100vh-300px)] max-h-[800px]">
        {/* Rooms Sidebar */}
        <div className="col-span-3 bg-charcoal rounded-lg p-4 overflow-y-auto border border-navy flex flex-col h-full">
          <h3 className="font-bold text-white font-teko mb-4">LIVE GAMES</h3>
          <div className="space-y-2 flex-1">
            {rooms.length === 0 ? (
              <div className="text-center text-light-gray py-8 text-sm">
                No live games available.
              </div>
            ) : (
              rooms.map((room) => (
                <button
                  key={room.room_id}
                  onClick={() => setSelectedRoom(room)}
                  className={`w-full text-left p-3 rounded-lg transition ${
                    selectedRoom?.room_id === room.room_id
                      ? 'bg-electric-blue text-charcoal font-bold'
                      : 'bg-navy hover:bg-navy/70 text-white'
                  }`}
                >
                  <div className="text-sm font-bold">{room.home_team.substring(0, 3).toUpperCase()}</div>
                  <div className="text-xs text-light-gray">vs {room.away_team.substring(0, 3).toUpperCase()}</div>
                  <div className="text-xs mt-1 font-teko">
                    {room.status === 'live' && <span className="text-red-400">🔴 LIVE</span>}
                    {room.status === 'scheduled' && <span className="text-yellow-400">⏱ SCHEDULED</span>}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Market Threads */}
        <div className="col-span-3 bg-charcoal rounded-lg p-4 overflow-y-auto border border-navy flex flex-col h-full">
          <h3 className="font-bold text-white font-teko mb-4">MARKETS</h3>
          <div className="space-y-2 flex-1">
            {threads.length === 0 ? (
              <div className="text-center text-light-gray py-8 text-sm">
                {!selectedRoom ? 'Select a game to view markets' : 'No market threads available'}
              </div>
            ) : (
              threads.map((thread) => (
                <button
                  key={thread.thread_id}
                  onClick={() => setSelectedThread(thread)}
                  className={`w-full text-left p-3 rounded-lg transition ${
                    selectedThread?.thread_id === thread.thread_id
                      ? 'bg-electric-blue text-charcoal'
                      : 'bg-navy hover:bg-navy/70 text-white'
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="font-bold text-sm capitalize">{thread.market_type}</div>
                      <div className="text-xs text-light-gray">{thread.post_count} posts</div>
                    </div>
                    {thread.is_locked && <Lock size={14} className="text-red-400" />}
                  </div>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Posts Feed */}
        <div className="col-span-6 bg-charcoal rounded-lg p-4 overflow-y-auto border border-navy flex flex-col h-full">
          {postingMode ? (
            <PostTemplateContainer
              type={postingMode}
              threadId={selectedThread?.thread_id || ''}
              userTier={userTier}
              onClose={() => setPostingMode(null)}
              onSubmit={() => {
                setPostingMode(null);
                if (selectedThread) loadPosts(selectedThread.thread_id);
              }}
            />
          ) : (
            <>
              <div className="mb-4">
                {userTier === 'free' ? (
                  <div className="bg-yellow-500/10 border border-yellow-500/30 px-3 py-2 rounded-lg text-xs text-yellow-400">
                    <strong>Free Tier:</strong> Read-only access. Upgrade to post market callouts.
                  </div>
                ) : (
                  <div className="flex gap-2 flex-wrap">
                    <button
                      onClick={() => setPostingMode('market_callout')}
                      className="px-3 py-2 bg-electric-blue text-charcoal font-bold text-xs rounded-lg hover:bg-electric-blue/90 transition"
                    >
                      + Market Callout
                    </button>
                    <button
                      onClick={() => setPostingMode('receipt')}
                      className="px-3 py-2 bg-green-500/20 text-green-400 font-bold text-xs rounded-lg hover:bg-green-500/30 transition border border-green-500/30"
                    >
                      📸 Receipt
                    </button>
                    <button
                      onClick={() => setPostingMode('parlay_build')}
                      className="px-3 py-2 bg-purple-500/20 text-purple-400 font-bold text-xs rounded-lg hover:bg-purple-500/30 transition border border-purple-500/30"
                    >
                      🧩 Parlay
                    </button>
                  </div>
                )}
              </div>

              <div className="space-y-3 flex-1">
                {posts.length === 0 ? (
                  <div className="text-center text-light-gray py-8">
                    No posts yet. Start the discussion.
                  </div>
                ) : (
                  posts.map((post) => <PostCard key={post.post_id} post={post} />)
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// POST TEMPLATE CONTAINER
// ============================================================================

interface PostTemplateContainerProps {
  type: string;
  threadId: string;
  userTier: string;
  onClose: () => void;
  onSubmit: () => void;
}

const PostTemplateContainer: React.FC<PostTemplateContainerProps> = ({
  type,
  threadId,
  userTier,
  onClose,
  onSubmit,
}) => {
  const [formData, setFormData] = useState<any>({
    market_type: 'spread',
    confidence: 'med',
    line: '',
    reason: '',
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  const handleChange = (field: string, value: any) => {
    setFormData({ ...formData, [field]: value });
    // Clear error for this field
    if (errors[field]) {
      setErrors({ ...errors, [field]: '' });
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    // Validate
    const newErrors: Record<string, string> = {};

    if (!formData.market_type) newErrors.market_type = 'Required';
    if (!formData.line) newErrors.line = 'Required';
    if (formData.reason.length < 10) newErrors.reason = 'Min 10 characters';
    if (formData.reason.length > 240) newErrors.reason = 'Max 240 characters';

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    setSubmitting(true);

    try {
      const response = await fetch('http://localhost:8000/api/war-room/posts/market-callout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('authToken')}`,
        },
        body: JSON.stringify({
          thread_id: threadId,
          game_matchup: 'Auto', // In production, get from room
          market_type: formData.market_type,
          line: formData.line,
          confidence: formData.confidence,
          reason: formData.reason,
          played_this: formData.played_this || false,
        }),
      });

      if (response.ok) {
        await swalSuccess('Posted', 'Your market callout is live');
        onSubmit();
      } else {
        const data = await response.json();
        await swalError('Error', data.detail || 'Failed to post');
      }
    } catch (err) {
      await swalError('Error', 'Network error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4 bg-navy/30 p-4 rounded-lg border border-electric-blue/30">
      <div className="flex justify-between items-center mb-4">
        <h4 className="font-bold text-electric-blue">Market Callout Template</h4>
        <button
          type="button"
          onClick={onClose}
          className="text-light-gray hover:text-white text-sm"
        >
          ✕
        </button>
      </div>

      {/* Market Type */}
      <div>
        <label className="text-xs font-bold text-light-gray">Market Type</label>
        <select
          value={formData.market_type}
          onChange={(e) => handleChange('market_type', e.target.value)}
          className="w-full mt-1 bg-charcoal border border-navy rounded px-3 py-2 text-white text-sm"
        >
          <option value="spread">Spread</option>
          <option value="total">Total</option>
          <option value="moneyline">Moneyline</option>
          <option value="prop">Prop</option>
        </select>
      </div>

      {/* Line */}
      <div>
        <label className="text-xs font-bold text-light-gray">
          Line <span className="text-red-400">*</span>
        </label>
        <input
          type="text"
          placeholder="e.g., Lakers -5.5 or Over 218.5"
          value={formData.line}
          onChange={(e) => handleChange('line', e.target.value)}
          className="w-full mt-1 bg-charcoal border border-navy rounded px-3 py-2 text-white text-sm"
        />
        {errors.line && <p className="text-xs text-red-400 mt-1">{errors.line}</p>}
      </div>

      {/* Confidence */}
      <div>
        <label className="text-xs font-bold text-light-gray">Confidence</label>
        <div className="grid grid-cols-3 gap-2 mt-1">
          {['low', 'med', 'high'].map((level) => (
            <button
              key={level}
              type="button"
              onClick={() => handleChange('confidence', level)}
              className={`py-2 px-3 rounded text-xs font-bold transition ${
                formData.confidence === level
                  ? 'bg-electric-blue text-charcoal'
                  : 'bg-navy text-light-gray hover:bg-navy/70'
              }`}
            >
              {level.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Reason */}
      <div>
        <label className="text-xs font-bold text-light-gray">
          Reason ({formData.reason.length}/240)
        </label>
        <textarea
          placeholder="Why this play? Be specific about edge, not hype."
          value={formData.reason}
          onChange={(e) => handleChange('reason', e.target.value)}
          maxLength={240}
          className="w-full mt-1 bg-charcoal border border-navy rounded px-3 py-2 text-white text-sm"
          rows={3}
        />
        {errors.reason && <p className="text-xs text-red-400 mt-1">{errors.reason}</p>}
      </div>

      {/* Played This */}
      <label className="flex items-center space-x-2 cursor-pointer">
        <input
          type="checkbox"
          checked={formData.played_this}
          onChange={(e) => handleChange('played_this', e.target.checked)}
          className="w-4 h-4"
        />
        <span className="text-xs text-light-gray">I played this</span>
      </label>

      {/* Submit */}
      <button
        type="submit"
        disabled={submitting}
        className="w-full bg-electric-blue text-charcoal font-bold py-2 rounded-lg hover:bg-electric-blue/90 transition disabled:opacity-50"
      >
        {submitting ? 'Posting...' : 'Post Market Callout'}
      </button>
    </form>
  );
};

// ============================================================================
// POST CARD
// ============================================================================

interface PostCardProps {
  post: Post;
}

const PostCard: React.FC<PostCardProps> = ({ post }) => {
  const getRankColor = (rank: string) => {
    switch (rank) {
      case 'elite':
        return 'bg-yellow-500/20 text-yellow-400';
      case 'verified':
        return 'bg-green-500/20 text-green-400';
      case 'contributor':
        return 'bg-blue-500/20 text-blue-400';
      default:
        return 'bg-gray-500/20 text-gray-400';
    }
  };

  return (
    <div className="bg-navy/40 border border-navy rounded-lg p-3 hover:border-electric-blue/50 transition">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <span className="font-bold text-white text-sm">{post.username}</span>
          <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${getRankColor(post.user_rank)}`}>
            {post.user_rank.toUpperCase()}
          </span>
        </div>
        <span className="text-xs text-light-gray">{new Date(post.created_at).toLocaleTimeString()}</span>
      </div>

      {/* Content */}
      {post.post_type === 'market_callout' && (
        <div className="space-y-2 mb-2">
          <div className="grid grid-cols-2 gap-2 text-xs">
            <div>
              <p className="text-light-gray">Market</p>
              <p className="font-bold text-white capitalize">{post.market_type}</p>
            </div>
            <div>
              <p className="text-light-gray">Line</p>
              <p className="font-bold text-white">{post.line}</p>
            </div>
          </div>
          <div className="bg-charcoal/50 px-2 py-1 rounded text-xs text-light-gray border-l-2 border-electric-blue">
            {post.reason}
          </div>
          <div className="flex items-center justify-between">
            <div className={`text-xs font-bold px-2 py-1 rounded ${
              post.confidence === 'high' ? 'bg-green-500/20 text-green-400' :
              post.confidence === 'med' ? 'bg-yellow-500/20 text-yellow-400' :
              'bg-red-500/20 text-red-400'
            }`}>
              {post.confidence?.toUpperCase()} CONFIDENCE
            </div>
            {post.model_context && (
              <span className="text-xs text-electric-blue font-bold">📊 Model Context</span>
            )}
          </div>
        </div>
      )}

      {post.post_type === 'receipt' && (
        <div className="space-y-2 mb-2">
          <div className="flex items-center space-x-2">
            <img src={post.screenshot_url} alt="receipt" className="w-20 h-20 object-cover rounded" />
            <div className="text-xs space-y-1">
              <p><strong>Market:</strong> {post.market_type}</p>
              <p><strong>Line:</strong> {post.line}</p>
              <p className={`font-bold ${post.result === 'W' ? 'text-green-400' : post.result === 'L' ? 'text-red-400' : 'text-yellow-400'}`}>
                {post.result === 'W' ? '✓ WIN' : post.result === 'L' ? '✗ LOSS' : '~ PUSH'}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center justify-between pt-2 border-t border-navy/50 text-xs text-light-gray">
        <div className="flex items-center space-x-3">
          <span className="flex items-center space-x-1">
            <Eye size={12} />
            <span>{post.views}</span>
          </span>
          <span className="flex items-center space-x-1">
            <TrendingUp size={12} />
            <span>{post.replies}</span>
          </span>
        </div>
        {post.is_flagged && (
          <span className="text-red-400 font-bold flex items-center space-x-1">
            <AlertCircle size={12} />
            <span>Flagged</span>
          </span>
        )}
      </div>
    </div>
  );
};

export default WarRoom;
