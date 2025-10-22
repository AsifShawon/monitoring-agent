"""Simplified API routes for monitoring agent."""
from fastapi import APIRouter, HTTPException, Depends, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import List, Optional
from bson import ObjectId
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field
import logging
import json

from app.database import get_database

logger = logging.getLogger(__name__)

router = APIRouter()

class UserSignup(BaseModel):
    """User signup model."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    """User response model."""
    id: str
    username: str
    email: str
    full_name: Optional[str] = None
    created_at: datetime
    is_active: bool


class TargetCreate(BaseModel):
    """Target creation model."""
    url: str = Field(..., description="URL to monitor")
    type: str = Field(..., description="linkedin_profile, linkedin_company, or website")
    frequency: str = Field(default="daily", description="hourly, daily, or weekly")
    description: Optional[str] = Field(None, description="Optional description")


class TargetResponse(BaseModel):
    """Target response model."""
    id: str
    user_id: str
    url: str
    type: str
    frequency: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    last_checked: Optional[datetime] = None


class ChangeResponse(BaseModel):
    """Change response model."""
    id: str
    target_id: str
    timestamp: datetime
    severity: str
    summary: str
    key_changes: Optional[List[str]] = None
    notified: bool = False


# USER ROUTES
@router.post("/users/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup_user(
    user: UserSignup,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Register a new user."""
    
    existing_user = await db.users.find_one({"username": user.username})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Check if email exists
    existing_email = await db.users.find_one({"email": user.email})
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    user_dict = {
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "created_at": datetime.utcnow(),
        "is_active": True
    }
    
    result = await db.users.insert_one(user_dict)
    
    created_user = await db.users.find_one({"_id": result.inserted_id})
    
    return UserResponse(
        id=str(created_user["_id"]),
        username=created_user["username"],
        email=created_user["email"],
        full_name=created_user.get("full_name"),
        created_at=created_user["created_at"],
        is_active=created_user["is_active"]
    )


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get user details by ID."""
    
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return UserResponse(
        id=str(user["_id"]),
        username=user["username"],
        email=user["email"],
        full_name=user.get("full_name"),
        created_at=user["created_at"],
        is_active=user["is_active"]
    )


# TARGET ROUTES
@router.post("/users/{user_id}/targets", response_model=TargetResponse, status_code=status.HTTP_201_CREATED)
async def create_target(
    user_id: str,
    target: TargetCreate,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Create a monitoring target for a user."""
    
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    valid_types = ["linkedin_profile", "linkedin_company", "linkedin_page", "website"]
    if target.type not in valid_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid type. Must be one of: {', '.join(valid_types)}"
        )
    
    valid_frequencies = ["hourly", "daily", "weekly"]
    if target.frequency not in valid_frequencies:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid frequency. Must be one of: {', '.join(valid_frequencies)}"
        )
    
    existing = await db.targets.find_one({
        "user_id": ObjectId(user_id),
        "url": target.url
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You are already monitoring this URL"
        )
    
    # Create target
    target_dict = {
        "user_id": ObjectId(user_id),
        "url": target.url,
        "type": target.type,
        "frequency": target.frequency,
        "description": target.description,
        "is_active": True,
        "created_at": datetime.utcnow(),
        "last_checked": None,
        "last_content": None
    }
    
    result = await db.targets.insert_one(target_dict)
    
    created_target = await db.targets.find_one({"_id": result.inserted_id})
    
    try:
        from app.agents.scraper_agent import scrape_target
        scrape_target.delay(
            target_id=str(created_target["_id"]),
            url=created_target["url"],
            target_type=created_target["type"]
        )
    except Exception as e:
        logger.warning(f"Failed to trigger immediate scrape: {e}")
    
    return TargetResponse(
        id=str(created_target["_id"]),
        user_id=str(created_target["user_id"]),
        url=created_target["url"],
        type=created_target["type"],
        frequency=created_target["frequency"],
        description=created_target.get("description"),
        is_active=created_target["is_active"],
        created_at=created_target["created_at"],
        last_checked=created_target.get("last_checked")
    )


@router.get("/users/{user_id}/targets", response_model=List[TargetResponse])
async def list_user_targets(
    user_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """List all monitoring targets for a user."""
    
    try:
        user_obj_id = ObjectId(user_id)
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    targets = await db.targets.find({"user_id": user_obj_id}).to_list(length=100)
    
    return [
        TargetResponse(
            id=str(target["_id"]),
            user_id=str(target["user_id"]),
            url=target["url"],
            type=target["type"],
            frequency=target["frequency"],
            description=target.get("description"),
            is_active=target["is_active"],
            created_at=target["created_at"],
            last_checked=target.get("last_checked")
        )
        for target in targets
    ]


@router.get("/targets/{target_id}", response_model=TargetResponse)
async def get_target(
    target_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get target details by ID."""
    
    try:
        target = await db.targets.find_one({"_id": ObjectId(target_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid target ID format"
        )
    
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found"
        )
    
    return TargetResponse(
        id=str(target["_id"]),
        user_id=str(target["user_id"]),
        url=target["url"],
        type=target["type"],
        frequency=target["frequency"],
        description=target.get("description"),
        is_active=target["is_active"],
        created_at=target["created_at"],
        last_checked=target.get("last_checked")
    )


@router.delete("/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_target(
    target_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Delete a monitoring target."""
    
    try:
        result = await db.targets.delete_one({"_id": ObjectId(target_id)})
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid target ID format"
        )
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target not found"
        )
    
    return None


# CHANGE ROUTES
@router.get("/targets/{target_id}/changes", response_model=List[ChangeResponse])
async def get_target_changes(
    target_id: str,
    limit: int = 10,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get change history for a target."""
    
    try:
        target_obj_id = ObjectId(target_id)
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid target ID format"
        )
    
    changes = await db.changes.find(
        {"target_id": target_obj_id}
    ).sort("timestamp", -1).limit(limit).to_list(length=limit)
    
    return [
        ChangeResponse(
            id=str(change["_id"]),
            target_id=str(change["target_id"]),
            timestamp=change["timestamp"],
            severity=change.get("severity", "unknown"),
            summary=change.get("summary", ""),
            key_changes=change.get("key_changes", []),
            notified=change.get("notified", False)
        )
        for change in changes
    ]


@router.get("/users/{user_id}/changes", response_model=List[ChangeResponse])
async def get_all_user_changes(
    user_id: str,
    limit: int = 20,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """Get all changes for all user's targets."""
    
    try:
        user_obj_id = ObjectId(user_id)
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    targets = await db.targets.find({"user_id": user_obj_id}).to_list(length=100)
    target_ids = [target["_id"] for target in targets]
    
    changes = await db.changes.find(
        {"target_id": {"$in": target_ids}}
    ).sort("timestamp", -1).limit(limit).to_list(length=limit)
    
    return [
        ChangeResponse(
            id=str(change["_id"]),
            target_id=str(change["target_id"]),
            timestamp=change["timestamp"],
            severity=change.get("severity", "unknown"),
            summary=change.get("summary", ""),
            key_changes=change.get("key_changes", []),
            notified=change.get("notified", False)
        )
        for change in changes
    ]


# HEALTH CHECK
@router.get("/health")
async def health_check(db: AsyncIOMotorDatabase = Depends(get_database)):
    """Health check endpoint."""
    try:
        await db.command("ping")
        return {
            "status": "healthy",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connection failed: {str(e)}"
        )

