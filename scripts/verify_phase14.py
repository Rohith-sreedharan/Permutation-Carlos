#!/usr/bin/env python3
"""
MASTER SYSTEM VERIFICATION PROTOCOL: PHASE 1-14
Comprehensive end-to-end validation of BeatVegas Intelligence Platform
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Any
import sys

# Configuration
BASE_URL = "http://localhost:8000"
FRONTEND_URL = "http://localhost:3000"

# Test results storage
results = {
    "branding": [],
    "sim_engine": [],
    "compliance": [],
    "architect": [],
    "payments": [],
    "v1_launch": []
}

def log_test(category: str, test_name: str, passed: bool, notes: str = ""):
    """Log test result"""
    status = "🟢 PASS" if passed else "🔴 FAIL"
    results[category].append({
        "test": test_name,
        "status": status,
        "notes": notes
    })
    print(f"{status} | {test_name}: {notes}")

def test_backend_health():
    """Verify backend is running"""
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        log_test("sim_engine", "Backend Health", response.status_code == 200, 
                f"Status: {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        log_test("sim_engine", "Backend Health", False, f"Error: {str(e)}")
        return False

def test_simulation_tiers():
    """Test tiered compute model (2k vs 100k iterations)"""
    print("\n=== PART 1: SIMULATION ENGINE TIERS ===")
    
    # Check if events exist in DB first
    test_event_id = None
    try:
        response = requests.get(f"{BASE_URL}/api/odds/list?limit=1", timeout=5)
        if response.status_code == 200:
            data = response.json()
            events = data.get("events", [])
            if not events:
                log_test("sim_engine", "Starter Tier (2k)", False, 
                        "No events in DB - sync odds first")
                log_test("sim_engine", "Elite Tier (100k)", False, 
                        "No events in DB - sync odds first")
                return
            
            test_event_id = events[0].get("event_id")
            log_test("sim_engine", "Events Available", True, 
                    f"Found {data.get('count', 0)} total events")
        else:
            log_test("sim_engine", "Events Check", False, f"Status: {response.status_code}")
            return
    except Exception as e:
        log_test("sim_engine", "Events Check", False, f"Error: {str(e)}")
        return
    
    # Test A: Starter tier (2k iterations)
    if test_event_id:
        try:
            response = requests.get(
                f"{BASE_URL}/api/simulations/{test_event_id}",
                headers={"Authorization": "Bearer starter_user_token"}
            )
            
            if response.status_code == 200:
                data = response.json()
                iterations = data.get("metadata", {}).get("iterations_run", 0)
                passed = iterations == 2000
                log_test("sim_engine", "Starter Tier (2k)", passed, 
                        f"Iterations: {iterations}")
            else:
                log_test("sim_engine", "Starter Tier (2k)", False, 
                        f"Status: {response.status_code}")
        except Exception as e:
            log_test("sim_engine", "Starter Tier (2k)", False, f"Error: {str(e)}")
    
        # Test B: Elite tier (100k iterations)
        try:
            response = requests.get(
                f"{BASE_URL}/api/simulations/{test_event_id}",
                headers={"Authorization": "Bearer elite_user_token"}
            )
            
            if response.status_code == 200:
                data = response.json()
                iterations = data.get("metadata", {}).get("iterations_run", 0)
                passed = iterations == 100000
                log_test("sim_engine", "Elite Tier (100k)", passed, 
                        f"Iterations: {iterations}")
            else:
                log_test("sim_engine", "Elite Tier (100k)", False, 
                        f"Status: {response.status_code}")
        except Exception as e:
            log_test("sim_engine", "Elite Tier (100k)", False, f"Error: {str(e)}")

def test_parlay_architect():
    """Test AI Parlay Architect endpoints"""
    print("\n=== PART 4: PARLAY ARCHITECT ===")
    
    # Test generation endpoint
    try:
        response = requests.post(
            f"{BASE_URL}/api/architect/generate",
            json={
                "sport_key": "basketball_nba",
                "leg_count": 4,
                "risk_profile": "balanced"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            has_preview = "legs_preview" in data or "legs" in data
            is_locked = not data.get("is_unlocked", False)
            has_price = "unlock_price" in data
            
            log_test("architect", "Generate Parlay", has_preview, 
                    f"Locked: {is_locked}, Price: ${data.get('unlock_price', 0)/100:.2f}")
        elif response.status_code == 400:
            error = response.json().get("detail", "")
            if "Insufficient" in error:
                log_test("architect", "Generate Parlay", False, 
                        "No events in DB - sync odds first")
            else:
                log_test("architect", "Generate Parlay", False, error)
        else:
            log_test("architect", "Generate Parlay", False, 
                    f"Status: {response.status_code}")
    except Exception as e:
        log_test("architect", "Generate Parlay", False, f"Error: {str(e)}")
    
    # Test Elite tokens endpoint
    try:
        response = requests.get(
            f"{BASE_URL}/api/architect/tokens",
            params={"user_id": "test_elite_user"}
        )
        
        if response.status_code == 200:
            data = response.json()
            log_test("architect", "Elite Tokens API", True, 
                    f"Tokens: {data.get('tokens_remaining', 0)}")
        else:
            log_test("architect", "Elite Tokens API", False, 
                    f"Status: {response.status_code}")
    except Exception as e:
        log_test("architect", "Elite Tokens API", False, f"Error: {str(e)}")

def test_payment_endpoints():
    """Test micro-transaction payment endpoints"""
    print("\n=== PART 3: PAYMENTS ===")
    
    # Test micro-charge endpoint
    try:
        response = requests.post(
            f"{BASE_URL}/api/payment/create-micro-charge",
            json={
                "product_id": "parlay_3_leg",
                "user_id": "test_user",
                "parlay_id": "test_parlay_123"
            }
        )
        
        # Note: This will fail if Stripe keys aren't configured
        if response.status_code == 200:
            data = response.json()
            has_url = "checkout_url" in data
            log_test("payments", "Micro-Transaction API", has_url, 
                    f"Price: ${data.get('price', 0)/100:.2f}")
        elif response.status_code == 500:
            error = response.json().get("detail", "")
            if "Stripe" in error:
                log_test("payments", "Micro-Transaction API", False, 
                        "Stripe keys not configured")
            else:
                log_test("payments", "Micro-Transaction API", False, error)
        else:
            log_test("payments", "Micro-Transaction API", False, 
                    f"Status: {response.status_code}")
    except Exception as e:
        log_test("payments", "Micro-Transaction API", False, f"Error: {str(e)}")

def test_branding_compliance():
    """Check for forbidden neon blue branding"""
    print("\n=== PART 2: BRANDING AUDIT ===")
    
    # Check key component files for electric-blue
    files_to_check = [
        "components/DecisionCommandCenter.tsx",
        "components/ParlayArchitect.tsx",
        "components/Sidebar.tsx",
        "components/GameDetail.tsx",
        "App.tsx"
    ]
    
    forbidden_colors = ["#00CFFF", "electric-blue", "neon-blue"]
    violations = []
    
    import os
    for file_path in files_to_check:
        full_path = os.path.join("/Users/rohithaditya/Downloads/Permutation-Carlos", file_path)
        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                content = f.read()
                for color in forbidden_colors:
                    if color in content:
                        violations.append(f"{file_path}: {color}")
    
    if violations:
        log_test("branding", "No Neon Blue", False, f"Found: {', '.join(violations)}")
    else:
        log_test("branding", "No Neon Blue", True, "All files use Gold/Red theme")
    
    # Check for required gold colors
    required_colors = ["#D4A64A", "gold"]
    gold_found = False
    
    for file_path in files_to_check:
        full_path = os.path.join("/Users/rohithaditya/Downloads/Permutation-Carlos", file_path)
        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                content = f.read()
                if any(color in content for color in required_colors):
                    gold_found = True
                    break
    
    log_test("branding", "Gold Theme Active", gold_found, 
            "Gold (#D4A64A) detected" if gold_found else "No gold colors found")

def test_v1_launch_components():
    """Test V1 Launch components"""
    print("\n=== PART 3: V1 LAUNCH ===")
    
    # Test waitlist endpoint
    try:
        response = requests.get(f"{BASE_URL}/api/waitlist/count")
        
        if response.status_code == 200:
            data = response.json()
            count = data.get("count", 0)
            founder_count = data.get("founder_count", 0)
            log_test("v1_launch", "Waitlist Counter", True, 
                    f"Total: {count}, Founders: {founder_count}/300")
        else:
            log_test("v1_launch", "Waitlist Counter", False, 
                    f"Status: {response.status_code}")
    except Exception as e:
        log_test("v1_launch", "Waitlist Counter", False, f"Error: {str(e)}")

def check_compliance_terminology():
    """Check for forbidden betting terminology in user-facing text"""
    print("\n=== COMPLIANCE CHECK ===")
    
    files_to_check = [
        "components/DecisionCommandCenter.tsx",
        "components/ParlayArchitect.tsx",
        "components/GameDetail.tsx"
    ]
    
    forbidden_patterns = [
        r'"[^"]*\bbet\b[^"]*"',  # "bet" in strings
        r'"[^"]*\bwager\b[^"]*"',  # "wager" in strings
        r'"[^"]*\bguaranteed\b[^"]*"',  # "guaranteed" in strings
        r'>[^<]*\bsure thing\b[^<]*<'  # "sure thing" in JSX content
    ]
    
    violations = []
    
    import os
    import re
    for file_path in files_to_check:
        full_path = os.path.join("/Users/rohithaditya/Downloads/Permutation-Carlos", file_path)
        if os.path.exists(full_path):
            with open(full_path, 'r') as f:
                content = f.read()
                for pattern in forbidden_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    if matches:
                        violations.append(f"{file_path}: {matches[0]}")
    
    if violations:
        log_test("compliance", "No Betting Terms", False, 
                f"Found: {', '.join(violations[:2])}")
    else:
        log_test("compliance", "No Betting Terms", True, 
                "Using decision/analytical language")

def generate_report():
    """Generate final verification report"""
    print("\n" + "="*70)
    print("MASTER VERIFICATION REPORT - PHASE 1-14")
    print("="*70 + "\n")
    
    print(f"| {'Module':<20} | {'Status':<12} | {'Notes':<35} |")
    print(f"|{'-'*20}|{'-'*12}|{'-'*35}|")
    
    for category, tests in results.items():
        if tests:
            category_name = category.replace("_", " ").title()
            for test in tests:
                print(f"| {test['test']:<20} | {test['status']:<12} | {test['notes']:<35} |")
    
    print("\n" + "="*70)
    
    # Calculate pass rate
    total_tests = sum(len(tests) for tests in results.values())
    passed_tests = sum(
        1 for tests in results.values() 
        for test in tests 
        if "🟢" in test['status']
    )
    
    pass_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
    
    print(f"\nOVERALL PASS RATE: {passed_tests}/{total_tests} ({pass_rate:.1f}%)")
    
    if pass_rate >= 80:
        print("\n✅ SYSTEM STATUS: PRODUCTION READY")
    elif pass_rate >= 60:
        print("\n🟡 SYSTEM STATUS: NEEDS MINOR FIXES")
    else:
        print("\n🔴 SYSTEM STATUS: CRITICAL ISSUES - DO NOT DEPLOY")
    
    print("\n" + "="*70)
    print("\nNEXT STEPS:")
    print("1. Sync odds: curl -X POST http://localhost:8000/api/odds/sync")
    print("2. Configure Stripe keys in backend/.env")
    print("3. Test frontend at http://localhost:3000")
    print("4. Review branding violations if any")
    print("\n" + "="*70)

def main():
    """Run all verification tests"""
    print("="*70)
    print("BEATVEGAS MASTER SYSTEM VERIFICATION - PHASE 1-14")
    print("="*70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Backend: {BASE_URL}")
    print(f"Frontend: {FRONTEND_URL}")
    print("="*70 + "\n")
    
    # Run all tests
    if not test_backend_health():
        print("\n❌ Backend not running! Start with: cd backend && uvicorn main:app --reload")
        sys.exit(1)
    
    test_simulation_tiers()
    test_parlay_architect()
    test_payment_endpoints()
    test_branding_compliance()
    test_v1_launch_components()
    check_compliance_terminology()
    
    # Generate final report
    generate_report()

if __name__ == "__main__":
    main()
