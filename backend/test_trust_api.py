"""
Quick test script for Phase 17 Trust Loop API
"""
import requests
import json

BASE_URL = "http://localhost:8000"

def test_trust_endpoints():
    """Test all Phase 17 Trust Loop endpoints"""
    
    print("🧪 Testing Phase 17 Trust Loop API\n")
    
    endpoints = [
        ("GET /api/trust/metrics", f"{BASE_URL}/api/trust/metrics"),
        ("GET /api/trust/yesterday", f"{BASE_URL}/api/trust/yesterday"),
        ("GET /api/trust/trend?days=7", f"{BASE_URL}/api/trust/trend?days=7"),
        ("GET /api/trust/history?days=7&limit=10", f"{BASE_URL}/api/trust/history?days=7&limit=10"),
        ("GET /api/trust/calibration", f"{BASE_URL}/api/trust/calibration"),
    ]
    
    for name, url in endpoints:
        try:
            print(f"Testing: {name}")
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                print(f"  ✅ Success ({response.status_code})")
                print(f"  📊 Response keys: {list(data.keys()) if isinstance(data, dict) else f'{len(data)} items'}")
            else:
                print(f"  ❌ Failed ({response.status_code})")
                print(f"  Error: {response.text[:200]}")
        except requests.exceptions.ConnectionError:
            print(f"  ⚠️  Backend not running. Start with: cd backend && uvicorn main:app --reload")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        print()

if __name__ == '__main__':
    test_trust_endpoints()
