# routers/diary_router.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import SessionLocal
from models import Diary, User, DiaryStatus, ProcessingStatus
from schemas import DiaryCreate, DiaryUpdate, DiaryResponse, DiaryStatusResponse
from utils import verify_access_token, analyze_emotion_and_get_image, TokenError, get_diary_status_from_ai_server
import requests

router = APIRouter(prefix="/diaries", tags=["Diary"])
http_bearer = HTTPBearer()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
        db: Session = Depends(get_db)
):
    try:
        payload = verify_access_token(credentials.credentials)
        user_id = payload.get("user_id")
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="존재하지 않는 유저입니다."
            )
        return user
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )

def update_status(diary_id: int, status: ProcessingStatus, error: str = None, emotion: str = None,
                  image_url: str = None):
    try:
        data = {
            "status": status.value,
            "error": error,
            "emotion": emotion,
            "image_url": image_url
        }

        response = requests.post(
            f"https://daily-momento.duckdns.org:20929/api/status/{diary_id}",
            headers={"X-API-KEY": 'daily-momento_hyupsung_computer_engineering'},
            json=data,
            verify=True
        )
        response.raise_for_status()
        if response.status_code == 200:
            print("Status updated successfully:", status.value)
            print("Response:", response.json())
    except Exception as e:
        print("Failed to update status:", str(e))
        if hasattr(e, 'response'):
            print("Response status code:", e.response.status_code)
            print("Response text:", e.response.text)


async def process_diary_content(db: Session, diary_id: int):
    status = None

    try:
        print(f"Starting process for diary {diary_id}")
        diary = db.query(Diary).filter(Diary.id == diary_id).first()
        if not diary:
            return

        result = analyze_emotion_and_get_image(diary.id, diary.content)

        diary.emotion = result.get("emotion")
        diary.image_url = result.get("image_url")

        status = db.query(DiaryStatus).filter(DiaryStatus.diary_id == diary_id).first()
        if status:
            status.status = result.get("status", ProcessingStatus.COMPLETED)
            status.updated_at = datetime.utcnow()

        db.commit()
    except Exception as e:
        status = db.query(DiaryStatus).filter(DiaryStatus.diary_id == diary_id).first()
        if status:
            status.status = ProcessingStatus.FAILED
            status.updated_at = datetime.utcnow()
            db.commit()
        print(f"Error processing diary {diary_id}: {str(e)}")


@router.post("/", response_model=DiaryResponse)
async def create_diary(
        diary_data: DiaryCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    new_diary = Diary(
        title=diary_data.title,
        content=diary_data.content,
        date=diary_data.date,
        user_id=current_user.id,
        shared=diary_data.shared
    )
    db.add(new_diary)
    db.flush()

    update_status(new_diary.id, ProcessingStatus.QUEUED)
    status = DiaryStatus(
        diary_id=new_diary.id,
        status=ProcessingStatus.QUEUED
    )
    db.add(status)
    db.commit()
    db.refresh(new_diary)

    background_tasks.add_task(process_diary_content, db, new_diary.id)
    return new_diary


@router.get("/", response_model=List[DiaryResponse])
def get_all_diaries(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    diaries = db.query(Diary).filter(
        Diary.user_id == current_user.id
    ).all()
    return diaries


@router.get("/{diary_id}", response_model=DiaryResponse)
def get_diary(
        diary_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    diary = db.query(Diary).filter(
        Diary.id == diary_id,
        Diary.user_id == current_user.id
    ).first()
    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="일기를 찾을 수 없습니다."
        )
    return diary


@router.get("/status/{diary_id}", response_model=DiaryStatusResponse)
def get_diary_status(
        diary_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    diary = db.query(Diary).filter(
        Diary.id == diary_id,
        Diary.user_id == current_user.id
    ).first()

    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="일기를 찾을 수 없습니다."
        )

    try:
        ai_status = get_diary_status_from_ai_server(diary_id)
        status = db.query(DiaryStatus).filter(
            DiaryStatus.diary_id == diary_id
        ).first()

        if status:
            status.status = ai_status["status"]
            status.updated_at = datetime.utcnow()

            if ai_status["status"] == "COMPLETED" and diary.emotion is None:
                diary.emotion = ai_status.get("emotion")
                diary.image_url = ai_status.get("image_url")
                diary.updated_at = datetime.utcnow()

            db.commit()
            db.refresh(status)
            db.refresh(diary)

        return DiaryStatusResponse(
            diary_id=diary_id,
            status=ai_status["status"],
            emotion=ai_status.get("emotion"),
            image_url=ai_status.get("image_url"),
            created_at=diary.created_at,
            updated_at=diary.updated_at
        )

    except HTTPException as e:
        print(f"Error checking status: {str(e)}")
        raise e


@router.put("/{diary_id}", response_model=DiaryResponse)
async def update_diary(
        diary_id: int,
        diary_data: DiaryUpdate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    diary = db.query(Diary).filter(
        Diary.id == diary_id,
        Diary.user_id == current_user.id
    ).first()

    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="일기를 찾을 수 없습니다."
        )

    diary.title = diary_data.title
    diary.content = diary_data.content
    diary.date = diary_data.date
    diary.shared = diary_data.shared
    diary.updated_at = datetime.utcnow()

    update_status(diary_id, ProcessingStatus.QUEUED)
    if diary.status_tracking:
        diary.status_tracking.status = ProcessingStatus.QUEUED
        diary.status_tracking.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(diary)

    background_tasks.add_task(process_diary_content, db, diary_id)
    return diary


@router.delete("/{diary_id}")
def delete_diary(
        diary_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    diary = db.query(Diary).filter(
        Diary.id == diary_id,
        Diary.user_id == current_user.id
    ).first()

    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="일기를 찾을 수 없습니다."
        )

    db.delete(diary)
    db.commit()
    return {"message": "일기가 삭제되었습니다."}

