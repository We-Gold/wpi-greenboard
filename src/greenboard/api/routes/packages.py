from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, text
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel
import os
import re
from sqlalchemy.exc import IntegrityError

from ..database import get_session
from ..models import Package, Carrier, Emission, PackageRead, Person
from ...emissions.emissions_calculator import (
    EmissionsCalculator, 
    EMISSION_FACTORS, 
    DEFAULT_DISTANCES,
    calculate_package_emissions
)

router = APIRouter(prefix="/packages", tags=["packages"])


class PackageCreate(BaseModel):
    """Model for creating a new package - weight_kg is used for calculation only, not stored"""
    tracking_number: str
    carrier_name: str
    service_type: Optional[str] = None
    recipient_id: str  # Required - WPI ID of the recipient
    date_shipped: Optional[datetime] = None
    weight_kg: Optional[float] = None  # Used for calculation, not stored in DB
    distance_traveled: Optional[float] = None


@router.get("/carriers")
async def get_carriers(db: Session = Depends(get_session)):
    """Get list of all carriers"""
    carriers = db.exec(select(Carrier)).all()
    return [{"carrier_id": c.carrier_id, "carrier_name": c.carrier_name} for c in carriers]


@router.get("/service-types")
async def get_service_types(db: Session = Depends(get_session)):
    """Get list of all service types with their emission factors"""
    service_types = db.exec(select(Emission)).all()
    return [
        {
            "service_type": e.service_type,
            "emission_factor": e.emission_factor
        }
        for e in service_types
    ]


@router.get("/persons")
async def get_persons(
    db: Session = Depends(get_session),
    students_only: bool = Query(False, description="Filter to students only")
):
    """Get list of all persons (WPI IDs) with their names for dropdown selection"""
    query = select(Person)
    if students_only:
        query = query.where(Person.is_student == True)
    
    persons = db.exec(query.order_by(Person.wpi_id)).all()
    
    return [
        {
            "wpi_id": p.wpi_id,
            "name": f"{p.first_name or ''} {p.last_name or ''}".strip() or p.wpi_id,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "is_student": p.is_student,
            "box_number": p.box_number
        }
        for p in persons
    ]


def detect_carrier_from_tracking(tracking_number: str) -> Optional[str]:
    """
    Detect carrier from tracking number format.
    
    UPS: Starts with "1Z", 18 characters total
    FedEx: 12 digits, or alphanumeric patterns
    """
    tracking = tracking_number.strip().upper()
    
    # UPS tracking numbers start with "1Z" and are 18 characters
    if tracking.startswith("1Z") and len(tracking) == 18:
        return "ups"
    
    # FedEx tracking numbers are typically 12 digits or alphanumeric
    # Common patterns: 12 digits, or alphanumeric with specific patterns
    if re.match(r'^\d{12}$', tracking) or re.match(r'^\d{4}\s?\d{4}\s?\d{4}$', tracking.replace(" ", "")):
        return "fedex"
    
    # Try to match FedEx alphanumeric patterns
    if re.match(r'^[0-9A-Z]{10,15}$', tracking):
        # Could be FedEx, but less certain - try FedEx first
        return "fedex"
    
    return None


def get_carrier_credentials(carrier: str) -> Optional[Dict[str, str]]:
    """
    Get carrier credentials from environment variables, with fallback to default credentials.
    
    First tries environment variables:
    - UPS_CLIENT_ID, UPS_CLIENT_SECRET
    - FEDEX_CLIENT_ID, FEDEX_CLIENT_SECRET
    
    Falls back to default credentials from csv_batch_processor.py if env vars not set.
    """
    carrier_lower = carrier.lower()
    
    # Default credentials (from csv_batch_processor.py)
    default_credentials = {
        'ups': {
            'client_id': 'HCTsyp8JsmGuiOYCkxpZAak9ZusNbA8Me9d1k5g7rmivxpoC',
            'client_secret': 'bbUGGCg1q66AuEeGV66EjhcbG6GNtOGYTb1r5vqAxssUaBsovaQIKPiTWHHpAGZV'
        },
        'fedex': {
            'client_id': 'l74673b0ec87d749268da2b0e59460429c',
            'client_secret': '4e8527a4c6614ef386672eebeb086223'
        },
        'usps': {
            'client_id': 'vrBISZnb8yn4KTNm0SA0UAA4yqlDfGdEFHkfARJzWgizAzGq',
            'client_secret': '13b8Ius4epIhNbIlz2s9KIlAOT0JVkSqnBGjtD6q5rnW5TRHrchLZYBfwUAaM51Y'
        },
        'dhl': {
            'client_id': 'JLOAsRhxyRDiU4hyT1w4ueexJlqSMVqg',
            'client_secret': 'cMI8ojXzljz32GhE'
        }
    }
    
    # Try environment variables first
    if carrier_lower == "ups":
        client_id = os.getenv("UPS_CLIENT_ID")
        client_secret = os.getenv("UPS_CLIENT_SECRET")
        if client_id and client_secret:
            return {"client_id": client_id, "client_secret": client_secret}
    
    elif carrier_lower == "fedex":
        client_id = os.getenv("FEDEX_CLIENT_ID")
        client_secret = os.getenv("FEDEX_CLIENT_SECRET")
        if client_id and client_secret:
            return {"client_id": client_id, "client_secret": client_secret}
    
    elif carrier_lower == "usps":
        client_id = os.getenv("USPS_CLIENT_ID")
        client_secret = os.getenv("USPS_CLIENT_SECRET")
        if client_id and client_secret:
            return {"client_id": client_id, "client_secret": client_secret}
    
    elif carrier_lower == "dhl":
        client_id = os.getenv("DHL_CLIENT_ID")
        client_secret = os.getenv("DHL_CLIENT_SECRET")
        if client_id and client_secret:
            return {"client_id": client_id, "client_secret": client_secret}
    
    # Fallback to default credentials
    if carrier_lower in default_credentials:
        return default_credentials[carrier_lower]
    
    return None


class TrackingLookupRequest(BaseModel):
    """Request model for tracking number lookup"""
    tracking_number: str
    carrier: Optional[str] = None
    production: bool = False


@router.post("/lookup-tracking")
async def lookup_tracking_number(
    request: TrackingLookupRequest
):
    """
    Lookup package information from tracking number using carrier APIs.
    
    Automatically detects carrier from tracking number format if not provided.
    Extracts: weight, distance, service type, carrier, dates, addresses.
    
    Requires carrier API credentials in environment variables:
    - UPS: UPS_CLIENT_ID, UPS_CLIENT_SECRET
    - FedEx: FEDEX_CLIENT_ID, FEDEX_CLIENT_SECRET
    """
    tracking_number = request.tracking_number.strip()
    carrier = request.carrier
    production = request.production
    
    # Detect carrier if not provided
    if not carrier:
        carrier = detect_carrier_from_tracking(tracking_number)
        if not carrier:
            raise HTTPException(
                status_code=400, 
                detail="Could not detect carrier from tracking number format. Please specify carrier (ups or fedex)."
            )
    
    carrier_lower = carrier.lower()
    if carrier_lower not in ["ups", "fedex"]:
        raise HTTPException(
            status_code=400,
            detail=f"Carrier '{carrier}' not supported. Supported: ups, fedex"
        )
    
    # Get credentials (will use defaults from csv_batch_processor.py if env vars not set)
    credentials = get_carrier_credentials(carrier_lower)
    if not credentials:
        raise HTTPException(
            status_code=500,
            detail=f"Carrier '{carrier}' not supported or credentials not available."
        )
    
    # Lookup package using emissions calculator
    try:
        result = calculate_package_emissions(
            carrier=carrier_lower,
            tracking_number=tracking_number,
            credentials=credentials,
            production=production,
            verbose=False
        )
        
        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Could not retrieve package information for tracking number {tracking_number}. The package may not exist or API access may be restricted."
            )
        
        package_info = result.package_info
        
        # Extract information for package creation
        return {
            "tracking_number": package_info.tracking_number,
            "carrier": package_info.carrier,
            "service_type": package_info.service_description,
            "service_code": package_info.service_code,
            "weight_kg": result.weight_used_kg,
            "distance_km": result.distance_km,
            "total_emissions_kg": result.total_emissions_kg,
            "transport_mode": result.transport_mode,
            "origin": {
                "city": package_info.origin.city if package_info.origin else None,
                "state": package_info.origin.state if package_info.origin else None,
                "postal_code": package_info.origin.postal_code if package_info.origin else None,
                "country": package_info.origin.country if package_info.origin else None,
            } if package_info.origin else None,
            "destination": {
                "city": package_info.destination.city if package_info.destination else None,
                "state": package_info.destination.state if package_info.destination else None,
                "postal_code": package_info.destination.postal_code if package_info.destination else None,
                "country": package_info.destination.country if package_info.destination else None,
            } if package_info.destination else None,
            "pickup_date": package_info.pickup_date,
            "breakdown": result.breakdown
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error looking up tracking number: {str(e)}"
        )


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


def map_service_type_to_transport_mode(service_type: Optional[str], distance_km: Optional[float] = None) -> str:
    """
    Map service type string to transport mode used by EmissionsCalculator.
    
    Args:
        service_type: Service type string from database
        distance_km: Optional distance to determine if air is short or long haul
    
    Returns:
        Transport mode string (e.g., 'truck_average', 'air_shorthaul', etc.)
    """
    if not service_type:
        return 'truck_average'  # Default
    
    service_lower = service_type.lower()
    
    # Air services
    if any(x in service_lower for x in ['air', 'express', 'overnight', 'next day', 'next-day', '2nd day', '2-day']):
        # Determine if short or long haul based on distance
        if distance_km and distance_km > 1500:
            return 'air_longhaul'
        else:
            return 'air_shorthaul'
    
    # Ocean/maritime
    if any(x in service_lower for x in ['ocean', 'ship', 'maritime', 'sea']):
        return 'ocean_container'
    
    # Rail
    if 'rail' in service_lower:
        return 'rail'
    
    # Ground/truck services
    if any(x in service_lower for x in ['ground', 'truck', 'standard', 'economy']):
        if 'longhaul' in service_lower or 'long-haul' in service_lower:
            return 'truck_longhaul'
        elif 'urban' in service_lower:
            return 'truck_urban_delivery'
        else:
            return 'truck_average'
    
    # Default to truck_average
    return 'truck_average'


def calculate_emissions_with_calculator(
    weight_kg: float, 
    distance_km: float, 
    service_type: Optional[str] = None,
    include_last_mile: bool = True
) -> float:
    """
    Calculate emissions using the EmissionsCalculator.
    Note: weight_kg is used for calculation only, not stored in database.
    
    Args:
        weight_kg: Package weight in kilograms (for calculation only)
        distance_km: Distance traveled in kilometers
        service_type: Optional service type string
        include_last_mile: Whether to include last-mile delivery emissions
    
    Returns:
        Total emissions in kg CO2e
    """
    if weight_kg <= 0 or distance_km <= 0:
        return 0.0
    
    # Map service type to transport mode
    transport_mode = map_service_type_to_transport_mode(service_type, distance_km)
    
    # Use EmissionsCalculator
    calculator = EmissionsCalculator()
    
    # Calculate main transit emissions
    main_emissions = calculator.calculate_emissions(weight_kg, distance_km, transport_mode)
    total_emissions = main_emissions
    
    # Add last-mile delivery if requested
    if include_last_mile and transport_mode != 'last_mile':
        last_mile_distance = DEFAULT_DISTANCES['last_mile']
        last_mile_emissions = calculator.calculate_emissions(
            weight_kg, last_mile_distance, 'last_mile'
        )
        total_emissions += last_mile_emissions
    
    return round(total_emissions, 4)


@router.post("/", response_model=PackageRead)
async def create_package(
    package_data: PackageCreate,
    db: Session = Depends(get_session)
):
    """
    Create a new package and calculate emissions using the EmissionsCalculator.
    
    Note: weight_kg is accepted as input for calculation purposes but is NOT stored
    in the database. Only the calculated total_emissions_kg is stored.
    
    If weight_kg and distance_traveled are provided, emissions will be calculated automatically
    using the EmissionsCalculator, which:
    - Maps service_type to appropriate transport mode (truck, air, rail, ocean, etc.)
    - Uses standardized emission factors from the emissions_calculator module
    - Includes last-mile delivery emissions automatically
    - Determines air short-haul vs long-haul based on distance (>1500km = long-haul)
    """
    # Validate recipient exists
    recipient = db.exec(select(Person).where(Person.wpi_id == package_data.recipient_id)).first()
    if not recipient:
        raise HTTPException(
            status_code=400,
            detail=f"Recipient with WPI ID {package_data.recipient_id} not found. Please select a valid recipient."
        )
    
    # Get or create carrier
    carrier = db.exec(select(Carrier).where(Carrier.carrier_name == package_data.carrier_name)).first()
    if not carrier:
        # Create new carrier if it doesn't exist
        carrier = Carrier(carrier_name=package_data.carrier_name)
        db.add(carrier)
        db.commit()
        db.refresh(carrier)
    
    # Calculate emissions using EmissionsCalculator if weight and distance are provided
    # Note: weight_kg is used for calculation but NOT stored in the database
    total_emissions_kg = None
    if package_data.weight_kg and package_data.distance_traveled:
        total_emissions_kg = calculate_emissions_with_calculator(
            package_data.weight_kg,
            package_data.distance_traveled,
            package_data.service_type,
            include_last_mile=True
        )
    
    # Create package (without weight_kg - it's not in the database schema)
    new_package = Package(
        carrier_id=carrier.carrier_id,
        tracking_number=package_data.tracking_number,
        service_type=package_data.service_type,
        recipient_id=package_data.recipient_id,
        date_shipped=package_data.date_shipped,
        total_emissions_kg=total_emissions_kg,
        distance_traveled=package_data.distance_traveled
    )
    
    db.add(new_package)
    
    try:
        db.commit()
        db.refresh(new_package)
    except IntegrityError as e:
        db.rollback()
        # Extract the actual database error message
        error_message = str(e.orig) if hasattr(e, 'orig') else str(e)
        
        # Check if it's a unique constraint violation (duplicate tracking number)
        if 'unique' in error_message.lower() or 'duplicate' in error_message.lower() or 'already exists' in error_message.lower():
            # Try to get more details from the exception
            if hasattr(e.orig, 'pgcode') and e.orig.pgcode == '23505':  # PostgreSQL unique violation error code
                raise HTTPException(
                    status_code=400,
                    detail=f"Package with tracking number '{package_data.tracking_number}' already exists. Database constraint violation: {error_message}"
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=f"Duplicate package detected. Tracking number '{package_data.tracking_number}' already exists. Database error: {error_message}"
                )
        else:
            # Other integrity errors (foreign key violations, etc.)
            raise HTTPException(
                status_code=400,
                detail=f"Database constraint violation: {error_message}"
            )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error creating package: {str(e)}"
        )
    
    # Return the created package in PackageRead format
    return PackageRead(
        package_id=new_package.package_id,
        tracking_number=new_package.tracking_number,
        carrier_name=carrier.carrier_name,
        service_type=new_package.service_type,
        date_shipped=new_package.date_shipped,
        total_emissions_kg=new_package.total_emissions_kg,
        distance_traveled=new_package.distance_traveled,
        equivalent_trees_planted=new_package.equivalent_trees_planted,
        equivalent_miles_driven=new_package.equivalent_miles_driven
    )