"""
Seed Community Content
Run this script to populate the community with initial content
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.community_bot import community_bot
from db.mongo import db

def seed_community():
    """Seed community with initial content"""
    print("🌱 Seeding community with content...\n")
    
    # 1. Generate game threads for today
    print("📅 Generating game threads...")
    game_threads = community_bot.generate_daily_game_threads()
    if game_threads:
        count = community_bot.post_messages(game_threads)
        print(f"✓ Posted {count} game threads\n")
    else:
        print("ℹ️  No games today\n")
    
    # 2. Generate daily prompt
    print("💬 Generating daily prompt...")
    prompt = community_bot.generate_daily_prompt()
    community_bot.post_message(prompt)
    print(f"✓ Posted: {prompt['content']}\n")
    
    # 3. Add some sample Monte Carlo alerts
    print("🎯 Generating sample Monte Carlo alerts...")
    sample_alerts = [
        {
            "game": "Lakers vs Warriors",
            "edge_type": "Sharp Edge Detected",
            "pick": "Lakers",
            "line": "-3.5",
            "win_prob": 63.4,
            "ev": 8.2,
            "channel": "nba-live"
        },
        {
            "game": "Chiefs vs Bills",
            "edge_type": "Value Play",
            "pick": "Bills",
            "line": "+2.5",
            "win_prob": 58.1,
            "ev": 5.7,
            "channel": "nfl-live"
        },
        {
            "game": "Celtics vs Heat",
            "edge_type": "High Confidence",
            "pick": "Celtics",
            "line": "-7.5",
            "win_prob": 71.2,
            "ev": 12.3,
            "channel": "nba-live"
        }
    ]
    
    for alert in sample_alerts:
        msg = community_bot.generate_monte_carlo_alert(**alert)
        community_bot.post_message(msg)
    print(f"✓ Posted {len(sample_alerts)} Monte Carlo alerts\n")
    
    # 4. Add sample injury alert
    print("🚨 Generating sample injury alert...")
    injury = community_bot.generate_injury_alert(
        player="LeBron James",
        team="Lakers",
        status="Questionable",
        sport="NBA"
    )
    community_bot.post_message(injury)
    print("✓ Posted injury alert\n")
    
    # 5. Add sample line movement alert
    print("📈 Generating sample line movement alert...")
    line_move = community_bot.generate_line_movement_alert(
        game="Patriots vs Dolphins",
        market="Spread",
        old_line=-3.5,
        new_line=-5.5,
        movement_pct=7.2
    )
    community_bot.post_message(line_move)
    print("✓ Posted line movement alert\n")
    
    # 6. Add sample parlay win celebration
    print("🎰 Generating sample parlay win...")
    parlay_win = community_bot.generate_parlay_win_celebration(
        user="SharpBettor42",
        legs=4,
        odds="+1250",
        profit=625.00
    )
    community_bot.post_message(parlay_win)
    print("✓ Posted parlay win celebration\n")
    
    # 7. Add sample AI commentary
    print("💡 Generating sample AI commentary...")
    ai_comment = community_bot.generate_ai_commentary(
        insight="The Warriors' defense has allowed 118+ points in 7 of their last 10 games. Lakers averaging 112 PPG on the road. Over 228.5 looks favorable.",
        confidence=67.8,
        game="Lakers vs Warriors"
    )
    community_bot.post_message(ai_comment)
    print("✓ Posted AI commentary\n")
    
    # 8. Add volatility alert
    print("⚡ Generating volatility alert...")
    volatility = community_bot.generate_volatility_alert(
        game="Knicks vs Nets",
        market="Total",
        old_value=221.0,
        new_value=226.5,
        time_window="40 minutes"
    )
    community_bot.post_message(volatility)
    print("✓ Posted volatility alert\n")
    
    # 9. Add top public pick
    print("📊 Generating top public pick...")
    public_pick = community_bot.generate_top_public_pick(
        pick="Celtics ML",
        game="Celtics vs Heat",
        percentage=78.3,
        total_users=247
    )
    community_bot.post_message(public_pick)
    print("✓ Posted top public pick\n")
    
    # Count total messages
    total_messages = db["community_messages"].count_documents({})
    print(f"🎉 Seeding complete! Total messages in database: {total_messages}")

if __name__ == "__main__":
    seed_community()
