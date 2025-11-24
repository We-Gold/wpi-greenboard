from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, text
from typing import List

from ..database import get_session
from ..models import Package, Carrier, Emission, PackageRead

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


@router.get("/students")
async def get_student_leaderboard(
    db: Session = Depends(get_session),
    major: str = Query(None, description="Filter by major/department")
    ):
    """
    Leaderboard of students ranked by total carbon emissions (kg CO2).
    Includes student name, total emissions, and their major/department.
    """
    major_filter = f"and d.department_name = '{major}'" if major else ""
    query = text(f"""
        SELECT 
            p.first_name,
            p.last_name,
            p.wpi_id,
            COALESCE(SUM(pk.total_emissions_kg), 0) AS total_emissions,
            d.department_name AS major
        FROM persons p
        LEFT JOIN packages pk ON p.wpi_id = pk.recipient_id
        LEFT JOIN departments d ON p.wpi_id = d.person_id
        WHERE p.is_student = TRUE {major_filter}
        GROUP BY p.wpi_id, d.department_name
        ORDER BY total_emissions DESC
    """)

    results = db.exec(query).all()

    leaderboard = []
    for rank, (first_name, last_name, wpi_id, emissions, major) in enumerate(results, start=1):
        leaderboard.append({
            "rank": rank,
            "name": f"{first_name} {last_name}",  # anonymized display
            "wpi_id": wpi_id,
            "carbon_emissions_kg": round(emissions or 0, 2),
            "major": major
        })

    return leaderboard

@router.get("/majors")
async def get_majors_leaderboard(db: Session = Depends(get_session)):
    """
    Leaderboard of majors ranked by total carbon emissions (kg CO2).
    Includes total emissions, and their related major/department.
    """
    query = text("""
        SELECT 
            d.department_name AS major,
            COALESCE(SUM(pk.total_emissions_kg), 0) AS total_emissions
        FROM persons p
        LEFT JOIN packages pk ON p.wpi_id = pk.recipient_id
        LEFT JOIN departments d ON p.wpi_id = d.person_id
        WHERE p.is_student = TRUE
        GROUP BY d.department_name
        ORDER BY total_emissions DESC
    """)

    results = db.exec(query).all()

    leaderboard = []
    for rank, (major, emissions) in enumerate(results, start=1):
        leaderboard.append({
            "rank": rank,
            "major": major,
            "carbon_emissions_kg": round(emissions or 0, 2), 
        })

    return leaderboard