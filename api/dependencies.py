"""
FastAPI Dependencies
"""
from collections.abc import Generator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings


async def verify_api_key(
    x_api_key: str | None = Header(None, alias="X-API-Key"),
    authorization: str | None = Header(None),
) -> str:
    """Verify API key for protected endpoints."""
    # Extract key from Authorization header if present
    api_key = x_api_key
    if not api_key and authorization:
        if authorization.startswith("Bearer "):
            api_key = authorization[7:]

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check against configured keys
    if settings.api_keys and api_key not in settings.api_keys:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key",
        )

    return api_key


async def get_current_user(api_key: str = Depends(verify_api_key)) -> dict:
    """Get current user from API key (placeholder)."""
    return {"api_key": api_key, "permissions": ["read", "write"]}


# Database session dependencies
def get_db_session() -> Generator[AsyncSession, None, None]:
    """Get database session (for sync compatibility)."""
    # This is a placeholder - actual async session is from get_db


# Common query parameters
class PaginationParams:
    def __init__(
        self,
        page: int = 1,
        page_size: int = 20,
    ):
        self.page = max(1, page)
        self.page_size = min(max(1, page_size), 100)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class DateRangeParams:
    def __init__(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ):
        self.start_date = start_date
        self.end_date = end_date
