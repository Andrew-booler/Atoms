import json
import logging
from typing import List, Optional

from datetime import datetime, date

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from services.studio_versions import Studio_versionsService
from dependencies.auth import get_current_user
from schemas.auth import UserResponse

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/studio_versions", tags=["studio_versions"])


# ---------- Pydantic Schemas ----------
class Studio_versionsData(BaseModel):
    """Entity data schema (for create/update)"""
    project_id: int
    version_no: int
    label: str = None
    plan_summary: str = None
    artifact_html: str


class Studio_versionsUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    project_id: Optional[int] = None
    version_no: Optional[int] = None
    label: Optional[str] = None
    plan_summary: Optional[str] = None
    artifact_html: Optional[str] = None


class Studio_versionsResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    project_id: int
    version_no: int
    label: Optional[str] = None
    plan_summary: Optional[str] = None
    artifact_html: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Studio_versionsListResponse(BaseModel):
    """List response schema"""
    items: List[Studio_versionsResponse]
    total: int
    skip: int
    limit: int


class Studio_versionsBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Studio_versionsData]


class Studio_versionsBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Studio_versionsUpdateData


class Studio_versionsBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Studio_versionsBatchUpdateItem]


class Studio_versionsBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=Studio_versionsListResponse)
async def query_studio_versionss(
    query: str = Query(None, description='Query conditions as JSON, e.g. {"id":2} or {"id":{"$gte":2}}'),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query studio_versionss with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying studio_versionss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Studio_versionsService(db)
    try:
        # Parse query JSON if provided
        query_dict = None
        if query:
            try:
                query_dict = json.loads(query)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid query JSON format")
        
        result = await service.get_list(
            skip=skip, 
            limit=limit,
            query_dict=query_dict,
            sort=sort,
            user_id=str(current_user.id),
        )
        logger.debug(f"Found {result['total']} studio_versionss")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid studio_versions query: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error querying studio_versionss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Studio_versionsListResponse)
async def query_studio_versionss_all(
    query: str = Query(None, description='Query conditions as JSON, e.g. {"id":2} or {"id":{"$gte":2}}'),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    # Query studio_versionss with filtering, sorting, and pagination without user limitation
    logger.debug(f"Querying studio_versionss: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Studio_versionsService(db)
    try:
        # Parse query JSON if provided
        query_dict = None
        if query:
            try:
                query_dict = json.loads(query)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="Invalid query JSON format")

        result = await service.get_list(
            skip=skip,
            limit=limit,
            query_dict=query_dict,
            sort=sort
        )
        logger.debug(f"Found {result['total']} studio_versionss")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid studio_versions query: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error querying studio_versionss: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Studio_versionsResponse)
async def get_studio_versions(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single studio_versions by ID (user can only see their own records)"""
    logger.debug(f"Fetching studio_versions with id: {id}, fields={fields}")
    
    service = Studio_versionsService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Studio_versions with id {id} not found")
            raise HTTPException(status_code=404, detail="Studio_versions not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching studio_versions {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Studio_versionsResponse, status_code=201)
async def create_studio_versions(
    data: Studio_versionsData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new studio_versions"""
    logger.debug(f"Creating new studio_versions with data: {data}")
    
    service = Studio_versionsService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create studio_versions")
        
        logger.info(f"Studio_versions created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating studio_versions: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating studio_versions: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Studio_versionsResponse], status_code=201)
async def create_studio_versionss_batch(
    request: Studio_versionsBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple studio_versionss in a single request"""
    logger.debug(f"Batch creating {len(request.items)} studio_versionss")
    
    service = Studio_versionsService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} studio_versionss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Studio_versionsResponse])
async def update_studio_versionss_batch(
    request: Studio_versionsBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple studio_versionss in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} studio_versionss")
    
    service = Studio_versionsService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} studio_versionss successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=Studio_versionsResponse)
async def update_studio_versions(
    id: int,
    data: Studio_versionsUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing studio_versions (requires ownership)"""
    logger.debug(f"Updating studio_versions {id} with data: {data}")

    service = Studio_versionsService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Studio_versions with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Studio_versions not found")
        
        logger.info(f"Studio_versions {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating studio_versions {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating studio_versions {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_studio_versionss_batch(
    request: Studio_versionsBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple studio_versionss by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} studio_versionss")
    
    service = Studio_versionsService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} studio_versionss successfully")
        return {"message": f"Successfully deleted {deleted_count} studio_versionss", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_studio_versions(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single studio_versions by ID (requires ownership)"""
    logger.debug(f"Deleting studio_versions with id: {id}")
    
    service = Studio_versionsService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Studio_versions with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Studio_versions not found")
        
        logger.info(f"Studio_versions {id} deleted successfully")
        return {"message": "Studio_versions deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting studio_versions {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")