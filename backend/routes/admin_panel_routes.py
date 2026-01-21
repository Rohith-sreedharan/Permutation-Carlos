"""
Admin Panel Routes - Comprehensive Admin Dashboard
Customer management, activity logs, billing, and system monitoring
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from bson import ObjectId
import os
import stripe

from db.mongo import db
from middleware.auth import require_admin, get_current_user

router = APIRouter(prefix="/api/admin/panel", tags=["admin-panel"])

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


# ============================================================================
# MODELS
# ============================================================================

class AdminStats(BaseModel):
    """Dashboard statistics"""
    total_users: int
    active_subscriptions: int
    total_revenue_monthly: float
    total_predictions: int
    active_users_24h: int
    new_users_7d: int


class CustomerActivity(BaseModel):
    """Customer activity log entry"""
    timestamp: datetime
    user_id: str
    user_email: str
    action: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None


class BillingUpdate(BaseModel):
    """Billing settings update"""
    user_id: str
    action: str  # cancel, refund, update_tier
    reason: Optional[str] = None


# ============================================================================
# DASHBOARD STATISTICS
# ============================================================================

@router.get("/stats", response_model=AdminStats)
async def get_admin_stats(
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Get dashboard statistics
    
    Returns:
        - Total users
        - Active subscriptions
        - Revenue metrics
        - Activity metrics
    """
    try:
        # Count total users
        total_users = db.users.count_documents({})
        
        # Count active subscriptions
        active_subscriptions = db.users.count_documents({
            "tier": {"$in": ["elite", "sharps_room", "founder"]}
        })
        
        # Calculate 24h active users (users who logged in or made API calls)
        yesterday = datetime.now(timezone.utc) - timedelta(hours=24)
        active_users_24h = db.users.count_documents({
            "last_login": {"$gte": yesterday}
        })
        
        # New users in last 7 days
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        new_users_7d = db.users.count_documents({
            "created_at": {"$gte": week_ago}
        })
        
        # Total predictions
        total_predictions = db.published_predictions.count_documents({})
        
        # Calculate monthly revenue (placeholder - would integrate with Stripe)
        # For now, estimate based on active subscriptions
        tier_prices = {
            "elite": 99.0,
            "sharps_room": 49.0,
            "founder": 199.0
        }
        
        total_revenue_monthly = 0.0
        for tier, price in tier_prices.items():
            count = db.users.count_documents({"tier": tier})
            total_revenue_monthly += count * price
        
        return AdminStats(
            total_users=total_users,
            active_subscriptions=active_subscriptions,
            total_revenue_monthly=total_revenue_monthly,
            total_predictions=total_predictions,
            active_users_24h=active_users_24h,
            new_users_7d=new_users_7d
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


# ============================================================================
# CUSTOMER MANAGEMENT
# ============================================================================

@router.get("/customers")
async def get_customers(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    search: Optional[str] = None,
    tier: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Get list of customers with pagination and filtering
    """
    try:
        # Build query
        query = {}
        
        if search:
            query["$or"] = [
                {"email": {"$regex": search, "$options": "i"}},
                {"username": {"$regex": search, "$options": "i"}}
            ]
        
        if tier:
            query["tier"] = tier
        
        # Fetch customers
        customers_cursor = db.users.find(query).skip(skip).limit(limit).sort("created_at", -1)
        customers = []
        
        for user in customers_cursor:
            # Get subscription info
            stripe_customer_id = user.get("stripe_customer_id")
            subscription_status = None
            
            if stripe_customer_id:
                try:
                    subscriptions = stripe.Subscription.list(
                        customer=stripe_customer_id,
                        limit=1
                    )
                    if subscriptions.data:
                        subscription_status = subscriptions.data[0].status
                except:
                    pass
            
            customers.append({
                "id": str(user["_id"]),
                "email": user.get("email"),
                "username": user.get("username"),
                "tier": user.get("tier", "free"),
                "created_at": user.get("created_at"),
                "last_login": user.get("last_login"),
                "simulations_today": user.get("simulations_today", 0),
                "total_simulations": user.get("total_simulations", 0),
                "stripe_customer_id": stripe_customer_id,
                "subscription_status": subscription_status,
                "is_admin": user.get("is_admin", False),
                "two_factor_enabled": user.get("two_factor_enabled", False)
            })
        
        # Get total count for pagination
        total = db.users.count_documents(query)
        
        return {
            "customers": customers,
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch customers: {str(e)}")


@router.get("/customers/{user_id}")
async def get_customer_detail(
    user_id: str,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Get detailed information about a specific customer"""
    try:
        user = db.users.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="Customer not found")
        
        # Get activity logs
        activity_logs = list(db.activity_logs.find(
            {"user_id": user_id}
        ).sort("timestamp", -1).limit(50))
        
        # Get prediction history
        predictions = list(db.published_predictions.find(
            {"user_id": user_id}
        ).sort("created_at", -1).limit(20))
        
        # Get Stripe subscription details
        stripe_info = None
        if user.get("stripe_customer_id"):
            try:
                customer = stripe.Customer.retrieve(user["stripe_customer_id"])
                subscriptions = stripe.Subscription.list(
                    customer=user["stripe_customer_id"]
                )
                stripe_info = {
                    "customer": {
                        "id": customer.id,
                        "email": customer.email,
                        "created": customer.created
                    },
                    "subscriptions": [
                        {
                            "id": sub.id,
                            "status": sub.status,
                            "current_period_end": sub.current_period_end,  # type: ignore
                            "plan": sub.plan.id if hasattr(sub, 'plan') and sub.plan else None  # type: ignore
                        }
                        for sub in subscriptions.data
                    ]
                }
            except Exception as e:
                stripe_info = {"error": str(e)}
        
        return {
            "user": {
                "id": str(user["_id"]),
                "email": user.get("email"),
                "username": user.get("username"),
                "tier": user.get("tier"),
                "created_at": user.get("created_at"),
                "last_login": user.get("last_login"),
                "simulations_today": user.get("simulations_today", 0),
                "total_simulations": user.get("total_simulations", 0),
                "is_admin": user.get("is_admin", False)
            },
            "activity_logs": [
                {
                    "timestamp": log.get("timestamp"),
                    "action": log.get("action"),
                    "details": log.get("details", {})
                }
                for log in activity_logs
            ],
            "predictions": [
                {
                    "id": str(pred["_id"]),
                    "event_id": pred.get("event_id"),
                    "created_at": pred.get("created_at"),
                    "bet_type": pred.get("bet_type"),
                    "confidence": pred.get("confidence")
                }
                for pred in predictions
            ],
            "stripe_info": stripe_info
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch customer details: {str(e)}")


# ============================================================================
# ACTIVITY LOGS
# ============================================================================

@router.get("/activity-logs")
async def get_activity_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    action_type: Optional[str] = None,
    user_id: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """
    Get system activity logs with filtering
    """
    try:
        query = {}
        
        if action_type:
            query["action"] = action_type
        
        if user_id:
            query["user_id"] = user_id
        
        logs_cursor = db.activity_logs.find(query).skip(skip).limit(limit).sort("timestamp", -1)
        logs = []
        
        for log in logs_cursor:
            # Fetch user info
            user = None
            if log.get("user_id"):
                user = db.users.find_one({"_id": ObjectId(log["user_id"])})
            
            logs.append({
                "id": str(log["_id"]),
                "timestamp": log.get("timestamp"),
                "user_id": log.get("user_id"),
                "user_email": user.get("email") if user else None,
                "action": log.get("action"),
                "details": log.get("details", {}),
                "ip_address": log.get("ip_address")
            })
        
        total = db.activity_logs.count_documents(query)
        
        return {
            "logs": logs,
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch activity logs: {str(e)}")


# ============================================================================
# FRONTEND LOGS
# ============================================================================

@router.post("/frontend-logs")
async def receive_frontend_log(
    log_data: Dict[str, Any],
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user)
):
    """
    Receive logs from frontend (errors, warnings, info)
    """
    try:
        log_entry = {
            "timestamp": datetime.now(timezone.utc),
            "user_id": str(current_user["_id"]) if current_user else None,
            "user_email": current_user.get("email") if current_user else None,
            "level": log_data.get("level", "info"),
            "message": log_data.get("message"),
            "details": log_data.get("details", {}),
            "source": "frontend",
            "user_agent": log_data.get("userAgent"),
            "url": log_data.get("url")
        }
        
        db.frontend_logs.insert_one(log_entry)
        
        return {"status": "logged"}
        
    except Exception as e:
        # Don't fail if logging fails
        print(f"Failed to log frontend event: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/frontend-logs")
async def get_frontend_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    level: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Get frontend error logs"""
    try:
        query = {}
        
        if level:
            query["level"] = level
        
        logs_cursor = db.frontend_logs.find(query).skip(skip).limit(limit).sort("timestamp", -1)
        logs = list(logs_cursor)
        
        # Convert ObjectId to string
        for log in logs:
            log["_id"] = str(log["_id"])
        
        total = db.frontend_logs.count_documents(query)
        
        return {
            "logs": logs,
            "total": total,
            "skip": skip,
            "limit": limit
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch frontend logs: {str(e)}")


# ============================================================================
# BILLING MANAGEMENT
# ============================================================================

@router.post("/billing/cancel-subscription")
async def cancel_subscription(
    update: BillingUpdate,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Cancel a user's subscription"""
    try:
        user = db.users.find_one({"_id": ObjectId(update.user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        stripe_customer_id = user.get("stripe_customer_id")
        if not stripe_customer_id:
            raise HTTPException(status_code=400, detail="User has no Stripe subscription")
        
        # Cancel all active subscriptions
        subscriptions = stripe.Subscription.list(customer=stripe_customer_id, status="active")
        
        cancelled_subs = []
        for subscription in subscriptions.data:
            # Use modify to cancel subscription
            cancelled_sub = stripe.Subscription.modify(
                subscription.id,
                cancel_at_period_end=False
            )
            # Then delete/cancel it
            stripe.Subscription.delete(subscription.id)  # type: ignore
            cancelled_subs.append(subscription.id)
        
        # Update user tier
        db.users.update_one(
            {"_id": ObjectId(update.user_id)},
            {"$set": {"tier": "free"}}
        )
        
        # Log the action
        db.activity_logs.insert_one({
            "timestamp": datetime.now(timezone.utc),
            "user_id": update.user_id,
            "action": "subscription_cancelled_by_admin",
            "details": {
                "reason": update.reason,
                "cancelled_by": str(current_user["_id"]),
                "subscriptions": cancelled_subs
            }
        })
        
        return {
            "status": "success",
            "message": f"Cancelled {len(cancelled_subs)} subscription(s)",
            "subscriptions": cancelled_subs
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to cancel subscription: {str(e)}")


@router.post("/billing/refund")
async def issue_refund(
    user_id: str,
    charge_id: str,
    amount: Optional[int] = None,  # Amount in cents, None for full refund
    reason: Optional[str] = None,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Issue a refund for a charge"""
    try:
        refund_params: Dict[str, Any] = {
            "charge": charge_id
        }
        
        if amount is not None:
            refund_params["amount"] = amount
        
        if reason:
            refund_params["reason"] = reason
        
        refund = stripe.Refund.create(**refund_params)  # type: ignore
        
        # Log the action
        db.activity_logs.insert_one({
            "timestamp": datetime.now(timezone.utc),
            "user_id": user_id,
            "action": "refund_issued_by_admin",
            "details": {
                "refund_id": refund.id,
                "charge_id": charge_id,
                "amount": amount,
                "reason": reason,
                "issued_by": str(current_user["_id"])
            }
        })
        
        return {
            "status": "success",
            "refund": {
                "id": refund.id,
                "amount": refund.amount,
                "status": refund.status
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to issue refund: {str(e)}")


@router.get("/billing/revenue")
async def get_revenue_stats(
    period: str = Query("month", regex="^(day|week|month|year)$"),
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Get revenue statistics"""
    try:
        # Calculate date range
        now = datetime.now(timezone.utc)
        
        if period == "day":
            start_date = now - timedelta(days=1)
        elif period == "week":
            start_date = now - timedelta(weeks=1)
        elif period == "month":
            start_date = now - timedelta(days=30)
        else:  # year
            start_date = now - timedelta(days=365)
        
        # In production, this would query Stripe for actual charges
        # For now, estimate from active subscriptions
        
        tier_prices = {
            "elite": 99.0,
            "sharps_room": 49.0,
            "founder": 199.0
        }
        
        revenue_by_tier = {}
        total_revenue = 0.0
        
        for tier, price in tier_prices.items():
            count = db.users.count_documents({"tier": tier})
            revenue = count * price
            revenue_by_tier[tier] = {
                "subscribers": count,
                "revenue": revenue
            }
            total_revenue += revenue
        
        return {
            "period": period,
            "start_date": start_date,
            "end_date": now,
            "total_revenue": total_revenue,
            "by_tier": revenue_by_tier,
            "currency": "USD"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch revenue stats: {str(e)}")


# ============================================================================
# USER MANAGEMENT
# ============================================================================

@router.patch("/customers/{user_id}/tier")
async def update_user_tier(
    user_id: str,
    tier: str,
    current_user: Dict[str, Any] = Depends(require_admin)
):
    """Update a user's tier manually"""
    try:
        valid_tiers = ["free", "elite", "sharps_room", "founder"]
        if tier not in valid_tiers:
            raise HTTPException(status_code=400, detail=f"Invalid tier. Must be one of: {valid_tiers}")
        
        result = db.users.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"tier": tier}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Log the action
        db.activity_logs.insert_one({
            "timestamp": datetime.now(timezone.utc),
            "user_id": user_id,
            "action": "tier_updated_by_admin",
            "details": {
                "new_tier": tier,
                "updated_by": str(current_user["_id"])
            }
        })
        
        return {"status": "success", "tier": tier}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update tier: {str(e)}")
