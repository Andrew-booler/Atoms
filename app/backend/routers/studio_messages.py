import json
import logging
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from dependencies.auth import get_current_user
from schemas.auth import UserResponse
from services.studio_messages import Studio_messagesService

# Set up logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/entities/studio_messages", tags=["studio_messages"])


# ---------- Pydantic Schemas ----------
class Studio_messagesData(BaseModel):
    """Entity data schema (for create/update)"""
    project_id: int
    role: str
    kind: str = None
    content: str
    meta: str = None


class Studio_messagesUpdateData(BaseModel):
    """Update entity data (partial updates allowed)"""
    project_id: Optional[int] = None
    role: Optional[str] = None
    kind: Optional[str] = None
    content: Optional[str] = None
    meta: Optional[str] = None


class Studio_messagesResponse(BaseModel):
    """Entity response schema"""
    id: int
    user_id: str
    project_id: int
    role: str
    kind: Optional[str] = None
    content: str
    meta: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Studio_messagesListResponse(BaseModel):
    """List response schema"""
    items: List[Studio_messagesResponse]
    total: int
    skip: int
    limit: int


class Studio_messagesBatchCreateRequest(BaseModel):
    """Batch create request"""
    items: List[Studio_messagesData]


class Studio_messagesBatchUpdateItem(BaseModel):
    """Batch update item"""
    id: int
    updates: Studio_messagesUpdateData


class Studio_messagesBatchUpdateRequest(BaseModel):
    """Batch update request"""
    items: List[Studio_messagesBatchUpdateItem]


class Studio_messagesBatchDeleteRequest(BaseModel):
    """Batch delete request"""
    ids: List[int]


# ---------- Routes ----------
@router.get("", response_model=Studio_messagesListResponse)
async def query_studio_messagess(
    query: str = Query(None, description='Query conditions as JSON, e.g. {"id":2} or {"id":{"$gte":2}}'),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Query studio_messagess with filtering, sorting, and pagination (user can only see their own records)"""
    logger.debug(f"Querying studio_messagess: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")
    
    service = Studio_messagesService(db)
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
        logger.debug(f"Found {result['total']} studio_messagess")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid studio_messages query: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error querying studio_messagess: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/all", response_model=Studio_messagesListResponse)
async def query_studio_messagess_all(
    query: str = Query(None, description='Query conditions as JSON, e.g. {"id":2} or {"id":{"$gte":2}}'),
    sort: str = Query(None, description="Sort field (prefix with '-' for descending)"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(20, ge=1, le=2000, description="Max number of records to return"),
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    db: AsyncSession = Depends(get_db),
):
    # Query studio_messagess with filtering, sorting, and pagination without user limitation
    logger.debug(f"Querying studio_messagess: query={query}, sort={sort}, skip={skip}, limit={limit}, fields={fields}")

    service = Studio_messagesService(db)
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
        logger.debug(f"Found {result['total']} studio_messagess")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid studio_messages query: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error querying studio_messagess: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{id}", response_model=Studio_messagesResponse)
async def get_studio_messages(
    id: int,
    fields: str = Query(None, description="Comma-separated list of fields to return"),
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a single studio_messages by ID (user can only see their own records)"""
    logger.debug(f"Fetching studio_messages with id: {id}, fields={fields}")
    
    service = Studio_messagesService(db)
    try:
        result = await service.get_by_id(id, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Studio_messages with id {id} not found")
            raise HTTPException(status_code=404, detail="Studio_messages not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching studio_messages {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("", response_model=Studio_messagesResponse, status_code=201)
async def create_studio_messages(
    data: Studio_messagesData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new studio_messages"""
    logger.debug(f"Creating new studio_messages with data: {data}")
    
    service = Studio_messagesService(db)
    try:
        result = await service.create(data.model_dump(), user_id=str(current_user.id))
        if not result:
            raise HTTPException(status_code=400, detail="Failed to create studio_messages")
        
        logger.info(f"Studio_messages created successfully with id: {result.id}")
        return result
    except ValueError as e:
        logger.error(f"Validation error creating studio_messages: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating studio_messages: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.post("/batch", response_model=List[Studio_messagesResponse], status_code=201)
async def create_studio_messagess_batch(
    request: Studio_messagesBatchCreateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create multiple studio_messagess in a single request"""
    logger.debug(f"Batch creating {len(request.items)} studio_messagess")
    
    service = Studio_messagesService(db)
    results = []
    
    try:
        for item_data in request.items:
            result = await service.create(item_data.model_dump(), user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch created {len(results)} studio_messagess successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch create: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch create failed: {str(e)}")


@router.put("/batch", response_model=List[Studio_messagesResponse])
async def update_studio_messagess_batch(
    request: Studio_messagesBatchUpdateRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update multiple studio_messagess in a single request (requires ownership)"""
    logger.debug(f"Batch updating {len(request.items)} studio_messagess")
    
    service = Studio_messagesService(db)
    results = []
    
    try:
        for item in request.items:
            # Only include non-None values for partial updates
            update_dict = {k: v for k, v in item.updates.model_dump().items() if v is not None}
            result = await service.update(item.id, update_dict, user_id=str(current_user.id))
            if result:
                results.append(result)
        
        logger.info(f"Batch updated {len(results)} studio_messagess successfully")
        return results
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch update: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch update failed: {str(e)}")


@router.put("/{id}", response_model=Studio_messagesResponse)
async def update_studio_messages(
    id: int,
    data: Studio_messagesUpdateData,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an existing studio_messages (requires ownership)"""
    logger.debug(f"Updating studio_messages {id} with data: {data}")

    service = Studio_messagesService(db)
    try:
        # Only include non-None values for partial updates
        update_dict = {k: v for k, v in data.model_dump().items() if v is not None}
        result = await service.update(id, update_dict, user_id=str(current_user.id))
        if not result:
            logger.warning(f"Studio_messages with id {id} not found for update")
            raise HTTPException(status_code=404, detail="Studio_messages not found")
        
        logger.info(f"Studio_messages {id} updated successfully")
        return result
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error updating studio_messages {id}: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating studio_messages {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/batch")
async def delete_studio_messagess_batch(
    request: Studio_messagesBatchDeleteRequest,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete multiple studio_messagess by their IDs (requires ownership)"""
    logger.debug(f"Batch deleting {len(request.ids)} studio_messagess")
    
    service = Studio_messagesService(db)
    deleted_count = 0
    
    try:
        for item_id in request.ids:
            success = await service.delete(item_id, user_id=str(current_user.id))
            if success:
                deleted_count += 1
        
        logger.info(f"Batch deleted {deleted_count} studio_messagess successfully")
        return {"message": f"Successfully deleted {deleted_count} studio_messagess", "deleted_count": deleted_count}
    except Exception as e:
        await db.rollback()
        logger.error(f"Error in batch delete: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Batch delete failed: {str(e)}")


@router.delete("/{id}")
async def delete_studio_messages(
    id: int,
    current_user: UserResponse = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a single studio_messages by ID (requires ownership)"""
    logger.debug(f"Deleting studio_messages with id: {id}")
    
    service = Studio_messagesService(db)
    try:
        success = await service.delete(id, user_id=str(current_user.id))
        if not success:
            logger.warning(f"Studio_messages with id {id} not found for deletion")
            raise HTTPException(status_code=404, detail="Studio_messages not found")
        
        logger.info(f"Studio_messages {id} deleted successfully")
        return {"message": "Studio_messages deleted successfully", "id": id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting studio_messages {id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")