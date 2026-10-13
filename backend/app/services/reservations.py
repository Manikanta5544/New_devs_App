from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, List
from zoneinfo import ZoneInfo
from sqlalchemy import text
from fastapi import HTTPException

async def calculate_monthly_revenue(property_id: str, tenant_id: str, month: int, year: int, db_session) -> Decimal:
    """
    Calculates revenue for a specific month.
    """

    if not tenant_id:
        raise HTTPException(status_code=403, detail="Tenant context required")

    if not 1 <= month <= 12 or year < 1:
        raise HTTPException(status_code=422, detail="Invalid reporting period")

    if db_session is None:
        raise ValueError("db_session is required to calculate monthly revenue")

    property_result = await db_session.execute(
        text("""
            SELECT timezone
            FROM properties
            WHERE id = :property_id
              AND tenant_id = :tenant_id
        """),
        {
            "property_id": property_id,
            "tenant_id": tenant_id,
        },
    )
    property_row = property_result.fetchone()

    if property_row is None:
        raise HTTPException(status_code=404, detail="Property not found")

    try:
        property_tz = ZoneInfo(property_row.timezone)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Property timezone configuration is invalid",
        ) from exc

    start_local = datetime(year, month, 1, tzinfo=property_tz)

    if month == 12:
        end_local = datetime(year + 1, 1, 1, tzinfo=property_tz)
    else:
        end_local = datetime(year, month + 1, 1, tzinfo=property_tz)

    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    print(
        f"DEBUG: Querying revenue for {property_id} "
        f"from {start_utc} to {end_utc} (UTC)"
    )

    # SQL Simulation (This would be executed against the actual DB)
    query = """
        SELECT COALESCE(SUM(total_amount), 0) AS total
        FROM reservations
        WHERE property_id = :property_id
          AND tenant_id = :tenant_id
          AND check_in_date >= :start_utc
          AND check_in_date < :end_utc
    """

    # In production this query executes against a database session.
    # result = await db.fetch_val(query, property_id, tenant_id, start_date, end_date)
    # return result or Decimal('0')

    result = await db_session.execute(
        text(query),
        {
            "property_id": property_id,
            "tenant_id": tenant_id,
            "start_utc": start_utc,
            "end_utc": end_utc,
        },
    )

    total = result.scalar_one()

    return Decimal(str(total))


async def calculate_total_revenue(property_id: str, tenant_id: str) -> Dict[str, Any]:
    """
    Aggregates revenue from database.
    """
    try:
        # Import database pool
        from app.core.database_pool import db_pool
        
        # Initialize pool if needed
        # db_pool = DatabasePool()
        await db_pool.initialize()
        
        if db_pool.session_factory:
            async with db_pool.get_session() as session:
                # Use SQLAlchemy text for raw SQL
                from sqlalchemy import text
                
                query = text("""
                    SELECT 
                        property_id,
                        SUM(total_amount) as total_revenue,
                        COUNT(*) as reservation_count
                    FROM reservations 
                    WHERE property_id = :property_id AND tenant_id = :tenant_id
                    GROUP BY property_id
                """)
                
                result = await session.execute(query, {
                    "property_id": property_id, 
                    "tenant_id": tenant_id
                })
                row = result.fetchone()
                
                if row:
                    total_revenue = Decimal(str(row.total_revenue))
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": str(total_revenue),
                        "currency": "USD", 
                        "count": row.reservation_count
                    }
                else:
                    # No reservations found for this property
                    return {
                        "property_id": property_id,
                        "tenant_id": tenant_id,
                        "total": "0.00",
                        "currency": "USD",
                        "count": 0
                    }
        else:
            raise Exception("Database pool not available")
            
    except Exception:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception(
            "Failed to calculate revenue for property %s and tenant %s",
            property_id,
            tenant_id,
        )
        raise