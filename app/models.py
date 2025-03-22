from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, Enum, Boolean, Table
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

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

# 일기-태그 다대다 관계 테이블
diary_tag = Table(
    "diary_tag",
    Base.metadata,
    Column("diary_id", Integer, ForeignKey("diaries.id"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("tags.id"), primary_key=True)
)

class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False, unique=True)
    category = Column(String(50), nullable=True)  # 취미, 고민거리, 생활습관 등의 카테고리
    created_at = Column(DateTime, default=datetime.utcnow)

    diaries = relationship("Diary", secondary=diary_tag, back_populates="tags")

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
    ai_comment = Column(Text, nullable=True)  # AI가 생성한 코멘트 저장

    owner = relationship("User", back_populates="diaries")
    status_tracking = relationship("DiaryStatus", back_populates="diary", uselist=False, cascade="all, delete-orphan")
    tags = relationship("Tag", secondary=diary_tag, back_populates="diaries")

class DiaryStatus(Base):
    __tablename__ = "diary_status"

    diary_id = Column(Integer, ForeignKey("diaries.id"), primary_key=True)
    status = Column(Enum(ProcessingStatus), nullable=False, default=ProcessingStatus.QUEUED)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    diary = relationship("Diary", back_populates="status_tracking")