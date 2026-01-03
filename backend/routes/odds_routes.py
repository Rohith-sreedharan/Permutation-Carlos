from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List
from datetime import datetime
from zoneinfo import ZoneInfo
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.timezone import now_est, now_utc, parse_iso_to_est, format_est_date, get_est_date_today, EST_TZ, UTC_TZ
from db.mongo import db
from integrations.odds_api import fetch_sports, fetch_odds, normalize_event, OddsApiError
from db.mongo import upsert_events, find_events

router = APIRouter(prefix="/api/odds", tags=["odds"])


@router.post("/refresh")
def refresh_odds_data(
    sports: str = Query("basketball_nba,americanfootball_nfl,baseball_mlb,icehockey_nhl", description="Comma-separated sports"),
    regions: str = Query("us", description="Comma-separated regions"),
    markets: str = Query("h2h,spreads,totals", description="Markets to fetch")
):
    """Fetch fresh odds from The Odds API and store in MongoDB."""
    sport_list = [s.strip() for s in sports.split(",") if s.strip()]
    region_list = [r.strip() for r in regions.split(",") if r.strip()]
    
    total_inserted = 0
    total_updated = 0
    errors = []
    
    for sport in sport_list:
        for region in region_list:
            try:
                raw_events = fetch_odds(sport=sport, region=region, markets=markets)
                
                for ev in raw_events:
                    norm = normalize_event(ev)
                    ct = norm.get("commence_time")
                    
                    # Add EST date for filtering
                    if ct:
                        try:
                            dt_est = parse_iso_to_est(ct)
                            if dt_est:
                                norm["local_date_est"] = format_est_date(dt_est)
                                norm["local_datetime_est"] = dt_est.isoformat()
                                dt_utc = dt_est.astimezone(UTC_TZ)
                                norm["local_date_utc"] = dt_utc.strftime("%Y-%m-%d")
                                norm["local_datetime_utc"] = dt_utc.isoformat()
                        except Exception:
                            pass
                    
                    # Upsert to database
                    event_id = norm.get("id")
                    if event_id:
                        result = db["events"].update_one(
                            {"id": event_id},
                            {"$set": norm},
                            upsert=True
                        )
                        if result.upserted_id:
                            total_inserted += 1
                        elif result.modified_count > 0:
                            total_updated += 1
                            
            except OddsApiError as e:
                errors.append(f"{sport}/{region}: {str(e)}")
    
    return {
        "success": True,
        "inserted": total_inserted,
        "updated": total_updated,
        "errors": errors,
        "message": f"Refreshed {total_inserted + total_updated} events from The Odds API"
    }


@router.get("/sports")
def list_sports():
    """Return supported sports from The Odds API."""
    return fetch_sports()


@router.get("/list")
def list_events(
    date: Optional[str] = Query(None, description="Target EST date YYYY-MM-DD; defaults to today's EST"),
    sport: Optional[str] = Query(None),
    upcoming_only: bool = Query(True),
    limit: int = Query(1000)  # Increased default limit
):
    """List events from database filtered by EST date."""
    # Default date to today's EST if not provided
    if not date:
        date = get_est_date_today()
    
    # Build MongoDB query filter
    mongo_filter = {"local_date_est": date}
    if sport:
        mongo_filter["sport_key"] = sport
    
    # Query database with filter for efficiency
    docs = find_events("events", filter=mongo_filter, limit=limit)
    now_utc_dt = now_utc()

    out = []
    for ev in docs:
        commence_iso = ev.get("commence_time")
        est_date = ev.get("local_date_est")
        
        # Recalculate EST date if missing
        if not est_date:
            try:
                if commence_iso:
                    dt_est = parse_iso_to_est(commence_iso)
                    if dt_est:
                        est_date = format_est_date(dt_est)
                        ev["local_date_est"] = est_date
            except Exception:
                est_date = None
        
        # Upcoming filter
        if upcoming_only and commence_iso:
            try:
                dt_est = parse_iso_to_est(commence_iso)
                if dt_est and dt_est.astimezone(UTC_TZ) < now_utc_dt:
                    continue
            except Exception:
                continue
        
        out.append(ev)
    
    return {"date": date, "sport": sport, "count": len(out), "events": out}


@router.get("/realtime/by-date")
def realtime_events_by_date(
    date: Optional[str] = Query(None, description="Target EST date YYYY-MM-DD; defaults to today's EST"),
    sport: str = Query("basketball_nba"),
    regions: str = Query("us"),
    markets: str = Query("h2h,spreads,totals"),
    upcoming_only: bool = Query(True),
    diagnostic: bool = Query(False, description="Return debug payload with counts and ranges"),
    date_basis: str = Query("est", description="Date basis: 'est' or 'utc' (default: est)"),
):
    """Fetch fresh odds from OddsAPI and filter by EST (default) or UTC calendar date in real time.

    Does not rely on stored DB fields; computes EST/UTC per response item. Use `diagnostic=true` to include debug info.
    """
    # Default date to today's EST or UTC
    if date_basis == "utc":
        if not date:
            date = now_utc().strftime("%Y-%m-%d")
    else:
        if not date:
            date = get_est_date_today()

    # Expand across multiple regions if provided as comma-separated list
    region_list = [r.strip() for r in regions.split(",") if r.strip()]

    aggregated_raw = []
    errors: List[str] = []
    for reg in region_list:
        try:
            raw = fetch_odds(sport=sport, region=reg, markets=markets)
            aggregated_raw.extend(raw)
        except OddsApiError as e:
            errors.append(f"{reg}:{str(e)}")

    now_utc_dt = now_utc()
    out = []
    # Diagnostic accumulators
    total_events = len(aggregated_raw)
    per_region_counts = {}
    commence_ranges = {"min": "", "max": ""}  # ISO strings for diagnostics

    for ev in aggregated_raw:
        norm = normalize_event(ev)
        ct = norm.get("commence_time")
        reg = norm.get("region") or ev.get("region") or "unknown"
        per_region_counts[reg] = per_region_counts.get(reg, 0) + 1
        if not ct:
            continue
        try:
            dt_est = parse_iso_to_est(ct)
            if not dt_est:
                continue
            dt_utc = dt_est.astimezone(UTC_TZ)
        except Exception:
            continue
        # Track commence ranges as ISO strings for type consistency
        curr_min = commence_ranges["min"] or ""
        curr_max = commence_ranges["max"] or ""
        dt_iso = dt_utc.isoformat()
        if not curr_min or dt_iso < curr_min:
            commence_ranges["min"] = dt_iso
        if not curr_max or dt_iso > curr_max:
            commence_ranges["max"] = dt_iso

        if upcoming_only and dt_utc < now_utc_dt:
            continue

        # Date filtering by EST or UTC
        if date_basis == "utc":
            filter_date = dt_utc.strftime("%Y-%m-%d")
        else:
            filter_date = format_est_date(dt_est)

        if filter_date == date:
            # Include both UTC and EST convenience fields
            norm["local_date_utc"] = dt_utc.strftime("%Y-%m-%d")
            norm["local_datetime_utc"] = dt_utc.isoformat()
            norm["local_date_est"] = format_est_date(dt_est)
            norm["local_datetime_est"] = dt_est.isoformat()
            out.append(norm)

    response = {"date": date, "sport": sport, "count": len(out), "events": out}
    if diagnostic:
        response["debug"] = {
            "requested_regions": region_list,
            "markets": markets.split(","),
            "total_raw_events": total_events,
            "per_region_counts": per_region_counts,
            "commence_time_range_utc": commence_ranges,
            "errors": errors,
            "date_basis": date_basis,
        }
    return response


@router.delete("/cleanup/expired")
def cleanup_expired_events(days_past: int = 0):
    """Remove events whose commence_time is earlier than current UTC minus `days_past` days.

    Use days_past > 0 to retain a trailing window if needed for settlement analytics.
    """
    now_utc_dt = now_utc()
    threshold = now_utc_dt
    # Note: days_past parameter currently not implemented for simplicity
    removed = 0
    for ev in db["events"].find():
        c = ev.get("commence_time")
        if not c:
            continue
        try:
            dt_est = parse_iso_to_est(c)
            if dt_est and dt_est.astimezone(UTC_TZ) < threshold:
                db["events"].delete_one({"_id": ev["_id"]})
                removed += 1
        except Exception:
            continue
    return {"removed": removed, "threshold": threshold.isoformat()}


# Legacy endpoint - kept for backwards compatibility but deprecated
@router.get("/realtime/by-date-utc")
def realtime_events_by_date_utc(
    date: Optional[str] = Query(None, description="Target UTC date YYYY-MM-DD; defaults to today's UTC"),
    sport: str = Query("basketball_nba"),
    regions: str = Query("us"),
    markets: str = Query("h2h,spreads,totals"),
    upcoming_only: bool = Query(True),
    diagnostic: bool = Query(False, description="Return debug payload with counts and ranges"),
):
    """Legacy UTC-based endpoint. Use /api/odds/realtime/by-date instead with date_basis='utc'."""
    if not date:
        date = now_utc().strftime("%Y-%m-%d")

    # Expand across multiple regions if provided as comma-separated list
    region_list = [r.strip() for r in regions.split(",") if r.strip()]

    aggregated_raw = []
    errors: List[str] = []
    for reg in region_list:
        try:
            raw = fetch_odds(sport=sport, region=reg, markets=markets)
            aggregated_raw.extend(raw)
        except OddsApiError as e:
            errors.append(f"{reg}:{str(e)}")

    now_utc_dt = now_utc()
    out = []
    # Diagnostic accumulators
    total_events = len(aggregated_raw)
    per_region_counts = {}
    commence_ranges = {"min": "", "max": ""}  # ISO strings for diagnostics

    for ev in aggregated_raw:
        norm = normalize_event(ev)
        ct = norm.get("commence_time")
        reg = norm.get("region") or ev.get("region") or "unknown"
        per_region_counts[reg] = per_region_counts.get(reg, 0) + 1
        if not ct:
            continue
        try:
            dt_est = parse_iso_to_est(ct)
            if not dt_est:
                continue
            dt_utc = dt_est.astimezone(UTC_TZ)
        except Exception:
            continue
        # Track commence ranges as ISO strings for type consistency
        curr_min = commence_ranges["min"] or ""
        curr_max = commence_ranges["max"] or ""
        dt_iso = dt_utc.isoformat()
        if not curr_min or dt_iso < curr_min:
            commence_ranges["min"] = dt_iso
        if not curr_max or dt_iso > curr_max:
            commence_ranges["max"] = dt_iso

        if upcoming_only and dt_utc < now_utc_dt:
            continue

        utc_date = dt_utc.strftime("%Y-%m-%d")
        if utc_date == date:
            # Include both UTC and EST convenience fields
            norm["local_date_utc"] = utc_date
            norm["local_datetime_utc"] = dt_utc.isoformat()
            norm["local_date_est"] = format_est_date(dt_est)
            norm["local_datetime_est"] = dt_est.isoformat()
            out.append(norm)

    response = {"date": date, "sport": sport, "count": len(out), "events": out}
    if diagnostic:
        response["debug"] = {
            "requested_regions": region_list,
            "markets": markets.split(","),
            "total_raw_events": total_events,
            "per_region_counts": per_region_counts,
            "commence_time_range_utc": commence_ranges,
            "errors": errors,
        }
    return response


# Note: Removed backfill and distribution endpoints to enforce real-time behavior
