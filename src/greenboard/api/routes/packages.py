from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from typing import List

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