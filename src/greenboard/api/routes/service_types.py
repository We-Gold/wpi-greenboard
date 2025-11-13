from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, text
from typing import Optional
from datetime import date

from ..database import get_session

router = APIRouter(prefix="/service-types", tags=["service_types"])


@router.get("/by-major")
async def get_service_type_stats_by_major(
    db: Session = Depends(get_session),
    start_date: Optional[date] = Query(
        None,
        description="Filter packages shipped on or after this date (YYYY-MM-DD)"
    ),
    end_date: Optional[date] = Query(
        None,
        description="Filter packages shipped on or before this date (YYYY-MM-DD)"
    ),
    students_only: bool = Query(
        True,
        description="If true, only include packages where the recipient is a student"
    )
):
    """
    Service-type statistics grouped by major/department.

    Each row combines:
    - major (department_name)
    - service_type
    - package_count
    - percent_of_major_packages (within that major)
    - total_emissions_kg
    - avg_emissions_per_package_kg
    """

    #Build dynamic filters
    date_filter = ""
    params = {}

    if start_date:
        date_filter += "AND pk.date_shipped >= :start_date "
        params["start_date"] = start_date

    if end_date:
        date_filter += "AND pk.date_shipped <= :end_date "
        params["end_date"] = end_date

    student_filter = ""
    if students_only:
        student_filter = "AND p.is_student = TRUE "

    query = text(f"""
        SELECT
            d.department_name AS major,
            COALESCE(pk.service_type, 'Unknown') AS service_type,
            COUNT(*) AS package_count,
            -- percentage of packages within this major using this service type
            ROUND(
                100.0 * COUNT(*) /
                NULLIF(SUM(COUNT(*)) OVER (PARTITION BY d.department_name), 0),
                2
            ) AS percent_of_major_packages,
            COALESCE(SUM(pk.total_emissions_kg), 0) AS total_emissions_kg,
            COALESCE(AVG(pk.total_emissions_kg), 0) AS avg_emissions_per_package_kg
        FROM packages pk
        JOIN persons p ON pk.recipient_id = p.wpi_id
        JOIN departments d ON p.wpi_id = d.person_id
        WHERE 1=1
        {student_filter}
        {date_filter}
        GROUP BY
            d.department_name,
            COALESCE(pk.service_type, 'Unknown')
        ORDER BY
            d.department_name ASC,
            package_count DESC
    """)

    results = db.exec(query, params).all()

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No package data available for the given filters"
        )

    rows = []
    for (
        major,
        service_type,
        package_count,
        percent_of_major_packages,
        total_emissions_kg,
        avg_emissions_per_package_kg,
    ) in results:
        rows.append({
            "major": major,
            "service_type": service_type,
            "package_count": package_count,
            "percent_of_major_packages": float(percent_of_major_packages)
                if percent_of_major_packages is not None else 0.0,
            "total_emissions_kg": round(total_emissions_kg, 2),
            "avg_emissions_per_package_kg": round(avg_emissions_per_package_kg, 2),
        })

    #Output: one row = one (major, service_type) combo
    return {
        "group_by": "major",
        "students_only": students_only,
        "filters": {
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
        },
        "row_count": len(rows),
        "rows": rows,
    }


@router.get("/by-class-year")
async def get_service_type_stats_by_class_year(
    db: Session = Depends(get_session),
    start_date: Optional[date] = Query(
        None,
        description="Filter packages shipped on or after this date (YYYY-MM-DD)"
    ),
    end_date: Optional[date] = Query(
        None,
        description="Filter packages shipped on or before this date (YYYY-MM-DD)"
    ),
    students_only: bool = Query(
        True,
        description="If true, only include packages where the recipient is a student"
    )
):
    """
    Service-type statistics grouped by class year bucket.

    class_year is stored as INT:

    We bucket as:
        1 => 'Year 1'
        2 => 'Year 2'
        3 => 'Year 3'
        4 => 'Year 4'
        >4 => 'Graduate'
        NULL/other => 'Unknown'

    Each row combines:
    - class_year_group
    - service_type
    - package_count
    - percent_of_year_packages (within that year group)
    - total_emissions_kg
    - avg_emissions_per_package_kg
    """

    date_filter = ""
    params = {}

    if start_date:
        date_filter += "AND pk.date_shipped >= :start_date "
        params["start_date"] = start_date

    if end_date:
        date_filter += "AND pk.date_shipped <= :end_date "
        params["end_date"] = end_date

    student_filter = ""
    if students_only:
        student_filter = "AND p.is_student = TRUE "

    query = text(f"""
        WITH classified AS (
            SELECT
                pk.*,
                p.class_year,
                CASE
                    WHEN p.class_year IS NULL THEN 'Unknown'
                    WHEN p.class_year BETWEEN 1 AND 4
                        THEN 'Year ' || p.class_year::text
                    WHEN p.class_year > 4 THEN 'Graduate'
                    ELSE 'Unknown'
                END AS class_year_group,
                p.wpi_id
            FROM packages pk
            JOIN persons p ON pk.recipient_id = p.wpi_id
            WHERE 1=1
            {student_filter}
            {date_filter}
        )
        SELECT
            class_year_group,
            COALESCE(service_type, 'Unknown') AS service_type,
            COUNT(*) AS package_count,
            ROUND(
                100.0 * COUNT(*) /
                NULLIF(SUM(COUNT(*)) OVER (PARTITION BY class_year_group), 0),
                2
            ) AS percent_of_year_packages,
            COALESCE(SUM(total_emissions_kg), 0) AS total_emissions_kg,
            COALESCE(AVG(total_emissions_kg), 0) AS avg_emissions_per_package_kg
        FROM classified
        GROUP BY
            class_year_group,
            COALESCE(service_type, 'Unknown')
        ORDER BY
            class_year_group,
            package_count DESC
    """)

    results = db.exec(query, params).all()

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No package data available for the given filters"
        )

    rows = []
    for (
        class_year_group,
        service_type,
        package_count,
        percent_of_year_packages,
        total_emissions_kg,
        avg_emissions_per_package_kg,
    ) in results:
        rows.append({
            "class_year_group": class_year_group,
            "service_type": service_type,
            "package_count": package_count,
            "percent_of_year_packages": float(percent_of_year_packages)
                if percent_of_year_packages is not None else 0.0,
            "total_emissions_kg": round(total_emissions_kg, 2),
            "avg_emissions_per_package_kg": round(avg_emissions_per_package_kg, 2),
        })

    return {
        "group_by": "class_year",
        "students_only": students_only,
        "filters": {
            "start_date": str(start_date) if start_date else None,
            "end_date": str(end_date) if end_date else None,
        },
        "row_count": len(rows),
        "rows": rows,
    }
