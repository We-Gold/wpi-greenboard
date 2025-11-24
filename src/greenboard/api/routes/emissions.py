from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, text
from typing import Optional

from ..database import get_session
from ..models import Package, Carrier

router = APIRouter(prefix="/emissions", tags=["emissions"])


@router.get("/tracking/{tracking_number}")
async def get_emissions_by_tracking(
    tracking_number: str,
    db: Session = Depends(get_session)
):
    """
    Get complete emissions data for a package by tracking number.
    Calculates weight and other metrics on the fly from existing data.
    """
    query = text(f"""
        SELECT 
            pk.package_id,
            pk.tracking_number,
            c.carrier_name,
            pk.service_type,
            pk.date_shipped,
            pk.total_emissions_kg,
            pk.distance_traveled,
            e.emission_factor,
            pk.recipient_id
        FROM packages pk
        LEFT JOIN carriers c ON pk.carrier_id = c.carrier_id
        LEFT JOIN emissions e ON pk.service_type = e.service_type
        WHERE pk.tracking_number = '{tracking_number}'
    """)
    
    result = db.exec(query).first()
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Package with tracking number {tracking_number} not found")
    
    # Unpack results
    package_id, tracking, carrier, service_type, date_shipped, total_emissions, distance_km, emission_factor, recipient_id = result
    
    # Calculate weight on the fly (reverse calculation)
    # Formula: emissions = (weight_kg / 1000) × distance × factor
    # Therefore: weight_kg = (emissions × 1000) / (distance × factor)
    weight_kg = None
    if emission_factor and distance_km and emission_factor > 0 and distance_km > 0 and total_emissions:
        weight_kg = (total_emissions * 1000) / (distance_km * emission_factor)
    
    # Determine transport mode from service type
    transport_mode = "unknown"
    if service_type:
        service_lower = service_type.lower()
        if any(x in service_lower for x in ['ground', 'home']):
            transport_mode = "truck_average"
        elif any(x in service_lower for x in ['air', 'express', 'overnight', 'next day']):
            if 'international' in service_lower:
                transport_mode = "air_longhaul"
            else:
                transport_mode = "air_shorthaul"
        elif 'ocean' in service_lower:
            transport_mode = "ocean_container"
        elif 'rail' in service_lower:
            transport_mode = "rail"
    
    # Calculate environmental equivalents
    trees_needed = total_emissions / 21 if total_emissions else 0
    miles_equivalent = total_emissions / 0.404 if total_emissions else 0
    km_to_miles = distance_km * 0.621371 if distance_km else 0
    
    return {
        "package_id": package_id,
        "tracking_number": tracking,
        "carrier": carrier,
        "service_type": service_type,
        "date_shipped": date_shipped,
        "emissions_calculation": {
            "total_emissions_kg": round(total_emissions, 4) if total_emissions else 0,
            "weight_used_kg": round(weight_kg, 2) if weight_kg else None,
            "is_dimensional_weight": None,  # Not stored, can't determine
            "distance_km": round(distance_km, 2) if distance_km else 0,
            "distance_miles": round(km_to_miles, 2),
            "transport_mode": transport_mode,
            "emission_factor_kg_per_tonne_km": emission_factor,
            "calculation_formula": "Emissions = (Weight_kg / 1000) × Distance_km × Emission_Factor",
            "note": "Weight calculated from emissions data (reverse calculation)"
        },
        "route_information": {
            "note": "Origin and destination data not available in current schema",
            "distance_traveled_km": round(distance_km, 2) if distance_km else 0
        },
        "environmental_impact": {
            "trees_to_offset_1_year": round(trees_needed, 2),
            "miles_driven_equivalent": round(miles_equivalent, 1),
            "explanation": {
                "trees": "One tree absorbs ~21 kg CO2e per year",
                "miles": "Average car emits ~0.404 kg CO2e per mile"
            }
        },
        "recipient_id": recipient_id
    }


@router.get("/package/{package_id}/calculation-details")
async def get_calculation_details(
    package_id: int,
    db: Session = Depends(get_session)
):
    """
    Get detailed breakdown of how emissions were calculated.
    Reconstructs calculation from existing data.
    """
    query = text(f"""
        SELECT 
            pk.package_id,
            pk.tracking_number,
            c.carrier_name,
            pk.service_type,
            pk.total_emissions_kg,
            pk.distance_traveled,
            e.emission_factor
        FROM packages pk
        LEFT JOIN carriers c ON pk.carrier_id = c.carrier_id
        LEFT JOIN emissions e ON pk.service_type = e.service_type
        WHERE pk.package_id = {package_id}
    """)
    
    result = db.exec(query).first()
    
    if not result:
        raise HTTPException(status_code=404, detail=f"Package {package_id} not found")
    
    # Unpack
    pkg_id, tracking, carrier, service_type, total_emissions, distance_km, emission_factor = result
    
    # Calculate weight (reverse calculation)
    weight_kg = 0
    if emission_factor and distance_km and emission_factor > 0 and distance_km > 0 and total_emissions:
        weight_kg = (total_emissions * 1000) / (distance_km * emission_factor)
    
    weight_tonnes = weight_kg / 1000
    
    # Determine transport mode
    transport_mode = "unknown"
    if service_type:
        service_lower = service_type.lower()
        if any(x in service_lower for x in ['ground', 'home']):
            transport_mode = "truck_average"
        elif any(x in service_lower for x in ['air', 'express', 'overnight', 'next day']):
            transport_mode = "air_shorthaul" if 'international' not in service_lower else "air_longhaul"
    
    # Reconstruct calculation steps
    tonne_km = weight_tonnes * distance_km if distance_km else 0
    calculated_emissions = tonne_km * emission_factor if emission_factor else 0
    
    return {
        "package_id": pkg_id,
        "tracking_number": tracking,
        "carrier": carrier,
        "service_type": service_type,
        "calculation_inputs": {
            "weight_kg": round(weight_kg, 2),
            "weight_tonnes": round(weight_tonnes, 4),
            "is_dimensional_weight": None,
            "distance_km": round(distance_km, 2) if distance_km else 0,
            "transport_mode": transport_mode,
            "emission_factor_per_tonne_km": emission_factor,
            "note": "Weight calculated from reverse formula: weight = (emissions × 1000) / (distance × factor)"
        },
        "calculation_steps": {
            "step_1": {
                "description": "Convert weight to tonnes",
                "formula": "weight_tonnes = weight_kg ÷ 1000",
                "calculation": f"{weight_kg:.2f} ÷ 1000 = {weight_tonnes:.4f}",
                "result": round(weight_tonnes, 4)
            },
            "step_2": {
                "description": "Calculate tonne-kilometers",
                "formula": "tonne_km = weight_tonnes × distance_km",
                "calculation": f"{weight_tonnes:.4f} × {distance_km} = {tonne_km:.2f}",
                "result": round(tonne_km, 2)
            },
            "step_3": {
                "description": "Apply emission factor",
                "formula": "emissions_kg = tonne_km × emission_factor",
                "calculation": f"{tonne_km:.2f} × {emission_factor} = {calculated_emissions:.4f}",
                "result": round(calculated_emissions, 4)
            }
        },
        "result": {
            "calculated_emissions_kg": round(calculated_emissions, 4),
            "stored_emissions_kg": round(total_emissions, 4) if total_emissions else 0,
            "match": abs(calculated_emissions - (total_emissions or 0)) < 0.01 if total_emissions else False,
            "note": "May not match exactly if weight was calculated differently originally"
        }
    }


@router.get("/factors")
async def get_emission_factors(db: Session = Depends(get_session)):
    """
    Get all emission factors from the database.
    Shows service types and their CO2e per tonne-km values.
    """
    # Get factors from database
    query = text("""
        SELECT service_type, emission_factor
        FROM emissions
        ORDER BY service_type
    """)
    
    results = db.exec(query).all()
    
    # Build response
    factors = {}
    for service_type, emission_factor in results:
        # Determine transport category
        category = "ground"
        if service_type:
            service_lower = service_type.lower()
            if any(x in service_lower for x in ['air', 'express', 'overnight', 'next']):
                category = "air"
            elif 'ocean' in service_lower:
                category = "ocean"
            elif 'rail' in service_lower:
                category = "rail"
        
        factors[service_type] = {
            "value": emission_factor,
            "unit": "kg CO2e per tonne-km",
            "category": category,
            "description": service_type
        }
    
    return {
        "emission_factors": factors,
        "source": "Database emmissions table",
        "environmental_equivalents": {
            "trees_absorption_rate": {
                "value": 21,
                "unit": "kg CO2e per tree per year",
                "description": "Average CO2 absorbed by one mature tree annually"
            },
            "car_emissions_rate": {
                "value": 0.404,
                "unit": "kg CO2e per mile",
                "description": "Average passenger car emissions"
            }
        },
        "standard_factors": {
            "truck_average": {"value": 0.127, "description": "Average truck transport"},
            "truck_longhaul": {"value": 0.062, "description": "Long-haul truck (efficient)"},
            "air_shorthaul": {"value": 0.82, "description": "Short-haul air freight"},
            "air_longhaul": {"value": 0.69, "description": "Long-haul air freight"},
            "rail": {"value": 0.022, "description": "Rail freight"},
            "ocean_container": {"value": 0.010, "description": "Ocean container ship"}
        }
    }


@router.get("/search")
async def search_packages(
    tracking_number: Optional[str] = Query(None, description="Search by tracking number"),
    min_emissions: Optional[float] = Query(None, description="Minimum emissions in kg"),
    max_emissions: Optional[float] = Query(None, description="Maximum emissions in kg"),
    carrier: Optional[str] = Query(None, description="Filter by carrier name"),
    service_type: Optional[str] = Query(None, description="Filter by service type"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(20, ge=1, le=100, description="Results per page"),
    db: Session = Depends(get_session)
):
    """
    Search packages with flexible filters.
    Works with existing schema, calculates weight on the fly.
    """
    # Build dynamic WHERE clause
    conditions = ["1=1"]
    
    if tracking_number:
        conditions.append(f"pk.tracking_number ILIKE '%{tracking_number}%'")
    
    if min_emissions is not None:
        conditions.append(f"pk.total_emissions_kg >= {min_emissions}")
    
    if max_emissions is not None:
        conditions.append(f"pk.total_emissions_kg <= {max_emissions}")
    
    if carrier:
        conditions.append(f"c.carrier_name ILIKE '%{carrier}%'")
    
    if service_type:
        conditions.append(f"pk.service_type ILIKE '%{service_type}%'")
    
    if start_date:
        conditions.append(f"pk.date_shipped >= '{start_date}'")
    
    if end_date:
        conditions.append(f"pk.date_shipped <= '{end_date}'")
    
    where_clause = " AND ".join(conditions)
    
    query = text(f"""
        SELECT 
            pk.package_id,
            pk.tracking_number,
            c.carrier_name,
            pk.service_type,
            pk.total_emissions_kg,
            pk.distance_traveled,
            e.emission_factor,
            pk.date_shipped
        FROM packages pk
        LEFT JOIN carriers c ON pk.carrier_id = c.carrier_id
        LEFT JOIN emissions e ON pk.service_type = e.service_type
        WHERE {where_clause}
        ORDER BY pk.date_shipped DESC
        LIMIT {limit}
    """)
    
    results = db.exec(query).all()
    
    packages = []
    for r in results:
        pkg_id, tracking, carrier, service, emissions, distance, factor, date_shipped = r
        
        # Calculate weight
        weight_kg = None
        if factor and distance and factor > 0 and distance > 0 and emissions:
            weight_kg = (emissions * 1000) / (distance * factor)
        
        # Determine transport mode
        transport_mode = "unknown"
        if service:
            service_lower = service.lower()
            if any(x in service_lower for x in ['ground', 'home']):
                transport_mode = "truck"
            elif any(x in service_lower for x in ['air', 'express', 'overnight']):
                transport_mode = "air"
        
        trees = emissions / 21 if emissions else 0
        miles = emissions / 0.404 if emissions else 0
        
        packages.append({
            "package_id": pkg_id,
            "tracking_number": tracking,
            "carrier": carrier,
            "service_type": service,
            "total_emissions_kg": round(emissions, 4) if emissions else 0,
            "distance_km": round(distance, 2) if distance else 0,
            "weight_kg": round(weight_kg, 2) if weight_kg else None,
            "transport_mode": transport_mode,
            "date_shipped": date_shipped,
            "environmental_impact": {
                "trees_needed": round(trees, 2),
                "miles_equivalent": round(miles, 1)
            }
        })
    
    return {
        "total_results": len(packages),
        "packages": packages,
        "note": "Weight calculated from emissions data using reverse formula"
    }