from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Enum, Boolean
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum
import pytz

Base = declarative_base()

class ProcessingStatus(str, enum.Enum):
    QUEUED = "QUEUED"
    ANALYZING = "ANALYZING"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(100), unique=True, nullable=False)
    password = Column(String(200), nullable=False)
    nickname = Column(String(50), nullable=False)
    profile_image_url = Column(String(300), nullable=True)

    diaries = relationship("Diary", back_populates="owner", cascade="all, delete-orphan")

class Diary(Base):
    __tablename__ = "diaries"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    date = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    user_id = Column(Integer, ForeignKey("users.id"))
    emotion = Column(String(50), nullable=True)
    image_url = Column(String(300), nullable=True)
    shared = Column(Boolean, default=False)  # 추가

    owner = relationship("User", back_populates="diaries")
    status_tracking = relationship("DiaryStatus", back_populates="diary", uselist=False, cascade="all, delete-orphan")


class DiaryStatus(Base):
    __tablename__ = "diary_status"

    diary_id = Column(Integer, ForeignKey("diaries.id"), primary_key=True)
    status = Column(Enum(ProcessingStatus), nullable=False, default=ProcessingStatus.QUEUED)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    diary = relationship("Diary", back_populates="status_tracking")


class Follow(Base):
    __tablename__ = "follows"

    id = Column(Integer, primary_key=True, index=True)
    follower_id = Column(Integer, ForeignKey("users.id"))
    following_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    follower = relationship("User", foreign_keys=[follower_id], backref="following")
    following = relationship("User", foreign_keys=[following_id], backref="followers")


class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    diary_id = Column(Integer, ForeignKey("diaries.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=datetime.utcnow)

    diary = relationship("Diary", backref="likes")
    user = relationship("User", backref="likes")


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(Text, nullable=False)
    diary_id = Column(Integer, ForeignKey("diaries.id", ondelete="CASCADE"))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Seoul')))
    updated_at = Column(DateTime, default=lambda: datetime.now(pytz.timezone('Asia/Seoul')),
                        onupdate=lambda: datetime.now(pytz.timezone('Asia/Seoul')))

    diary = relationship("Diary", backref="comments")
    user = relationship("User", backref="comments")