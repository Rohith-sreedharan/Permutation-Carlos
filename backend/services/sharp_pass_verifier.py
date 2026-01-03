"""
Sharp Pass Verifier

Verifies betting history for Sharp Pass applications using MongoDB.
"""
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import csv
from io import StringIO
from bson import ObjectId

from ..db.database import Database


class SharpPassVerifier:
    """Verify Sharp Pass applications"""
    
    def __init__(self, db: Database):
        self.db = db
        
    async def process_csv_upload(
        self,
        user_id: str,
        csv_content: str
    ) -> Dict:
        """Process uploaded betting history CSV"""
        # Parse CSV
        reader = csv.DictReader(StringIO(csv_content))
        bets = list(reader)
        
        # Validate format
        required_fields = ["date", "sport", "pick", "odds", "result"]
        if not all(field in bets[0] for field in required_fields):
            raise ValueError("Invalid CSV format")
            
        # Calculate metrics
        total_bets = len(bets)
        wins = sum(1 for bet in bets if bet["result"].upper() == "WIN")
        win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
        
        # Calculate CLV (placeholder - would need actual market data)
        avg_clv = 0.0  # TODO: Calculate from historical odds
        
        # Determine eligibility
        eligible = (
            total_bets >= 100 and
            win_rate >= 55 and
            avg_clv >= 1.5
        )
        
        # Store application
        doc = {
            "user_id": user_id,
            "total_bets": total_bets,
            "win_rate": win_rate,
            "avg_clv": avg_clv,
            "status": "ELIGIBLE" if eligible else "REVIEW",
            "submitted_at": datetime.now()
        }
        
        result = self.db.sharp_pass_applications.insert_one(doc)
        
        return {
            "application_id": str(result.inserted_id),
            "total_bets": total_bets,
            "win_rate": win_rate,
            "avg_clv": avg_clv,
            "eligible": eligible,
            "status": "ELIGIBLE" if eligible else "REVIEW"
        }
        
    async def approve_application(
        self,
        application_id: str,
        admin_id: str
    ):
        """Approve Sharp Pass application"""
        # Get application
        app = self.db.sharp_pass_applications.find_one({"_id": ObjectId(application_id)})
        
        if not app:
            raise ValueError("Application not found")
            
        # Update application status
        self.db.sharp_pass_applications.update_one(
            {"_id": ObjectId(application_id)},
            {"$set": {
                "status": "APPROVED",
                "approved_at": datetime.now(),
                "approved_by": admin_id
            }}
        )
        
        # Activate Sharp Pass for user
        self.db.users.update_one(
            {"_id": ObjectId(app["user_id"])},
            {"$set": {
                "sharp_pass_active": True,
                "sharp_pass_activated_at": datetime.now()
            }}
        )
        
        return {"status": "approved"}
    
    async def analyze_bet_history(self, bets: List[Dict]) -> Dict:
        """Analyze bet history from CSV"""
        total_bets = len(bets)
        profitable = sum(1 for bet in bets if bet.get('result', '').upper() == 'WIN')
        losing = sum(1 for bet in bets if bet.get('result', '').upper() == 'LOSS')
        push = sum(1 for bet in bets if bet.get('result', '').upper() == 'PUSH')
        
        # Calculate CLV edge (simplified)
        clv_edge = 0.0
        for bet in bets:
            if bet.get('closing_odds') and bet.get('entry_odds'):
                try:
                    closing = float(bet['closing_odds'])
                    entry = float(bet['entry_odds'])
                    clv_edge += ((closing - entry) / entry) * 100
                except:
                    pass
        
        clv_edge_percentage = (clv_edge / total_bets) if total_bets > 0 else 0.0
        
        return {
            'total_bets': total_bets,
            'profitable_bets': profitable,
            'losing_bets': losing,
            'push_bets': push,
            'clv_edge_percentage': clv_edge_percentage
        }
    
    async def create_application(
        self,
        user_id: str,
        csv_url: str,
        csv_filename: str,
        analysis: Dict,
        status: str
    ) -> Dict:
        """Create Sharp Pass application"""
        doc = {
            "user_id": user_id,
            "csv_url": csv_url,
            "csv_filename": csv_filename,
            "total_bets": analysis['total_bets'],
            "clv_edge_percentage": analysis['clv_edge_percentage'],
            "profitable_bets": analysis['profitable_bets'],
            "losing_bets": analysis['losing_bets'],
            "push_bets": analysis['push_bets'],
            "status": status,
            "submitted_at": datetime.now(),
            "reviewed_at": None,
            "reviewed_by": None
        }
        
        result = self.db.sharp_pass_applications.insert_one(doc)
        
        return {
            "application_id": str(result.inserted_id),
            **doc
        }
    
    async def update_user_sharp_pass_status(
        self,
        user_id: str,
        status: str,
        sharp_score: float,
        bet_count: int
    ):
        """Update user's Sharp Pass status"""
        self.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "sharp_pass_status": status,
                "sharp_pass_score": sharp_score,
                "sharp_pass_bet_count": bet_count,
                "sharp_pass_updated_at": datetime.now()
            }}
        )
    
    async def get_user_applications(self, user_id: str) -> List[Dict]:
        """Get all applications for a user"""
        apps = list(self.db.sharp_pass_applications.find({"user_id": user_id}).sort("submitted_at", -1))
        
        for app in apps:
            app['application_id'] = str(app.pop('_id'))
        
        return apps
    
    async def get_all_applications(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """Get all applications with filters"""
        query = {}
        if status:
            query['status'] = status
        
        apps = list(
            self.db.sharp_pass_applications
            .find(query)
            .sort("submitted_at", -1)
            .skip(offset)
            .limit(limit)
        )
        
        for app in apps:
            app['application_id'] = str(app.pop('_id'))
        
        return apps
    
    async def count_applications(self, status: Optional[str] = None) -> int:
        """Count applications"""
        query = {}
        if status:
            query['status'] = status
        
        return self.db.sharp_pass_applications.count_documents(query)
    
    async def get_application(self, application_id: str) -> Dict:
        """Get single application"""
        app = self.db.sharp_pass_applications.find_one({"_id": ObjectId(application_id)})
        
        if not app:
            raise ValueError("Application not found")
        
        app['application_id'] = str(app.pop('_id'))
        return app
    
    async def grant_wire_pro_access(self, user_id: str):
        """Grant Wire Pro access to user"""
        self.db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {
                "wire_pro_active": True,
                "wire_pro_activated_at": datetime.now()
            }}
        )
    
    async def reject_application(
        self,
        application_id: str,
        admin_id: str,
        rejection_reason: str
    ):
        """Reject Sharp Pass application"""
        self.db.sharp_pass_applications.update_one(
            {"_id": ObjectId(application_id)},
            {"$set": {
                "status": "REJECTED",
                "reviewed_at": datetime.now(),
                "reviewed_by": admin_id,
                "rejection_reason": rejection_reason
            }}
        )
