from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, text
from typing import List, Dict, Any

from ..database import get_session
from ..models import Package, Carrier, Emission, PackageRead

router = APIRouter(prefix="/packages", tags=["packages"])


@router.get("/", response_model=List[PackageRead])
async def get_packages(
    page: int = Query(1, ge=1, description="Page number, starting from 1"),
    limit: int = Query(20, ge=1, le=100, description="Items per page (max 100)"),
    db: Session = Depends(get_session)
):
    offset = (page - 1) * limit

    # total = db.exec(select(Package)).count()  # optional: for total count
    statement = (
        select(
            Package.package_id,
            Package.tracking_number,
            Carrier.carrier_name,
            Package.service_type,
            Package.date_shipped,
            Package.total_emissions_kg,
            Package.distance_traveled
        )
        .join(Carrier, Package.carrier_id == Carrier.carrier_id, isouter=True)
        .offset(offset)
        .limit(limit)
    )
    
    results = db.exec(statement).all()
    
    return [
        PackageRead(
            package_id=r[0],
            tracking_number=r[1],
            carrier_name=r[2],
            service_type=r[3],
            date_shipped=r[4],
            total_emissions_kg=r[5],
            distance_traveled=r[6]
        )
        for r in results
    ]


@router.get("/{package_id}", response_model=PackageRead)
async def get_package(
    package_id: int,
    session: Session = Depends(get_session)
):
    """Get single package by ID."""
    statement = (
        select(
            Package.package_id,
            Package.tracking_number,
            Carrier.carrier_name,
            Package.service_type,
            Package.date_shipped,
            Package.total_emissions_kg,
            Package.distance_traveled
        )
        .join(Carrier, Package.carrier_id == Carrier.carrier_id, isouter=True)
        .where(Package.package_id == package_id)
    )
    
    result = session.exec(statement).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Package not found")
    
    return PackageRead(
        package_id=result[0],
        tracking_number=result[1],
        carrier_name=result[2],
        service_type=result[3],
        date_shipped=result[4],
        total_emissions_kg=result[5],
        distance_traveled=result[6]
    )


@router.get("/tracking/{tracking_number}", response_model=PackageRead)
async def get_package_by_tracking(
    tracking_number: str,
    session: Session = Depends(get_session)
):
    """Get package by tracking number."""
    statement = select(Package).where(Package.tracking_number == tracking_number)
    package = session.exec(statement).first()
    
    if not package:
        raise HTTPException(status_code=404, detail="Package not found")
    
    return await get_package(package.package_id, session)

@router.get("/student/{wpi_id}", response_model=List[PackageRead])
async def get_packages_by_student(
    wpi_id: str,
    db: Session = Depends(get_session)
):
    """Get all packages by student WPI ID."""

    statement = (
        select(
            Package.package_id,
            Package.tracking_number,
            Carrier.carrier_name,
            Package.service_type,
            Package.date_shipped,
            Package.total_emissions_kg,
            Package.distance_traveled,
            Package.equivalent_trees_planted,
            Package.equivalent_miles_driven
        )
        .where(Package.recipient_id == wpi_id)
        .join(Carrier, Package.carrier_id == Carrier.carrier_id, isouter=True)
    )
    
    results = db.exec(statement).all()
    
    return [
        PackageRead(
            package_id=r[0],
            tracking_number=r[1],
            carrier_name=r[2],
            service_type=r[3],
            date_shipped=r[4],
            total_emissions_kg=r[5],
            distance_traveled=r[6],
            equivalent_trees_planted=r[7],
            equivalent_miles_driven=r[8]
        )
        for r in results
    ]


@router.get("/student/{wpi_id}/carrier-stats")
async def get_carrier_stats_by_student(
    wpi_id: str,
    db: Session = Depends(get_session)
):
    """
    Get carrier statistics for a specific student.
    Returns aggregated package count, frequency, and emissions per carrier.
    Uses the person_carrier_stats view created in database/init.sql
    """
    query = text("""
        SELECT 
            carrier_name,
            package_count,
            frequency_percentage,
            total_emissions_kg,
            avg_emissions_per_package_kg,
            total_distance_km,
            avg_distance_per_package_km,
            total_trees_planted,
            total_miles_driven
        FROM person_carrier_stats
        WHERE wpi_id = :wpi_id
        ORDER BY package_count DESC
    """)
    
    results = db.exec(query.params(wpi_id=wpi_id)).all()
    
    if not results:
        # Check if student exists but has no packages
        person_check = text("SELECT wpi_id FROM persons WHERE wpi_id = :wpi_id")
        person_exists = db.exec(person_check.params(wpi_id=wpi_id)).first()
        if not person_exists:
            raise HTTPException(status_code=404, detail="Student not found")
        return []  # Student exists but has no packages
    
    stats = []
    for row in results:
        stats.append({
            "carrier_name": row[0],
            "package_count": row[1],
            "frequency_percentage": float(row[2]) if row[2] is not None else 0.0,
            "total_emissions_kg": float(row[3]) if row[3] is not None else 0.0,
            "avg_emissions_per_package_kg": float(row[4]) if row[4] is not None else 0.0,
            "total_distance_km": float(row[5]) if row[5] is not None else 0.0,
            "avg_distance_per_package_km": float(row[6]) if row[6] is not None else 0.0,
            "total_trees_planted": float(row[7]) if row[7] is not None else 0.0,
            "total_miles_driven": float(row[8]) if row[8] is not None else 0.0
        })
    
    return stats