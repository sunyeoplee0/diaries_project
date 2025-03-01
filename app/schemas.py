from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional
from models import ProcessingStatus
from typing import List, Optional



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
    followers_count: int
    following_count: int
    is_following: bool

    class Config:
        from_attributes = True

class DiaryCreate(BaseModel):
    title: str
    content: str
    date: datetime
    shared: bool = False

class DiaryUpdate(BaseModel):
    title: str
    content: str
    date: datetime
    shared: bool


class DiaryStatusResponse(BaseModel):
    diary_id: int
    status: ProcessingStatus
    emotion: Optional[str] = None
    image_url: Optional[str] = None
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
    shared: bool
    status_tracking: Optional[DiaryStatusResponse]

    class Config:
        from_attributes = True


class ImageGalleryResponse(BaseModel):
    id: int
    url: str
    emotion: str
    date: datetime
    content: Optional[str]
    title: str

    class Config:
        from_attributes = True

class EmotionStats(BaseModel):
    emotion: str
    count: int
    percentage: float

    class Config:
        from_attributes = True

class WritingStats(BaseModel):
    consecutive_days: int
    total_entries: int
    monthly_entries: int
    average_length: int

    class Config:
        from_attributes = True


class FollowResponse(BaseModel):
    id: int
    follower_id: int
    following_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileWithFollow(UserResponse):
    followers_count: int
    following_count: int
    is_following: bool

    class Config:
        from_attributes = True


class FeedDiaryResponse(DiaryResponse):
    user: UserResponse
    likes_count: int
    comments_count: int
    is_liked: bool

    class Config:
        from_attributes = True

class CommentCreate(BaseModel):
    content: str

class CommentUpdate(BaseModel):
    content: str

class CommentResponse(BaseModel):
    id: int
    content: str
    diary_id: int
    user_id: int
    user: UserResponse
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class UserProfileResponse(BaseModel):
    id: int
    email: EmailStr
    nickname: str
    profile_image_url: Optional[str] = None
    followers_count: int
    following_count: int
    is_following: bool

    class Config:
        from_attributes = True

class UserProfileStatsResponse(BaseModel):
    consecutive_days: int
    total_entries: int
    monthly_entries: int
    average_length: int
    followers_count: int
    following_count: int

    class Config:
        from_attributes = True