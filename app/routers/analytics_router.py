# routers/analytics_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, timedelta
from database import SessionLocal
from models import Diary, User, Follow
from schemas import ImageGalleryResponse, EmotionStats, UserProfileStatsResponse
from .diary_router import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# routers/analytics_router.py 이어서

@router.get("/images", response_model=List[ImageGalleryResponse])
def get_user_images(
        emotion: Optional[str] = None,  # 감정별 필터링 추가
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    query = db.query(Diary).filter(
        Diary.user_id == current_user.id,
        Diary.image_url.isnot(None),
        Diary.status_tracking.has(status='COMPLETED')
    )

    # 감정별 필터링
    if emotion:
        query = query.filter(Diary.emotion == emotion)

    diaries = query.order_by(Diary.date.desc()).all()

    return [
        ImageGalleryResponse(
            id=diary.id,
            url=diary.image_url,
            emotion=diary.emotion,
            date=diary.date,
            content=diary.content,
            title=diary.title
        ) for diary in diaries
    ]


@router.get("/images/{diary_id}", response_model=ImageGalleryResponse)
def get_image_detail(
        diary_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    diary = db.query(Diary).filter(
        Diary.id == diary_id,
        Diary.user_id == current_user.id
    ).first()

    if not diary or not diary.image_url:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="이미지를 찾을 수 없습니다."
        )

    return ImageGalleryResponse(
        id=diary.id,
        url=diary.image_url,
        emotion=diary.emotion,
        date=diary.date,
        content=diary.content,
        title=diary.title
    )

@router.get("/emotions", response_model=List[EmotionStats])
def get_emotion_stats(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    # 감정이 있는 일기만 조회
    diaries = db.query(Diary).filter(
        Diary.user_id == current_user.id,
        Diary.emotion.isnot(None)
    ).all()

    # 감정별 카운트 계산
    emotion_counts = {}
    total_count = len(diaries)

    for diary in diaries:
        emotion = diary.emotion
        emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1

    # 통계 생성
    stats = []
    for emotion, count in emotion_counts.items():
        percentage = (count / total_count * 100) if total_count > 0 else 0
        stats.append(EmotionStats(
            emotion=emotion,
            count=count,
            percentage=round(percentage, 1)
        ))

    return sorted(stats, key=lambda x: x.count, reverse=True)


@router.get("/stats", response_model=UserProfileStatsResponse)
def get_writing_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 전체 일기 조회
    diaries = db.query(Diary).filter(
        Diary.user_id == current_user.id
    ).order_by(Diary.date.desc()).all()

    now = datetime.utcnow()

    # 이번 달 일기 수
    monthly_entries = db.query(Diary).filter(
        Diary.user_id == current_user.id,
        func.extract('month', Diary.date) == now.month,
        func.extract('year', Diary.date) == now.year
    ).count()

    # 팔로워/팔로잉 수 계산
    followers_count = db.query(Follow).filter(
        Follow.following_id == current_user.id
    ).count()
    following_count = db.query(Follow).filter(
        Follow.follower_id == current_user.id
    ).count()

    # 총 일기 수
    total_entries = len(diaries)

    # 연속 작성일 계산
    consecutive_days = 0
    if diaries:
        current_date = now.date()
        diary_dates = set(d.date.date() for d in diaries)

        while (current_date - timedelta(days=consecutive_days)) in diary_dates:
            consecutive_days += 1

    # 평균 글자 수
    total_length = sum(len(d.content) for d in diaries)
    average_length = total_length // total_entries if total_entries > 0 else 0

    return {
        "consecutive_days": consecutive_days,
        "total_entries": total_entries,
        "monthly_entries": monthly_entries,
        "average_length": average_length,
        "followers_count": followers_count,
        "following_count": following_count
    }
