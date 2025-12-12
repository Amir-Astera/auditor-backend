from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.modules.customers.models import CustomerStatus


class CustomerCreate(BaseModel):
    company_name: str = Field(..., description="Название компании заказчика")
    short_description: str | None = Field(None, description="Краткое описание")
    assigned_employee_id: UUID
    status: CustomerStatus = CustomerStatus.IN_PROGRESS


class CustomerUpdate(BaseModel):
    company_name: str | None = None
    short_description: str | None = None
    assigned_employee_id: UUID | None = None
    status: CustomerStatus | None = None


class CustomerBase(BaseModel):
    id: UUID
    company_name: str
    short_description: str | None
    assigned_employee_id: UUID
    status: CustomerStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True
