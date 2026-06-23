from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str
    full_name: Optional[str] = None
    password: Optional[str] = None
    role: str  # 'doctor', 'technician', 'admin'


class PurchaseDetail(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    machine_id: Optional[int] = Field(default=None, foreign_key="machine.id")
    vendor: Optional[str] = None
    manufacturer: Optional[str] = None
    hospital_serial_number: Optional[str] = None
    purchase_date: Optional[datetime] = None
    price: Optional[float] = None
    safety_standard: Optional[str] = None


class Machine(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    location: Optional[str] = None
    model: Optional[str] = None
    serial: Optional[str] = None
    status: str = "Active"  # Active, Under Maintenance, Offline
    last_maintenance: Optional[datetime] = None


class MaintenanceLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    machine_id: int = Field(foreign_key="machine.id")
    performed_by: Optional[str] = None
    notes: Optional[str] = None
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None


class UsageLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    machine_id: int = Field(foreign_key="machine.id")
    user: Optional[str] = None
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None
    effectiveness: Optional[float] = None  # 0-100


class IssueReport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    machine_id: int = Field(foreign_key="machine.id")
    reported_by: Optional[str] = None
    severity: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
