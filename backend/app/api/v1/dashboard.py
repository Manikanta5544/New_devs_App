from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any
from app.services.cache import get_revenue_summary
from app.core.auth import authenticate_request as get_current_user

from decimal import Decimal

router = APIRouter()

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    property_id: str,
    month: int = Query(None, ge=1, le=12),
    year: int = Query(None, ge=1),
    current_user: dict = Depends(get_current_user)
) -> Dict[str, Any]:

    tenant_id = (
        current_user.get("tenant_id")
        if isinstance(current_user, dict)
        else getattr(current_user, "tenant_id", None)
    )

    if not tenant_id:
        raise HTTPException(status_code=403, detail="Authenticated tenant is required")

    if (month is None) != (year is None):
        raise HTTPException(
            status_code=422,
            detail="Both month and year must be provided together"
        )

    if month is not None and year is not None:
        from app.services.reservations import calculate_monthly_revenue
        from app.core.database_pool import DatabasePool

        try:
            db_pool = DatabasePool()
            await db_pool.initialize()

            if not db_pool.session_factory:
                raise HTTPException(
                    status_code=503,
                    detail="Database pool not available"
                )

            async with db_pool.get_session() as session:
                total_revenue = await calculate_monthly_revenue(
                    property_id=property_id,
                    tenant_id=tenant_id,
                    month=month,
                    year=year,
                    db_session=session
                )

            return {
                "property_id": property_id,
                "total_revenue": str(total_revenue),
                "currency": "USD",
                "reservations_count": None
            }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail="Unable to calculate monthly revenue"
            ) from e
        
    revenue_data = await get_revenue_summary(property_id, tenant_id)
    total_revenue = str(Decimal(str(revenue_data["total"])))
    return {
        "property_id": revenue_data['property_id'],
        "total_revenue": total_revenue_float,
        "currency": revenue_data['currency'],
        "reservations_count": revenue_data['count']
    }
