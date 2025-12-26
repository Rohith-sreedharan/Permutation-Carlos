"""
🔒 TELEGRAM SAFETY AUDIT
Critical safety validation for Telegram auto-posting

This tool audits Telegram posts to ensure:
- Only EDGE posts go live
- No LEANS leak into EDGE channel
- No injury-compromised posts
- No duplicate or stale posts
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from db.mongo import db
from pymongo.database import Database


class TelegramSafetyAuditor:
    """Audit Telegram posting safety and compliance"""
    
    def __init__(self, database: Database):
        self.db = database
        self.violations: List[Dict[str, Any]] = []
        self.warnings: List[str] = []
    
    async def run_safety_audit(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Run comprehensive Telegram safety audit
        
        Args:
            hours_back: How many hours of history to audit
        
        Returns:
            Audit report with violations and recommendations
        """
        print("\n🔒 TELEGRAM SAFETY AUDIT")
        print(f"Auditing last {hours_back} hours")
        print("="*80)
        
        cutoff_time = datetime.now() - timedelta(hours=hours_back)
        
        # 1. Check for LEAN leakage into EDGE channel
        await self._check_lean_leakage(cutoff_time)
        
        # 2. Check for injury-compromised posts
        await self._check_injury_compromised_posts(cutoff_time)
        
        # 3. Check for duplicate posts
        await self._check_duplicate_posts(cutoff_time)
        
        # 4. Check for stale posts
        await self._check_stale_posts(cutoff_time)
        
        # 5. Verify state consistency
        await self._check_state_consistency(cutoff_time)
        
        # Print results
        self._print_audit_results()
        
        # Generate report
        report = self._generate_audit_report()
        
        # Determine if freeze needed
        if self._should_freeze():
            print("\n🚨 IMMEDIATE FREEZE REQUIRED")
            print("Critical violations detected. PAUSE auto-posting immediately.")
            report["freeze_required"] = True
        else:
            print("\n✅ No critical violations detected")
            report["freeze_required"] = False
        
        return report
    
    async def _check_lean_leakage(self, cutoff_time: datetime):
        """Check if any LEANs were posted to EDGE channel"""
        print("\n1️⃣ Checking for LEAN leakage into EDGE channel...")
        
        try:
            # Query Telegram posts (adjust collection name as needed)
            posts = list(self.db.db["telegram_posts"].find({
                "posted_at": {"$gte": cutoff_time},
                "channel_type": "EDGE"  # Assuming you track channel type
            }))
            
            for post in posts:
                # Check if the associated wave was actually a LEAN
                wave_id = post.get("wave_id")
                if wave_id:
                    wave = self.db.db["autonomous_edge_waves"].find_one({"_id": wave_id})
                    if wave and wave.get("state") == "LEAN_CONFIRMED":
                        self.violations.append({
                            "type": "LEAN_LEAKAGE",
                            "severity": "CRITICAL",
                            "post_id": str(post.get("_id")),
                            "wave_id": str(wave_id),
                            "posted_at": post.get("posted_at"),
                            "details": "LEAN was posted to EDGE channel"
                        })
            
            lean_violations = [v for v in self.violations if v["type"] == "LEAN_LEAKAGE"]
            if lean_violations:
                print(f"   🚨 CRITICAL: {len(lean_violations)} LEAN leakage(s) detected")
            else:
                print("   ✅ No LEAN leakage detected")
        
        except Exception as e:
            print(f"   ⚠️  Error checking LEAN leakage: {e}")
            self.warnings.append(f"Error checking LEAN leakage: {e}")
    
    async def _check_injury_compromised_posts(self, cutoff_time: datetime):
        """Check if any posts were made despite injury uncertainty"""
        print("\n2️⃣ Checking for injury-compromised posts...")
        
        try:
            posts = list(self.db.db["telegram_posts"].find({
                "posted_at": {"$gte": cutoff_time}
            }))
            
            for post in posts:
                wave_id = post.get("wave_id")
                if wave_id:
                    wave = self.db.db["autonomous_edge_waves"].find_one({"_id": wave_id})
                    if wave:
                        # Check for injury flags
                        reason_codes = wave.get("reason_codes", [])
                        has_injury_flag = any("injury" in str(code).lower() for code in reason_codes)
                        
                        if has_injury_flag:
                            self.violations.append({
                                "type": "INJURY_COMPROMISED",
                                "severity": "CRITICAL",
                                "post_id": str(post.get("_id")),
                                "wave_id": str(wave_id),
                                "posted_at": post.get("posted_at"),
                                "details": "Post made despite injury uncertainty"
                            })
            
            injury_violations = [v for v in self.violations if v["type"] == "INJURY_COMPROMISED"]
            if injury_violations:
                print(f"   🚨 CRITICAL: {len(injury_violations)} injury-compromised post(s) detected")
            else:
                print("   ✅ No injury-compromised posts detected")
        
        except Exception as e:
            print(f"   ⚠️  Error checking injury-compromised posts: {e}")
            self.warnings.append(f"Error checking injury-compromised posts: {e}")
    
    async def _check_duplicate_posts(self, cutoff_time: datetime):
        """Check for duplicate posts of the same game"""
        print("\n3️⃣ Checking for duplicate posts...")
        
        try:
            posts = list(self.db.db["telegram_posts"].find({
                "posted_at": {"$gte": cutoff_time}
            }))
            
            # Group by game_id
            game_posts = defaultdict(list)
            for post in posts:
                game_id = post.get("game_id")
                if game_id:
                    game_posts[game_id].append(post)
            
            # Check for duplicates
            for game_id, posts_list in game_posts.items():
                if len(posts_list) > 1:
                    self.violations.append({
                        "type": "DUPLICATE_POST",
                        "severity": "HIGH",
                        "game_id": game_id,
                        "post_count": len(posts_list),
                        "details": f"Game posted {len(posts_list)} times"
                    })
            
            dup_violations = [v for v in self.violations if v["type"] == "DUPLICATE_POST"]
            if dup_violations:
                print(f"   ⚠️  {len(dup_violations)} duplicate post(s) detected")
            else:
                print("   ✅ No duplicate posts detected")
        
        except Exception as e:
            print(f"   ⚠️  Error checking duplicate posts: {e}")
            self.warnings.append(f"Error checking duplicate posts: {e}")
    
    async def _check_stale_posts(self, cutoff_time: datetime):
        """Check for posts made too close to game time (stale data)"""
        print("\n4️⃣ Checking for stale posts...")
        
        try:
            posts = list(self.db.db["telegram_posts"].find({
                "posted_at": {"$gte": cutoff_time}
            }))
            
            for post in posts:
                posted_at = post.get("posted_at")
                game_time = post.get("game_time")
                
                if posted_at and game_time:
                    # Check if posted within 30 minutes of game start
                    time_diff = (game_time - posted_at).total_seconds() / 60
                    
                    if time_diff < 30:
                        self.warnings.append(
                            f"Post made {time_diff:.0f} minutes before game - may be stale"
                        )
            
            print(f"   ℹ️  Checked {len(posts)} posts for staleness")
        
        except Exception as e:
            print(f"   ⚠️  Error checking stale posts: {e}")
            self.warnings.append(f"Error checking stale posts: {e}")
    
    async def _check_state_consistency(self, cutoff_time: datetime):
        """Verify all posted plays have state==EDGE"""
        print("\n5️⃣ Checking state consistency...")
        
        try:
            posts = list(self.db.db["telegram_posts"].find({
                "posted_at": {"$gte": cutoff_time}
            }))
            
            for post in posts:
                wave_id = post.get("wave_id")
                if wave_id:
                    wave = self.db.db["autonomous_edge_waves"].find_one({"_id": wave_id})
                    if wave:
                        state = wave.get("state")
                        
                        # Only EDGE_CONFIRMED or PUBLISHED should be posted
                        if state not in ["EDGE_CONFIRMED", "PUBLISHED"]:
                            self.violations.append({
                                "type": "INVALID_STATE",
                                "severity": "CRITICAL",
                                "post_id": str(post.get("_id")),
                                "wave_id": str(wave_id),
                                "state": state,
                                "details": f"Post made with invalid state: {state}"
                            })
            
            state_violations = [v for v in self.violations if v["type"] == "INVALID_STATE"]
            if state_violations:
                print(f"   🚨 CRITICAL: {len(state_violations)} invalid state post(s) detected")
            else:
                print("   ✅ All posts have valid state")
        
        except Exception as e:
            print(f"   ⚠️  Error checking state consistency: {e}")
            self.warnings.append(f"Error checking state consistency: {e}")
    
    def _print_audit_results(self):
        """Print audit results"""
        print("\n" + "="*80)
        print("🔍 AUDIT RESULTS")
        print("="*80)
        
        if not self.violations and not self.warnings:
            print("\n✅ CLEAN AUDIT - No violations or warnings")
            return
        
        # Print critical violations
        critical = [v for v in self.violations if v["severity"] == "CRITICAL"]
        if critical:
            print(f"\n🚨 CRITICAL VIOLATIONS ({len(critical)}):")
            for v in critical:
                print(f"   • {v['type']}: {v['details']}")
        
        # Print high severity violations
        high = [v for v in self.violations if v["severity"] == "HIGH"]
        if high:
            print(f"\n⚠️  HIGH SEVERITY ({len(high)}):")
            for v in high:
                print(f"   • {v['type']}: {v['details']}")
        
        # Print warnings
        if self.warnings:
            print(f"\nℹ️  WARNINGS ({len(self.warnings)}):")
            for w in self.warnings[:10]:  # Limit to 10
                print(f"   • {w}")
    
    def _should_freeze(self) -> bool:
        """Determine if auto-posting should be frozen"""
        critical_violations = [v for v in self.violations if v["severity"] == "CRITICAL"]
        return len(critical_violations) > 0
    
    def _generate_audit_report(self) -> Dict[str, Any]:
        """Generate audit report"""
        critical = [v for v in self.violations if v["severity"] == "CRITICAL"]
        high = [v for v in self.violations if v["severity"] == "HIGH"]
        
        return {
            "timestamp": datetime.now().isoformat(),
            "violations": self.violations,
            "warnings": self.warnings,
            "summary": {
                "total_violations": len(self.violations),
                "critical_violations": len(critical),
                "high_severity_violations": len(high),
                "warnings": len(self.warnings)
            },
            "freeze_required": self._should_freeze()
        }


async def main():
    """Run Telegram safety audit"""
    import asyncio
    from db.mongo import db
    
    auditor = TelegramSafetyAuditor(db)
    
    # Allow specifying hours via command line
    hours = int(sys.argv[1]) if len(sys.argv) > 1 else 24
    
    report = await auditor.run_safety_audit(hours)
    
    print("\n" + "="*80)
    print("AUDIT COMPLETE")
    if report["freeze_required"]:
        print("🚨 ACTION REQUIRED: Freeze auto-posting and investigate")
        sys.exit(1)
    else:
        print("✅ No action required")
        sys.exit(0)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
