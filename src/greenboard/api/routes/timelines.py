from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, text
from typing import Optional
from datetime import date

from ..database import get_session
from ..models import Package, Carrier, Emission

router = APIRouter(prefix="/timeline", tags=["timeline"])


@router.get("/majors/list") # Incase we want dropdown of majors in the frontend 
async def get_available_majors(db: Session = Depends(get_session)):
    """
    Get list of all available majors/departments for dropdown selection.
    Returns unique department names from the departments table.
    """
    query = text("""
        SELECT DISTINCT d.department_name
        FROM departments d
        ORDER BY d.department_name ASC
    """)
    
    results = db.exec(query).all()
    
    majors = [major[0] for major in results if major[0]]  # Filter out any NULL values
    
    return {
        "majors": majors,
        "count": len(majors)
    }


@router.get("/person/{wpi_id}")
async def get_person_emissions_timeline(
    wpi_id: str,
    db: Session = Depends(get_session),
    start_date: Optional[date] = Query(None, description="Start date for timeline (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date for timeline (YYYY-MM-DD)"),
    interval: str = Query("month", description="Grouping interval: day, week, month, year")
):
    """
    Timeline of carbon emissions for a specific person.
    Returns emissions grouped by the specified time interval.
    """
    # Validate interval
    valid_intervals = ["day", "week", "month", "year"]
    if interval not in valid_intervals:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid interval. Must be one of: {', '.join(valid_intervals)}"
        )
    
    # Build date filter
    date_filter = ""
    if start_date:
        date_filter += f"AND pk.date_shipped >= '{start_date}' "
    if end_date:
        date_filter += f"AND pk.date_shipped <= '{end_date}' "
    
    # Determine date truncation based on interval
    date_trunc_map = {
        "day": "DATE(pk.date_shipped)",
        "week": "DATE_TRUNC('week', pk.date_shipped)::date",
        "month": "DATE_TRUNC('month', pk.date_shipped)::date",
        "year": "DATE_TRUNC('year', pk.date_shipped)::date"
    }
    
    query = text(f"""
        SELECT 
            {date_trunc_map[interval]} AS period,
            COUNT(pk.package_id) AS package_count,
            COALESCE(SUM(pk.total_emissions_kg), 0) AS total_emissions,
            COALESCE(AVG(pk.total_emissions_kg), 0) AS avg_emissions_per_package,
            COALESCE(SUM(pk.equivalent_trees_planted), 0) AS total_trees_planted,
            COALESCE(SUM(pk.equivalent_miles_driven), 0) AS total_miles_driven
        FROM packages pk
        JOIN persons p ON pk.recipient_id = p.wpi_id
        WHERE p.wpi_id = '{wpi_id}'
        {date_filter}
        GROUP BY period
        ORDER BY period ASC
    """)
    
    results = db.exec(query).all()
    
    if not results:
        raise HTTPException(status_code=404, detail="Person not found or no package data available")
    
    timeline = []
    for period, package_count, total_emissions, avg_emissions, total_trees_planted, total_miles_driven in results:
        timeline.append({
            "period": str(period),
            "package_count": package_count,
            "total_emissions_kg": round(total_emissions, 2),
            "avg_emissions_per_package_kg": round(avg_emissions, 2),
            "total_trees_planted": round(total_trees_planted, 2),
            "total_miles_driven": round(total_miles_driven, 2)
        })
    
    return {
        "wpi_id": wpi_id,
        "interval": interval,
        "timeline": timeline
    }


@router.get("/major")
async def get_major_emissions_timeline(
    major_name: str = Query(..., description="Major/department name"),
    db: Session = Depends(get_session),
    start_date: Optional[date] = Query(None, description="Start date for timeline (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date for timeline (YYYY-MM-DD)"),
    interval: str = Query("month", description="Grouping interval: day, week, month, year")
):
    """
    Timeline of carbon emissions for a specific major/department.
    Returns emissions grouped by the specified time interval.
    """
    # Validate interval
    valid_intervals = ["day", "week", "month", "year"]
    if interval not in valid_intervals:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid interval. Must be one of: {', '.join(valid_intervals)}"
        )
    
    # Build date filter
    date_filter = ""
    if start_date:
        date_filter += f"AND pk.date_shipped >= '{start_date}' "
    if end_date:
        date_filter += f"AND pk.date_shipped <= '{end_date}' "
    
    # Determine date truncation based on interval
    date_trunc_map = {
        "day": "DATE(pk.date_shipped)",
        "week": "DATE_TRUNC('week', pk.date_shipped)::date",
        "month": "DATE_TRUNC('month', pk.date_shipped)::date",
        "year": "DATE_TRUNC('year', pk.date_shipped)::date"
    }
    
    query = text(f"""
        SELECT 
            {date_trunc_map[interval]} AS period,
            COUNT(pk.package_id) AS package_count,
            COUNT(DISTINCT p.wpi_id) AS unique_students,
            COALESCE(SUM(pk.total_emissions_kg), 0) AS total_emissions,
            COALESCE(AVG(pk.total_emissions_kg), 0) AS avg_emissions_per_package,
            COALESCE(SUM(pk.equivalent_trees_planted), 0) AS total_trees_planted,
            COALESCE(SUM(pk.equivalent_miles_driven), 0) AS total_miles_driven
        FROM packages pk
        JOIN persons p ON pk.recipient_id = p.wpi_id
        JOIN departments d ON p.wpi_id = d.person_id
        WHERE d.department_name = '{major_name}'
        AND p.is_student = TRUE
        {date_filter}
        GROUP BY period
        ORDER BY period ASC
    """)
    
    results = db.exec(query).all()
    
    if not results:
        raise HTTPException(status_code=404, detail="Major/department not found or no package data available")
    
    timeline = []
    for period, package_count, unique_students, total_emissions, avg_emissions, total_trees_planted, total_miles_driven in results:
        timeline.append({
            "period": str(period),
            "package_count": package_count,
            "unique_students": unique_students,
            "total_emissions_kg": round(total_emissions, 2),
            "avg_emissions_per_package_kg": round(avg_emissions, 2),
            "total_trees_planted": round(total_trees_planted, 2),
            "total_miles_driven": round(total_miles_driven, 2)
        })
    
    return {
        "major": major_name,
        "interval": interval,
        "timeline": timeline
    }


@router.get("/all")
async def get_all_emissions_timeline(
    db: Session = Depends(get_session),
    start_date: Optional[date] = Query(None, description="Start date for timeline (YYYY-MM-DD)"),
    end_date: Optional[date] = Query(None, description="End date for timeline (YYYY-MM-DD)"),
    interval: str = Query("month", description="Grouping interval: day, week, month, year"),
    students_only: bool = Query(False, description="Filter to students only")
):
    """
    Timeline of carbon emissions for all people.
    Returns emissions grouped by the specified time interval.
    """
    # Validate interval
    valid_intervals = ["day", "week", "month", "year"]
    if interval not in valid_intervals:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid interval. Must be one of: {', '.join(valid_intervals)}"
        )
    
    # Build date filter
    date_filter = ""
    if start_date:
        date_filter += f"AND pk.date_shipped >= '{start_date}' "
    if end_date:
        date_filter += f"AND pk.date_shipped <= '{end_date}' "
    
    # Build student filter
    student_filter = "AND p.is_student = TRUE" if students_only else ""
    
    # Determine date truncation based on interval
    date_trunc_map = {
        "day": "DATE(pk.date_shipped)",
        "week": "DATE_TRUNC('week', pk.date_shipped)::date",
        "month": "DATE_TRUNC('month', pk.date_shipped)::date",
        "year": "DATE_TRUNC('year', pk.date_shipped)::date"
    }
    
    query = text(f"""
        SELECT 
            {date_trunc_map[interval]} AS period,
            COUNT(pk.package_id) AS package_count,
            COUNT(DISTINCT pk.recipient_id) AS unique_recipients,
            COALESCE(SUM(pk.total_emissions_kg), 0) AS total_emissions,
            COALESCE(AVG(pk.total_emissions_kg), 0) AS avg_emissions_per_package,
            COALESCE(SUM(pk.distance_traveled), 0) AS total_distance_km,
            COALESCE(SUM(pk.equivalent_trees_planted), 0) AS total_trees_planted,
            COALESCE(SUM(pk.equivalent_miles_driven), 0) AS total_miles_driven
        FROM packages pk
        LEFT JOIN persons p ON pk.recipient_id = p.wpi_id
        WHERE 1=1
        {student_filter}
        {date_filter}
        GROUP BY period
        ORDER BY period ASC
    """)
    
    results = db.exec(query).all()
    
    timeline = []
    for period, package_count, unique_recipients, total_emissions, avg_emissions, total_distance, total_trees_planted, total_miles_driven in results:
        timeline.append({
            "period": str(period),
            "package_count": package_count,
            "unique_recipients": unique_recipients,
            "total_emissions_kg": round(total_emissions, 2),
            "avg_emissions_per_package_kg": round(avg_emissions, 2),
            "total_distance_km": round(total_distance, 2),
            "total_trees_planted": round(total_trees_planted, 2),
            "total_miles_driven": round(total_miles_driven, 2)
        })
    
    return {
        "interval": interval,
        "students_only": students_only,
        "total_periods": len(timeline),
        "timeline": timeline
    }