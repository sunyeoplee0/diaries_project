from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional, List
from models import ProcessingStatus

class UserProfileUpdate(BaseModel):
    nickname: Optional[str] = None
    email: Optional[EmailStr] = None
    profile_image_url: Optional[str] = None

    class Config:
        from_attributes = True

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    nickname: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    nickname: str
    profile_image_url: Optional[str] = None

    class Config:
        from_attributes = True

class TagBase(BaseModel):
    name: str
    category: Optional[str] = None

class TagCreate(TagBase):
    pass

class TagResponse(TagBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class DiaryCreate(BaseModel):
    title: str
    content: str
    date: datetime

class DiaryUpdate(BaseModel):
    title: str
    content: str
    date: datetime

class DiaryStatusResponse(BaseModel):
    diary_id: int
    status: ProcessingStatus
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class DiaryResponse(BaseModel):
    id: int
    title: str
    content: str
    date: datetime
    created_at: datetime
    updated_at: datetime
    user_id: int
    emotion: Optional[str]
    image_url: Optional[str]
    ai_comment: Optional[str]
    status_tracking: Optional[DiaryStatusResponse]
    tags: List[TagResponse] = []

    class Config:
        from_attributes = True

class DiaryTagExtraction(BaseModel):
    diary_id: int
    content: str

class DiaryCommentGeneration(BaseModel):
    diary_id: int
    similar_diaries_count: int = Field(default=3, ge=1, le=10)