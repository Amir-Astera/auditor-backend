from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.auth.models import User
from app.modules.auth.router import get_current_admin, get_current_employee
from app.modules.customers.models import Customer
from app.modules.customers.schemas import CustomerBase, CustomerCreate, CustomerUpdate

router = APIRouter(prefix="/customers", tags=["customers"])


@router.post(
    "",
    response_model=CustomerBase,
    summary="Создать заказчика",
)
def create_customer(
    payload: CustomerCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_employee),
):
    # можно добавить проверку, что current_user имеет право назначать на другого
    customer = Customer(
        company_name=payload.company_name,
        short_description=payload.short_description,
        assigned_employee_id=payload.assigned_employee_id,
        status=payload.status,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get(
    "",
    response_model=list[CustomerBase],
    summary="Список заказчиков текущего сотрудника",
)
def list_my_customers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_employee),
):
    customers = (
        db.query(Customer)
        .filter(Customer.assigned_employee_id == current_user.id)
        .order_by(Customer.created_at.desc())
        .all()
    )
    return customers


@router.get(
    "/{customer_id}",
    response_model=CustomerBase,
    summary="Получить заказчика",
)
def get_customer(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_employee),
):
    customer = db.query(Customer).get(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )

    # можно ограничить доступ только к своим заказчикам
    if customer.assigned_employee_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return customer


@router.patch(
    "/{customer_id}",
    response_model=CustomerBase,
    summary="Обновить заказчика",
)
def update_customer(
    customer_id: UUID,
    payload: CustomerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_employee),
):
    customer = db.query(Customer).get(customer_id)
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found"
        )

    if customer.assigned_employee_id != current_user.id and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    data = payload.dict(exclude_unset=True)
    for key, value in data.items():
        setattr(customer, key, value)

    db.commit()
    db.refresh(customer)
    return customer