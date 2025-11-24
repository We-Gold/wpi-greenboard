from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, text
from typing import Optional
from datetime import date

from ..database import get_session

router = APIRouter(prefix="/service-types", tags=["service_types"])

@router.get("/overall")
async def get_service_type_stats_overall(
    db: Session = Depends(get_session),
):
    """
    Service-type statistics for all students (no date filter).

    Each row combines:
    - service_type
    - package_count
    - percent_of_all_packages (share of all student packages)
    - total_emissions_kg
    - avg_emissions_per_package_kg
    """

    query = text("""
        WITH base AS (
            SELECT
                COALESCE(pk.service_type, 'Unknown') AS service_type,
                COUNT(*) AS package_count,
                COALESCE(SUM(pk.total_emissions_kg), 0) AS total_emissions_kg,
                COALESCE(AVG(pk.total_emissions_kg), 0) AS avg_emissions_per_package_kg
            FROM packages pk
            JOIN persons p ON pk.recipient_id = p.wpi_id
            WHERE p.is_student = TRUE
            GROUP BY
                COALESCE(pk.service_type, 'Unknown')
        )
        SELECT
            service_type,
            package_count,
            ROUND(
                100.0 * package_count /
                NULLIF(SUM(package_count) OVER (), 0),
                2
            ) AS percent_of_all_packages,
            total_emissions_kg,
            avg_emissions_per_package_kg
        FROM base
        ORDER BY
            package_count DESC
    """)

    results = db.exec(query).all()

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No package data available for students"
        )

    rows = []
    for (
        service_type,
        package_count,
        percent_of_all_packages,
        total_emissions_kg,
        avg_emissions_per_package_kg,
    ) in results:
        rows.append({
            "service_type": service_type,
            "package_count": package_count,
            "percent_of_all_packages": float(percent_of_all_packages)
                if percent_of_all_packages is not None else 0.0,
            "total_emissions_kg": round(total_emissions_kg or 0, 2),
            "avg_emissions_per_package_kg": round(avg_emissions_per_package_kg or 0, 2),
        })

    return {
        "group_by": "all_students",
        "students_only": True,
        "row_count": len(rows),
        "rows": rows,
    }


@router.get("/by-major")
async def get_service_type_stats_by_major(
    db: Session = Depends(get_session),
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
    - percent_of_major_packages
    - total_emissions_kg
    - avg_emissions_per_package_kg
    """

    student_filter = ""
    if students_only:
        student_filter = "AND p.is_student = TRUE "

    query = text(f"""
        WITH base AS (
            SELECT
                d.department_name AS major,
                COALESCE(pk.service_type, 'Unknown') AS service_type,
                COUNT(*) AS package_count,
                COALESCE(SUM(pk.total_emissions_kg), 0) AS total_emissions_kg,
                COALESCE(AVG(pk.total_emissions_kg), 0) AS avg_emissions_per_package_kg
            FROM packages pk
            JOIN persons p ON pk.recipient_id = p.wpi_id
            JOIN departments d ON p.wpi_id = d.person_id
            WHERE 1=1
            {student_filter}
            GROUP BY
                d.department_name,
                COALESCE(pk.service_type, 'Unknown')
        )
        SELECT
            major,
            service_type,
            package_count,
            ROUND(
                100.0 * package_count /
                NULLIF(SUM(package_count) OVER (PARTITION BY major), 0),
                2
            ) AS percent_of_major_packages,
            total_emissions_kg,
            avg_emissions_per_package_kg
        FROM base
        ORDER BY
            major ASC,
            package_count DESC
    """)

    results = db.exec(query).all()

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No package data available"
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
            "percent_of_major_packages": float(percent_of_major_packages or 0),
            "total_emissions_kg": round(total_emissions_kg or 0, 2),
            "avg_emissions_per_package_kg": round(avg_emissions_per_package_kg or 0, 2),
        })

    return {
        "group_by": "major",
        "students_only": students_only,
        "row_count": len(rows),
        "rows": rows,
    }


@router.get("/by-class-year")
async def get_service_type_stats_by_class_year(
    db: Session = Depends(get_session),
    students_only: bool = Query(
        True,
        description="If true, only include packages where the recipient is a student"
    )
):
    """
    Service-type statistics grouped by class year bucket.
    """

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
                    WHEN p.class_year BETWEEN 2026 AND 2029
                        THEN 'Class of ' || p.class_year::text
                    ELSE 'Unknown'
                END AS class_year_group
            FROM packages pk
            JOIN persons p ON pk.recipient_id = p.wpi_id
            WHERE 1=1
            {student_filter}
        ),
        base AS (
            SELECT
                class_year_group,
                COALESCE(service_type, 'Unknown') AS service_type,
                COUNT(*) AS package_count,
                COALESCE(SUM(total_emissions_kg), 0) AS total_emissions_kg,
                COALESCE(AVG(total_emissions_kg), 0) AS avg_emissions_per_package_kg
            FROM classified
            GROUP BY
                class_year_group,
                COALESCE(service_type, 'Unknown')
        )
        SELECT
            class_year_group,
            service_type,
            package_count,
            ROUND(
                100.0 * package_count /
                NULLIF(SUM(package_count) OVER (PARTITION BY class_year_group), 0),
                2
            ) AS percent_of_year_packages,
            total_emissions_kg,
            avg_emissions_per_package_kg
        FROM base
        ORDER BY
            class_year_group,
            package_count DESC
    """)

    results = db.exec(query).all()

    if not results:
        raise HTTPException(
            status_code=404,
            detail="No package data available"
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
            "percent_of_year_packages": float(percent_of_year_packages or 0),
            "total_emissions_kg": round(total_emissions_kg or 0, 2),
            "avg_emissions_per_package_kg": round(avg_emissions_per_package_kg or 0, 2),
        })

    return {
        "group_by": "class_year",
        "students_only": students_only,
        "row_count": len(rows),
        "rows": rows,
    }
