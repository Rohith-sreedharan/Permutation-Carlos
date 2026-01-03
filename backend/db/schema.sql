-- BeatVegas/SimSports Database Schema
-- Comprehensive schema covering B2C → B2B transition

-- =============================================================================
-- USERS & AUTHENTICATION
-- =============================================================================

CREATE TABLE users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    
    -- Profile
    display_name VARCHAR(100),
    avatar_url TEXT,
    bio TEXT,
    
    -- Subscription tier (B2C)
    subscription_tier VARCHAR(50) DEFAULT 'FREE',  -- FREE, STARTER, PRO, ELITE
    subscription_price DECIMAL(10, 2),  -- $29.99, $49.99, $89.99
    subscription_started_at TIMESTAMP,
    subscription_expires_at TIMESTAMP,
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    
    -- Sharp Pass verification ($999/mo)
    sharp_pass_status VARCHAR(50) DEFAULT 'NOT_APPLIED',  -- NOT_APPLIED, PENDING, APPROVED, REJECTED
    sharp_pass_score DECIMAL(5, 2),  -- CLV edge percentage
    sharp_pass_bet_count INT DEFAULT 0,
    sharp_pass_applied_at TIMESTAMP,
    sharp_pass_approved_at TIMESTAMP,
    
    -- Wire Pro access (community)
    wire_pro_access BOOLEAN DEFAULT FALSE,
    wire_pro_granted_at TIMESTAMP,
    
    -- SimSports B2B (institutional)
    simsports_access BOOLEAN DEFAULT FALSE,
    simsports_tier VARCHAR(50),  -- STARTER, PROFESSIONAL, INSTITUTIONAL
    simsports_api_key VARCHAR(255),
    simsports_monthly_fee DECIMAL(10, 2),  -- $5k-$50k/mo
    
    -- Preferences
    timezone VARCHAR(50) DEFAULT 'America/New_York',
    notifications_enabled BOOLEAN DEFAULT TRUE,
    telegram_user_id VARCHAR(100),
    telegram_connected_at TIMESTAMP,
    
    -- Tracking
    onboarding_completed BOOLEAN DEFAULT FALSE,
    referral_code VARCHAR(50) UNIQUE,
    referred_by UUID REFERENCES users(user_id)
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_subscription_tier ON users(subscription_tier);
CREATE INDEX idx_users_sharp_pass_status ON users(sharp_pass_status);
CREATE INDEX idx_users_stripe_customer ON users(stripe_customer_id);


-- =============================================================================
-- GAMES & SIMULATIONS
-- =============================================================================

CREATE TABLE games (
    game_id VARCHAR(100) PRIMARY KEY,
    sport VARCHAR(50) NOT NULL,  -- MLB, NFL, NBA, NCAAB, NCAAF, NHL
    league VARCHAR(50),
    
    -- Teams
    team_a VARCHAR(100) NOT NULL,
    team_b VARCHAR(100) NOT NULL,
    home_team VARCHAR(100),
    away_team VARCHAR(100),
    
    -- Timing
    scheduled_time TIMESTAMP NOT NULL,
    actual_start_time TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Final result
    final_score_team_a INT,
    final_score_team_b INT,
    game_status VARCHAR(50) DEFAULT 'SCHEDULED',  -- SCHEDULED, IN_PROGRESS, FINAL, CANCELLED
    
    -- Metadata
    venue VARCHAR(255),
    weather_conditions TEXT,
    pitcher_home VARCHAR(100),  -- MLB
    pitcher_away VARCHAR(100),  -- MLB
    qb_home VARCHAR(100),  -- NFL/NCAAF
    qb_away VARCHAR(100),  -- NFL/NCAAF
    goalie_home VARCHAR(100),  -- NHL
    goalie_away VARCHAR(100),  -- NHL
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_games_sport ON games(sport);
CREATE INDEX idx_games_scheduled_time ON games(scheduled_time);
CREATE INDEX idx_games_status ON games(game_status);


CREATE TABLE simulations (
    sim_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id VARCHAR(100) NOT NULL REFERENCES games(game_id),
    sim_run_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Simulation metadata
    wave VARCHAR(50) NOT NULL,  -- WAVE_1_DISCOVERY, WAVE_2_VALIDATION, WAVE_3_PUBLISH
    num_simulations INT NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    sport VARCHAR(50) NOT NULL,
    
    -- Timing
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    execution_duration_ms INT,
    
    -- Results
    edge_state VARCHAR(50),  -- EDGE, LEAN, NO_PLAY
    raw_edge DECIMAL(5, 2),
    compressed_edge DECIMAL(5, 2),
    compression_factor DECIMAL(3, 2),
    
    -- Volatility & Distribution
    volatility VARCHAR(50),  -- LOW, MEDIUM, HIGH, EXTREME
    distribution_flag VARCHAR(50),  -- STABLE, UNSTABLE, UNSTABLE_EXTREME
    convergence_rate DECIMAL(5, 4),
    
    -- Sharp side selection
    sharp_side VARCHAR(100),
    favored_team VARCHAR(100),
    points_side VARCHAR(50),  -- FAVORITE, UNDERDOG, N/A
    volatility_penalty DECIMAL(5, 2),
    
    -- Market type
    market_type VARCHAR(50),  -- SPREAD, TOTAL, MONEYLINE, PUCKLINE
    
    -- Full result data (JSON)
    result_data JSONB,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_simulations_game_id ON simulations(game_id);
CREATE INDEX idx_simulations_wave ON simulations(wave);
CREATE INDEX idx_simulations_edge_state ON simulations(edge_state);
CREATE INDEX idx_simulations_executed_at ON simulations(executed_at);


CREATE TABLE market_snapshots (
    snapshot_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id VARCHAR(100) NOT NULL REFERENCES games(game_id),
    sim_id UUID REFERENCES simulations(sim_id),
    
    -- Timing
    captured_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    wave VARCHAR(50),  -- WAVE_1_DISCOVERY, WAVE_2_VALIDATION, WAVE_3_PUBLISH
    
    -- Spread market
    team_a_spread DECIMAL(5, 2),
    team_a_spread_odds INT,
    team_b_spread DECIMAL(5, 2),
    team_b_spread_odds INT,
    
    -- Totals market
    over_line DECIMAL(5, 2),
    over_odds INT,
    under_line DECIMAL(5, 2),
    under_odds INT,
    
    -- Moneyline market
    team_a_ml_odds INT,
    team_b_ml_odds INT,
    
    -- Sportsbook
    sportsbook VARCHAR(100) DEFAULT 'DraftKings',
    
    -- Deltas from previous snapshot
    spread_delta DECIMAL(5, 2),
    total_delta DECIMAL(5, 2)
);

CREATE INDEX idx_market_snapshots_game_id ON market_snapshots(game_id);
CREATE INDEX idx_market_snapshots_captured_at ON market_snapshots(captured_at);


-- =============================================================================
-- SIGNALS & PUBLISHING
-- =============================================================================

CREATE TABLE signals (
    signal_id VARCHAR(100) PRIMARY KEY,
    game_id VARCHAR(100) NOT NULL REFERENCES games(game_id),
    
    -- Signal metadata
    status VARCHAR(50) NOT NULL,  -- DISCOVERED, VALIDATING, PUBLISHED, LOCKED, GRADED
    intent VARCHAR(50) NOT NULL,  -- TRUTH_MODE, PARLAY_MODE, B2B_SIMSPORTS
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP,
    locked_at TIMESTAMP,  -- Game started
    graded_at TIMESTAMP,
    
    -- Entry snapshot (captured at publish)
    entry_sharp_side VARCHAR(100),
    entry_market_type VARCHAR(50),
    entry_spread DECIMAL(5, 2),
    entry_total DECIMAL(5, 2),
    entry_odds INT,
    max_acceptable_spread DECIMAL(5, 2),
    max_acceptable_total DECIMAL(5, 2),
    max_acceptable_odds INT,
    
    -- Result
    final_result VARCHAR(50),  -- WIN, LOSS, PUSH
    
    -- Action freeze (prevent re-sim spam)
    freeze_until TIMESTAMP,
    freeze_reason TEXT,
    
    -- Latest simulation reference
    latest_sim_id UUID REFERENCES simulations(sim_id)
);

CREATE INDEX idx_signals_game_id ON signals(game_id);
CREATE INDEX idx_signals_status ON signals(status);
CREATE INDEX idx_signals_intent ON signals(intent);
CREATE INDEX idx_signals_published_at ON signals(published_at);


-- =============================================================================
-- SHARP PASS VERIFICATION
-- =============================================================================

CREATE TABLE sharp_pass_applications (
    application_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    
    -- CSV upload
    csv_url TEXT NOT NULL,
    csv_filename VARCHAR(255),
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Analysis results
    total_bets INT,
    profitable_bets INT,
    losing_bets INT,
    push_bets INT,
    clv_edge_percentage DECIMAL(5, 2),
    
    -- Verification
    status VARCHAR(50) DEFAULT 'PENDING',  -- PENDING, APPROVED, REJECTED
    reviewed_by UUID REFERENCES users(user_id),
    reviewed_at TIMESTAMP,
    rejection_reason TEXT,
    
    -- Requirements check
    meets_bet_count_requirement BOOLEAN,  -- 500+ bets
    meets_clv_requirement BOOLEAN,  -- 2.0%+ CLV edge
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sharp_pass_applications_user_id ON sharp_pass_applications(user_id);
CREATE INDEX idx_sharp_pass_applications_status ON sharp_pass_applications(status);


-- =============================================================================
-- BET HISTORY & TRACKING
-- =============================================================================

CREATE TABLE bet_history (
    bet_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    signal_id VARCHAR(100) REFERENCES signals(signal_id),
    game_id VARCHAR(100) REFERENCES games(game_id),
    
    -- Bet details
    bet_type VARCHAR(50),  -- SPREAD, TOTAL, MONEYLINE, PARLAY
    bet_side VARCHAR(100),
    stake DECIMAL(10, 2),
    odds INT,
    
    -- Entry details
    entry_spread DECIMAL(5, 2),
    entry_total DECIMAL(5, 2),
    entry_price INT,
    
    -- Result
    result VARCHAR(50),  -- WIN, LOSS, PUSH, PENDING
    profit_loss DECIMAL(10, 2),
    
    -- CLV tracking
    clv_spread DECIMAL(5, 2),  -- Closing line spread
    clv_total DECIMAL(5, 2),  -- Closing line total
    clv_odds INT,  -- Closing line odds
    clv_edge DECIMAL(5, 2),  -- CLV edge percentage
    
    -- Timing
    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    settled_at TIMESTAMP,
    
    -- Metadata
    sportsbook VARCHAR(100),
    notes TEXT
);

CREATE INDEX idx_bet_history_user_id ON bet_history(user_id);
CREATE INDEX idx_bet_history_signal_id ON bet_history(signal_id);
CREATE INDEX idx_bet_history_result ON bet_history(result);
CREATE INDEX idx_bet_history_placed_at ON bet_history(placed_at);


-- =============================================================================
-- COMMUNITY WAR ROOM
-- =============================================================================

CREATE TABLE community_channels (
    channel_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug VARCHAR(100) UNIQUE NOT NULL,
    
    -- Channel metadata
    channel_type VARCHAR(50) NOT NULL,  -- GAME_THREAD, MARKET_THREAD, GENERAL
    title VARCHAR(255) NOT NULL,
    description TEXT,
    
    -- Game association (for game threads)
    game_id VARCHAR(100) REFERENCES games(game_id),
    market_type VARCHAR(50),  -- SPREAD, TOTAL, MONEYLINE (for market threads)
    
    -- Access control
    access_level VARCHAR(50) DEFAULT 'FREE',  -- FREE, PRO, WIRE_PRO, SHARP_PASS
    
    -- Thread metadata
    parent_channel_id UUID REFERENCES community_channels(channel_id),  -- For threaded channels
    
    -- Stats
    post_count INT DEFAULT 0,
    member_count INT DEFAULT 0,
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity_at TIMESTAMP,
    expires_at TIMESTAMP,  -- TTL for game threads
    
    -- Flags
    is_archived BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_community_channels_slug ON community_channels(slug);
CREATE INDEX idx_community_channels_game_id ON community_channels(game_id);
CREATE INDEX idx_community_channels_access_level ON community_channels(access_level);


CREATE TABLE community_posts (
    post_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel_id UUID NOT NULL REFERENCES community_channels(channel_id),
    user_id UUID NOT NULL REFERENCES users(user_id),
    
    -- Content
    content TEXT NOT NULL,
    
    -- Simulation attachment
    sim_id UUID REFERENCES simulations(sim_id),
    
    -- Parent post (for replies)
    parent_post_id UUID REFERENCES community_posts(post_id),
    
    -- Reactions
    upvotes INT DEFAULT 0,
    downvotes INT DEFAULT 0,
    
    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    
    -- Moderation
    is_deleted BOOLEAN DEFAULT FALSE,
    deleted_at TIMESTAMP,
    deleted_by UUID REFERENCES users(user_id)
);

CREATE INDEX idx_community_posts_channel_id ON community_posts(channel_id);
CREATE INDEX idx_community_posts_user_id ON community_posts(user_id);
CREATE INDEX idx_community_posts_created_at ON community_posts(created_at);
CREATE INDEX idx_community_posts_sim_id ON community_posts(sim_id);


-- =============================================================================
-- AUDIT & LOGGING
-- =============================================================================

CREATE TABLE sim_audit (
    audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sim_id UUID REFERENCES simulations(sim_id),
    game_id VARCHAR(100) REFERENCES games(game_id),
    
    -- Event
    event_type VARCHAR(100) NOT NULL,  -- WAVE_1_COMPLETE, EDGE_DRIFT_DETECTED, PUBLISHED, etc.
    event_data JSONB,
    
    -- Context
    triggered_by VARCHAR(100),  -- CRON, API, USER
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sim_audit_sim_id ON sim_audit(sim_id);
CREATE INDEX idx_sim_audit_game_id ON sim_audit(game_id);
CREATE INDEX idx_sim_audit_event_type ON sim_audit(event_type);


CREATE TABLE rcl_log (
    log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    game_id VARCHAR(100) REFERENCES games(game_id),
    
    -- RCL data
    sport VARCHAR(50),
    market_type VARCHAR(50),
    
    -- Opening line
    opening_spread DECIMAL(5, 2),
    opening_total DECIMAL(5, 2),
    opening_ml_favorite INT,
    opening_ml_underdog INT,
    opening_time TIMESTAMP,
    
    -- Closing line
    closing_spread DECIMAL(5, 2),
    closing_total DECIMAL(5, 2),
    closing_ml_favorite INT,
    closing_ml_underdog INT,
    closing_time TIMESTAMP,
    
    -- Movement
    line_movement DECIMAL(5, 2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rcl_log_game_id ON rcl_log(game_id);
CREATE INDEX idx_rcl_log_sport ON rcl_log(sport);


-- =============================================================================
-- CALIBRATION & MONITORING
-- =============================================================================

CREATE TABLE calibration_weekly (
    calibration_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sport VARCHAR(50) NOT NULL,
    market_type VARCHAR(50) NOT NULL,
    
    -- Week
    week_start DATE NOT NULL,
    week_end DATE NOT NULL,
    
    -- Performance
    total_signals INT,
    wins INT,
    losses INT,
    pushes INT,
    win_rate DECIMAL(5, 2),
    
    -- Edge calibration
    avg_predicted_edge DECIMAL(5, 2),
    avg_actual_edge DECIMAL(5, 2),
    edge_calibration_error DECIMAL(5, 2),
    
    -- Probability calibration
    avg_predicted_prob DECIMAL(5, 2),
    avg_actual_prob DECIMAL(5, 2),
    prob_calibration_error DECIMAL(5, 2),
    
    -- ROI
    total_staked DECIMAL(10, 2),
    total_profit DECIMAL(10, 2),
    roi_percentage DECIMAL(5, 2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_calibration_weekly_sport ON calibration_weekly(sport);
CREATE INDEX idx_calibration_weekly_week_start ON calibration_weekly(week_start);


-- =============================================================================
-- PARLAYS & PARLAY BUILDER
-- =============================================================================

CREATE TABLE parlays (
    parlay_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    
    -- Parlay details
    parlay_name VARCHAR(255),
    num_legs INT NOT NULL,
    total_odds INT,
    stake DECIMAL(10, 2),
    potential_payout DECIMAL(10, 2),
    
    -- Result
    status VARCHAR(50) DEFAULT 'PENDING',  -- PENDING, WON, LOST
    settled_at TIMESTAMP,
    actual_payout DECIMAL(10, 2),
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE parlay_legs (
    leg_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    parlay_id UUID NOT NULL REFERENCES parlays(parlay_id),
    signal_id VARCHAR(100) REFERENCES signals(signal_id),
    game_id VARCHAR(100) REFERENCES games(game_id),
    
    -- Leg details
    bet_side VARCHAR(100),
    market_type VARCHAR(50),
    odds INT,
    
    -- Result
    result VARCHAR(50),  -- WIN, LOSS, PUSH, PENDING
    
    leg_order INT  -- Position in parlay
);

CREATE INDEX idx_parlay_legs_parlay_id ON parlay_legs(parlay_id);
CREATE INDEX idx_parlay_legs_signal_id ON parlay_legs(signal_id);


-- =============================================================================
-- B2B SIMSPORTS
-- =============================================================================

CREATE TABLE simsports_api_requests (
    request_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(user_id),
    
    -- Request details
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    request_params JSONB,
    
    -- Response
    status_code INT,
    response_data JSONB,
    
    -- Usage tracking
    simulations_consumed INT DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_simsports_api_requests_user_id ON simsports_api_requests(user_id);
CREATE INDEX idx_simsports_api_requests_created_at ON simsports_api_requests(created_at);


-- =============================================================================
-- TELEGRAM INTEGRATION
-- =============================================================================

CREATE TABLE telegram_channels (
    channel_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_chat_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Channel metadata
    channel_type VARCHAR(50),  -- SIGNALS, COMMUNITY, DM
    access_level VARCHAR(50),  -- FREE, STARTER, PRO, ELITE, SHARP_PASS
    
    -- Stats
    member_count INT DEFAULT 0,
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE telegram_posts (
    post_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_channel_id UUID REFERENCES telegram_channels(channel_id),
    signal_id VARCHAR(100) REFERENCES signals(signal_id),
    
    -- Message
    message_text TEXT NOT NULL,
    telegram_message_id VARCHAR(100),
    
    -- Timing
    posted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    scheduled_for TIMESTAMP
);

CREATE INDEX idx_telegram_posts_signal_id ON telegram_posts(signal_id);
CREATE INDEX idx_telegram_posts_posted_at ON telegram_posts(posted_at);


-- =============================================================================
-- VIEWS FOR REPORTING
-- =============================================================================

CREATE VIEW v_active_signals AS
SELECT 
    s.signal_id,
    s.game_id,
    g.sport,
    g.team_a,
    g.team_b,
    g.scheduled_time,
    s.status,
    s.intent,
    s.entry_sharp_side,
    s.entry_market_type,
    sim.compressed_edge,
    sim.volatility,
    s.published_at
FROM signals s
JOIN games g ON s.game_id = g.game_id
LEFT JOIN simulations sim ON s.latest_sim_id = sim.sim_id
WHERE s.status IN ('PUBLISHED', 'LOCKED')
AND g.game_status != 'FINAL';


CREATE VIEW v_user_performance AS
SELECT 
    u.user_id,
    u.display_name,
    u.subscription_tier,
    u.sharp_pass_status,
    COUNT(bh.bet_id) as total_bets,
    SUM(CASE WHEN bh.result = 'WIN' THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN bh.result = 'LOSS' THEN 1 ELSE 0 END) as losses,
    SUM(CASE WHEN bh.result = 'PUSH' THEN 1 ELSE 0 END) as pushes,
    ROUND(AVG(CASE WHEN bh.result IN ('WIN', 'LOSS') THEN 
        CASE WHEN bh.result = 'WIN' THEN 1.0 ELSE 0.0 END 
    END) * 100, 2) as win_rate,
    SUM(bh.profit_loss) as total_profit,
    ROUND(AVG(bh.clv_edge), 2) as avg_clv_edge
FROM users u
LEFT JOIN bet_history bh ON u.user_id = bh.user_id
GROUP BY u.user_id, u.display_name, u.subscription_tier, u.sharp_pass_status;
