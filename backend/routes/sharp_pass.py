"""
API Routes for Sharp Pass Verification

$999/mo verification system requiring:
- 500+ bets
- 2.0%+ CLV edge
"""
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel
import csv
import io

from ..middleware.auth import require_user, require_admin
from ..services.sharp_pass_verifier import SharpPassVerifier
from ..db.database import Database, get_database
from ..db.database import Database, get_database

router = APIRouter(prefix="/api/sharp-pass", tags=["sharp-pass"])


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class UploadCSVResponse(BaseModel):
    application_id: str
    total_bets: int
    profitable_bets: int
    losing_bets: int
    push_bets: int
    clv_edge_percentage: float
    
    # Requirements check
    meets_bet_count_requirement: bool
    meets_clv_requirement: bool
    
    # Status
    status: str  # PENDING, APPROVED, REJECTED
    message: str


class ApplicationResponse(BaseModel):
    application_id: str
    user_id: str
    
    # Analysis
    total_bets: int
    clv_edge_percentage: float
    
    # Requirements
    meets_bet_count_requirement: bool
    meets_clv_requirement: bool
    
    # Status
    status: str
    uploaded_at: datetime
    reviewed_at: Optional[datetime]
    rejection_reason: Optional[str]


class ApplicationListResponse(BaseModel):
    applications: List[ApplicationResponse]
    total: int


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/upload-csv", response_model=UploadCSVResponse)
async def upload_bet_history_csv(
    file: UploadFile = File(...),
    user = Depends(require_user),
    db: Database = Depends(get_database)
):
    """
    Upload bet history CSV for Sharp Pass verification
    
    CSV format:
    - date, sport, bet_type, bet_side, stake, odds, result, entry_price, closing_line
    
    Requirements:
    - 500+ bets
    - 2.0%+ CLV edge
    
    Access: All authenticated users
    """
    # Check if user already has Sharp Pass
    if user.sharp_pass_status == "APPROVED":
        raise HTTPException(status_code=400, detail="Already have Sharp Pass access")
    
    # Check if pending application exists
    if user.sharp_pass_status == "PENDING":
        raise HTTPException(status_code=400, detail="Application already pending review")
    
    # Read CSV
    contents = await file.read()
    csv_text = contents.decode('utf-8')
    
    try:
        # Parse CSV
        csv_reader = csv.DictReader(io.StringIO(csv_text))
        bets = list(csv_reader)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {str(e)}")
    
    # Verify CSV has required columns
    required_columns = ['date', 'sport', 'bet_type', 'bet_side', 'stake', 'odds', 'result', 'entry_price', 'closing_line']
    if not all(col in bets[0].keys() for col in required_columns):
        raise HTTPException(
            status_code=400,
            detail=f"CSV must contain columns: {', '.join(required_columns)}"
        )
    
    # Analyze bet history
    verifier = SharpPassVerifier(db)
    analysis = await verifier.analyze_bet_history(bets)
    
    # Check requirements
    meets_bet_count = analysis['total_bets'] >= 500
    meets_clv = analysis['clv_edge_percentage'] >= 2.0
    
    # Determine status
    if meets_bet_count and meets_clv:
        status = "PENDING"  # Requires admin review
        message = "Application meets requirements and is pending review"
    else:
        status = "REJECTED"
        reasons = []
        if not meets_bet_count:
            reasons.append(f"Only {analysis['total_bets']} bets (need 500+)")
        if not meets_clv:
            reasons.append(f"Only {analysis['clv_edge_percentage']:.2f}% CLV edge (need 2.0%+)")
        message = "Application rejected: " + ", ".join(reasons)
    
    # Save application
    application = await verifier.create_application(
        user_id=user.user_id,
        csv_url=f"s3://beatvegas-sharp-pass/{user.user_id}/{file.filename or 'upload.csv'}",
        csv_filename=file.filename or "upload.csv",
        analysis=analysis,
        status=status
    )
    
    # Update user status
    await verifier.update_user_sharp_pass_status(
        user_id=user.user_id,
        status=status,
        sharp_score=analysis['clv_edge_percentage'],
        bet_count=analysis['total_bets']
    )
    
    return UploadCSVResponse(
        application_id=application['application_id'],
        total_bets=analysis['total_bets'],
        profitable_bets=analysis['profitable_bets'],
        losing_bets=analysis['losing_bets'],
        push_bets=analysis['push_bets'],
        clv_edge_percentage=analysis['clv_edge_percentage'],
        meets_bet_count_requirement=meets_bet_count,
        meets_clv_requirement=meets_clv,
        status=status,
        message=message
    )


@router.get("/applications/me", response_model=List[ApplicationResponse])
async def get_my_applications(
    user = Depends(require_user),
    db: Database = Depends(get_database)
):
    """
    Get my Sharp Pass applications
    
    Access: All authenticated users
    """
    verifier = SharpPassVerifier(db)
    applications = await verifier.get_user_applications(user.user_id)
    
    return [ApplicationResponse(**app) for app in applications]


@router.get("/applications", response_model=ApplicationListResponse)
async def get_all_applications(
    status: Optional[str] = None,  # PENDING, APPROVED, REJECTED
    limit: int = 50,
    offset: int = 0,
    admin = Depends(require_admin),
    db: Database = Depends(get_database)
):
    """
    Get all Sharp Pass applications (admin only)
    
    Access: Admins only
    """
    verifier = SharpPassVerifier(db)
    applications = await verifier.get_all_applications(
        status=status,
        limit=limit,
        offset=offset
    )
    
    total = await verifier.count_applications(status=status)
    
    return ApplicationListResponse(
        applications=[ApplicationResponse(**app) for app in applications],
        total=total
    )


@router.post("/applications/{application_id}/approve")
async def approve_application(
    application_id: str,
    admin = Depends(require_admin),
    db: Database = Depends(get_database)
):
    """
    Approve Sharp Pass application (admin only)
    
    Grants Sharp Pass access and Wire Pro access
    
    Access: Admins only
    """
    verifier = SharpPassVerifier(db)
    
    # Approve application
    await verifier.approve_application(
        application_id=application_id,
        admin_id=admin.user_id
    )
    
    # Get application to get user_id
    application = await verifier.get_application(application_id)
    
    # Update user status
    await verifier.update_user_sharp_pass_status(
        user_id=application['user_id'],
        status="APPROVED",
        sharp_score=application['clv_edge_percentage'],
        bet_count=application['total_bets']
    )
    
    # Grant Wire Pro access
    await verifier.grant_wire_pro_access(application['user_id'])
    
    # Send notification
    # TODO: Send email/Telegram notification
    
    return {"success": True, "message": "Application approved"}


@router.post("/applications/{application_id}/reject")
async def reject_application(
    application_id: str,
    reason: str,
    admin = Depends(require_admin),
    db: Database = Depends(get_database)
):
    """
    Reject Sharp Pass application (admin only)
    
    Access: Admins only
    """
    verifier = SharpPassVerifier(db)
    
    # Reject application
    await verifier.reject_application(
        application_id=application_id,
        admin_id=admin.user_id,
        rejection_reason=reason
    )
    
    # Get application to get user_id
    application = await verifier.get_application(application_id)
    
    # Update user status
    await verifier.update_user_sharp_pass_status(
        user_id=application['user_id'],
        status="REJECTED",
        sharp_score=application['clv_edge_percentage'],
        bet_count=application['total_bets']
    )
    
    # Send notification
    # TODO: Send email/Telegram notification
    
    return {"success": True, "message": "Application rejected"}


@router.get("/requirements")
async def get_requirements():
    """
    Get Sharp Pass requirements
    
    Public endpoint
    """
    return {
        "minimum_bets": 500,
        "minimum_clv_edge": 2.0,
        "monthly_price": 999.00,
        "benefits": [
            "Truth Mode access (strict edge filters)",
            "Wire Pro community access",
            "Priority signal delivery",
            "Advanced analytics",
            "Telegram DM sequences",
            "CLV tracking dashboard"
        ]
    }


@router.get("/status")
async def get_sharp_pass_status(
    user = Depends(require_user)
):
    """
    Get my Sharp Pass status
    
    Access: All authenticated users
    """
    return {
        "sharp_pass_status": user.sharp_pass_status,
        "sharp_score": user.sharp_pass_score,
        "bet_count": user.sharp_pass_bet_count,
        "wire_pro_access": user.wire_pro_access,
        "subscription_active": user.subscription_tier != "FREE"
    }
