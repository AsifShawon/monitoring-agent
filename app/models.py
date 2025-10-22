"""Data models for the monitoring agent."""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Literal
from datetime import datetime
from bson import ObjectId


class PyObjectId(ObjectId):
    """Custom ObjectId type for Pydantic."""
    
    @classmethod
    def __get_validators__(cls):
        yield cls.validate
    
    @classmethod
    def validate(cls, v):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)
    
    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")


class UserPreferences(BaseModel):
    """User notification preferences."""
    notify_via: Literal["email", "console"] = "console"


class User(BaseModel):
    """User model."""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    email: EmailStr
    preferences: UserPreferences = UserPreferences()
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class UserCreate(BaseModel):
    """User creation model."""
    email: EmailStr
    preferences: Optional[UserPreferences] = None


class Target(BaseModel):
    """Monitoring target model."""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    url: str
    type: Literal["linkedin_profile", "linkedin_page", "website"]
    frequency: Literal["hourly", "daily", "weekly"] = "daily"
    last_checked: Optional[datetime] = None
    last_content: Optional[str] = None  # Store last content snapshot directly
    is_active: bool = True
    user_id: Optional[PyObjectId] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class TargetCreate(BaseModel):
    """Target creation model."""
    url: str
    type: Literal["linkedin_profile", "linkedin_page", "website"]
    frequency: Literal["hourly", "daily", "weekly"] = "daily"
    user_id: Optional[str] = None


class TargetUpdate(BaseModel):
    """Target update model."""
    frequency: Optional[Literal["hourly", "daily", "weekly"]] = None
    is_active: Optional[bool] = None


class Change(BaseModel):
    """Change detection model."""
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    target_id: PyObjectId
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    change_type: str
    summary: str
    before: Optional[str] = None
    after: Optional[str] = None
    severity: Literal["minor", "major", "critical"] = "minor"
    notified: bool = False
    
    class Config:
        populate_by_name = True
        arbitrary_types_allowed = True
        json_encoders = {ObjectId: str}


class ChangeResponse(BaseModel):
    """Change response model."""
    id: str
    target_id: str
    timestamp: datetime
    change_type: str
    summary: str
    severity: str
    target_url: Optional[str] = None


class TargetResponse(BaseModel):
    """Target response model."""
    id: str
    url: str
    type: str
    frequency: str
    last_checked: Optional[datetime]
    is_active: bool
    created_at: datetime

