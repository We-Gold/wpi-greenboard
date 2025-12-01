from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime
from enum import Enum


class TransactionTypeEnum(str, Enum):
    delivered = "delivered"
    stored = "stored"
    routed = "routed"


# ============================================================================
# Database Models (table=True)
# ============================================================================

class Carrier(SQLModel, table=True):
    __tablename__ = "carriers"
    
    carrier_id: Optional[int] = Field(default=None, primary_key=True)
    carrier_name: str = Field(max_length=20)
    
    # Relationships
    packages: List["Package"] = Relationship(back_populates="carrier")


class Emission(SQLModel, table=True):
    __tablename__ = "emissions"  # Fixed: database table is "emissions" (not "emmissions")
    
    service_type: str = Field(primary_key=True, max_length=50)
    emission_factor: Optional[float] = None
    
    # Relationships
    packages: List["Package"] = Relationship(back_populates="emission")


class Package(SQLModel, table=True):
    __tablename__ = "packages"
    
    package_id: Optional[int] = Field(default=None, primary_key=True)
    carrier_id: Optional[int] = Field(default=None, foreign_key="carriers.carrier_id")
    tracking_number: str = Field(max_length=255)
    service_type: Optional[str] = Field(default=None, foreign_key="emissions.service_type", max_length=50)
    date_shipped: Optional[datetime] = None
    total_emissions_kg: Optional[float] = None
    distance_traveled: Optional[float] = None
    recipient_id: Optional[str] = Field(default=None, foreign_key="persons.wpi_id", max_length=9)
    equivalent_trees_planted: Optional[float] = None
    equivalent_miles_driven: Optional[float] = None
    
    # Relationships
    carrier: Optional[Carrier] = Relationship(back_populates="packages")
    emission: Optional[Emission] = Relationship(back_populates="packages")
    transactions: List["Transaction"] = Relationship(back_populates="package")


class Person(SQLModel, table=True):
    __tablename__ = "persons"
    
    wpi_id: str = Field(primary_key=True, max_length=9)
    first_name: Optional[str] = Field(default=None, max_length=50)
    last_name: Optional[str] = Field(default=None, max_length=50)
    is_student: Optional[bool] = None
    is_mailroom_worker: Optional[bool] = None
    box_number: Optional[str] = Field(default=None, max_length=5)
    class_year: Optional[int] = None
    supervisor_id: Optional[str] = Field(default=None, foreign_key="persons.wpi_id", max_length=9)
    
    # Relationships
    departments: List["Department"] = Relationship(back_populates="person")
    transactions: List["Transaction"] = Relationship(back_populates="worker")
    # Note: Self-referential relationship for supervisor can be added if needed


class Department(SQLModel, table=True):
    __tablename__ = "departments"
    
    person_id: str = Field(foreign_key="persons.wpi_id", primary_key=True, max_length=9)
    department_name: str = Field(primary_key=True, max_length=100)
    
    # Relationships
    person: Optional[Person] = Relationship(back_populates="departments")


class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"
    
    transaction_id: Optional[int] = Field(default=None, primary_key=True)
    date: Optional[datetime] = None
    transaction_type: TransactionTypeEnum
    locker: Optional[str] = Field(default=None, max_length=20)
    location: Optional[str] = Field(default=None, max_length=20)
    package_id: int = Field(foreign_key="packages.package_id")
    worker_id: str = Field(foreign_key="persons.wpi_id", max_length=9)
    
    # Relationships
    package: Optional[Package] = Relationship(back_populates="transactions")
    worker: Optional[Person] = Relationship(back_populates="transactions")

### Output Data Models 
class PackageRead(SQLModel):
    """Response model for package with carrier info"""
    package_id: int
    tracking_number: str
    carrier_name: Optional[str] = None
    service_type: Optional[str] = None
    date_shipped: Optional[datetime] = None
    total_emissions_kg: Optional[float] = None
    distance_traveled: Optional[float] = None
    equivalent_trees_planted: Optional[float] = None
    equivalent_miles_driven: Optional[float] = None


class PersonRead(SQLModel):
    """Response model for person"""
    wpi_id: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    is_student: Optional[bool] = None
    box_number: Optional[str] = None
    class_year: Optional[int] = None
    

class EmissionsStats(SQLModel):
    """Statistics model"""
    carrier_name: str
    package_count: int
    total_emissions_kg: float
    avg_emissions_kg: float