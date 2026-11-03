from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db

# Database session dependency
DbSession = Annotated[AsyncSession, Depends(get_db)]
