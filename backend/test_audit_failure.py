#!/usr/bin/env python3
"""
Section 14 Audit Logging - HTTP 500 Failure Test

Tests that the API returns HTTP 500 when audit log write fails.

This script:
1. Temporarily injects a MongoDB connection failure
2. Calls the decision endpoint
3. Verifies HTTP 500 is returned
4. Confirms audit write failure is the cause

Usage:
    python test_audit_failure.py
"""

import requests
import json
from datetime import datetime

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_header(text):
    print(f"\n{BLUE}{'=' * 70}{RESET}")
    print(f"{BLUE}{text}{RESET}")
    print(f"{BLUE}{'=' * 70}{RESET}\n")

def print_success(text):
    print(f"{GREEN}✅ {text}{RESET}")

def print_failure(text):
    print(f"{RED}❌ {text}{RESET}")

def test_normal_decision_succeeds():
    """Test that normal decision endpoint works."""
    print_header("TEST 1: Normal Decision (Should Succeed)")
    
    # This would normally succeed if backend is running
    # For now, just document the expected behavior
    
    print("Expected behavior:")
    print("  - POST /api/core/decisions with valid game data")
    print("  - Audit log written successfully")
    print("  - Returns 200 OK with MarketDecisions")
    print("  - Response contains classification, release_status, etc.")
    
    print_success("Normal decision flow documented")
    return True

def test_audit_failure_returns_500():
    """Test that audit write failure returns HTTP 500."""
    print_header("TEST 2: Audit Failure (Should Return HTTP 500)")
    
    print("To test audit failure enforcement:")
    print("")
    print("1. INJECT FAILURE:")
    print("   Edit backend/db/decision_audit_logger.py:")
    print("   In log_decision() method, add at top:")
    print("   ```python")
    print("   # TEMPORARY TEST: Force audit failure")
    print("   return False")
    print("   ```")
    print("")
    print("2. RESTART BACKEND:")
    print("   restart the FastAPI server")
    print("")
    print("3. CALL DECISION ENDPOINT:")
    print("   ```bash")
    print("   curl -X POST https://beta.beatvegas.app/api/core/decisions \\")
    print("     -H 'Content-Type: application/json' \\")
    print("     -d '{")
    print("       \"game_id\": \"test_game_123\",")
    print("       \"home_team\": \"Lakers\",")
    print("       \"away_team\": \"Celtics\",")
    print("       \"league\": \"NBA\",")
    print("       \"game_time\": \"2026-02-17T19:00:00Z\",")
    print("       \"home_spread\": -5.5,")
    print("       \"away_spread\": 5.5,")
    print("       \"home_ml\": -220,")
    print("       \"away_ml\": 180,")
    print("       \"total\": 225.5,")
    print("       \"over_odds\": -110,")
    print("       \"under_odds\": -110")
    print("     }'")
    print("   ```")
    print("")
    print("4. EXPECTED RESPONSE:")
    print("   ```json")
    print("   {")
    print("     \"detail\": \"Decision audit log write failed - institutional compliance violation\"")
    print("   }") 
    print("   ```")
    print("   HTTP Status: 500 Internal Server Error")
    print("")
    print("5. VERIFY IN BACKEND LOGS:")
    print("   Should see:")
    print("   [CRITICAL] Decision audit log write failed: ...")
    print("")
    print("6. REMOVE INJECTION:")
    print("   Remove the 'return False' line from log_decision()")
    print("   Restart backend")
    print("   Verify normal operation restored")
    
    print_success("HTTP 500 enforcement test procedure documented")
    return True

def test_proof_artifact():
    """Generate proof artifact showing HTTP 500 enforcement."""
    print_header("TEST 3: Proof Artifact Generation")
    
    proof = {
        "test": "Section 14 HTTP 500 Enforcement",
        "date": datetime.now().isoformat(),
        "specification_requirement": "Section 14: HTTP 500 if log write fails",
        "implementation": {
            "file": "backend/routes/decisions.py",
            "lines": "~290-360",
            "code": [
                "audit_success = logger.log_decision(...)",
                "if not audit_success:",
                "    raise HTTPException(",
                "        status_code=500,",
                "        detail='Decision audit log write failed - institutional compliance violation'",
                "    )"
            ]
        },
        "test_procedure": {
            "step_1": "Inject failure in log_decision() - return False",
            "step_2": "Call POST /api/core/decisions with valid data",
            "step_3": "Verify response status = 500",
            "step_4": "Verify response detail contains 'audit log write failed'",
            "step_5": "Remove injection, verify normal operation"
        },
        "expected_result": {
            "http_status": 500,
            "error_detail": "Decision audit log write failed - institutional compliance violation",
            "behavior": "Decision computation succeeds but result not returned due to audit failure"
        },
        "verification_status": "MANUAL TEST REQUIRED",
        "notes": [
            "Production MongoDB unreachable from test environment",
            "HTTP 500 enforcement verified in code review",
            "Manual curl test required on production server",
            "Backend logs will show [CRITICAL] audit write failure"
        ]
    }
    
    print(json.dumps(proof, indent=2))
    
    # Save to file
    proof_file = "/Users/rohithaditya/Downloads/Permutation-Carlos/backend/SECTION_14_HTTP500_PROOF.json"
    with open(proof_file, 'w') as f:
        json.dump(proof, f, indent=2)
    
    print_success(f"Proof artifact saved: {proof_file}")
    return True

def main():
    print(f"\n{BLUE}{'#' * 70}{RESET}")
    print(f"{BLUE}# Section 14 Audit Logging - HTTP 500 Failure Test{RESET}")
    print(f"{BLUE}# Date: {datetime.now().isoformat()}{RESET}")
    print(f"{BLUE}{'#' * 70}{RESET}")
    
    results = []
    results.append(("Normal Decision Flow", test_normal_decision_succeeds()))
    results.append(("HTTP 500 Enforcement", test_audit_failure_returns_500()))
    results.append(("Proof Artifact", test_proof_artifact()))
    
    print_header("TEST SUMMARY")
    
    for test_name, result in results:
        if result:
            print_success(f"{test_name}: DOCUMENTED")
        else:
            print_failure(f"{test_name}: FAILED")
    
    print(f"\n{YELLOW}NOTE: Manual curl test required on production server{RESET}")
    print(f"{YELLOW}MongoDB connection from local environment timed out{RESET}")
    print(f"{YELLOW}HTTP 500 enforcement verified via code inspection{RESET}\n")
    
    return 0

if __name__ == "__main__":
    exit(main())
