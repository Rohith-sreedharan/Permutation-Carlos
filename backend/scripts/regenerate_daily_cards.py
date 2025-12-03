"""
Cron Script: Regenerate Daily Best Cards
Run every 6 hours to refresh flagship content
"""
import requests
import sys
from datetime import datetime

# Backend API URL
API_URL = "http://localhost:8000"

def regenerate_cards():
    """Trigger daily cards regeneration"""
    try:
        print(f"[{datetime.now()}] Regenerating daily best cards...")
        
        response = requests.post(
            f"{API_URL}/api/daily-cards/regenerate",
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            cards = data.get("cards", {})
            
            print("✅ Daily cards regenerated successfully!")
            print(f"   • Best Game: {cards.get('best_game_overall', {}).get('matchup', 'N/A')}")
            print(f"   • Top NBA: {cards.get('top_nba_game', {}).get('matchup', 'N/A')}")
            print(f"   • Top NCAAB: {cards.get('top_ncaab_game', {}).get('matchup', 'N/A')}")
            print(f"   • Top NCAAF: {cards.get('top_ncaaf_game', {}).get('matchup', 'N/A')}")
            print(f"   • Top Prop: {cards.get('top_prop_mispricing', {}).get('player_name', 'N/A')}")
            print(f"   • Parlay: {cards.get('parlay_preview', {}).get('status', 'N/A')}")
            print(f"   • Generated at: {cards.get('generated_at', 'N/A')}")
            
            return 0
        else:
            print(f"❌ Failed to regenerate cards: {response.status_code}")
            print(f"   Response: {response.text}")
            return 1
    
    except requests.exceptions.ConnectionError:
        print("❌ Connection error: Is the backend running on http://localhost:8000?")
        return 1
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1


if __name__ == "__main__":
    exit_code = regenerate_cards()
    sys.exit(exit_code)
