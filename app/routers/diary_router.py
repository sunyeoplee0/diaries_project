# routers/diary_router.py
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import datetime
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import SessionLocal
from models import Diary, User, DiaryStatus, ProcessingStatus, Tag
from schemas import DiaryCreate, DiaryUpdate, DiaryResponse, DiaryTagExtraction, DiaryCommentGeneration
from utils import verify_access_token, TokenError, extract_tags_from_diary, generate_diary_comment, find_similar_diaries

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


@router.post("/", response_model=DiaryResponse)
async def create_diary(
        diary_data: DiaryCreate,
        background_tasks: BackgroundTasks,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    # 새 일기 생성
    new_diary = Diary(
        title=diary_data.title,
        content=diary_data.content,
        date=diary_data.date,
        user_id=current_user.id
    )

    # 상태 추적 객체 생성
    new_diary_status = DiaryStatus(
        status=ProcessingStatus.QUEUED
    )

    new_diary.status_tracking = new_diary_status

    db.add(new_diary)
    db.commit()
    db.refresh(new_diary)

    # 백그라운드 태스크로 태그 추출 처리
    background_tasks.add_task(
        process_diary_tags,
        new_diary.id,
        new_diary.content,
        current_user.id
    )

    return new_diary


async def process_diary_tags(diary_id: int, content: str, user_id: int):
    """일기에서 태그를 추출하고 저장하는 백그라운드 프로세스"""
    db = SessionLocal()
    try:
        # 일기 상태 업데이트
        diary = db.query(Diary).filter(Diary.id == diary_id).first()
        if not diary:
            print(f"일기를 찾을 수 없음: {diary_id}")
            return

        # 상태 업데이트 - 분석 중
        if diary.status_tracking:
            diary.status_tracking.status = ProcessingStatus.ANALYZING
            diary.status_tracking.updated_at = datetime.utcnow()
            db.commit()

        # 태그 추출
        tags_data = await extract_tags_from_diary(content)

        # 태그 저장
        for tag_data in tags_data:
            # 기존 태그 확인
            tag = db.query(Tag).filter(Tag.name == tag_data["name"]).first()

            # 없으면 새로 생성
            if not tag:
                tag = Tag(
                    name=tag_data["name"],
                    category=tag_data.get("category")
                )
                db.add(tag)
                db.flush()

            # 일기와 태그 연결
            diary.tags.append(tag)

        # 감정 분석 (간단한 예시)
        positive_emotions = ["행복", "기쁨", "즐거움", "감사", "만족"]
        negative_emotions = ["슬픔", "우울", "불안", "분노", "좌절"]

        # 태그 기반 간단한 감정 분석
        emotion_tags = [tag_data["name"] for tag_data in tags_data]
        positive_count = sum(1 for emotion in positive_emotions if emotion in emotion_tags)
        negative_count = sum(1 for emotion in negative_emotions if emotion in emotion_tags)

        if positive_count > negative_count:
            diary.emotion = "긍정적"
        elif negative_count > positive_count:
            diary.emotion = "부정적"
        else:
            diary.emotion = "중립적"

        # 상태 업데이트 - 완료
        if diary.status_tracking:
            diary.status_tracking.status = ProcessingStatus.COMPLETED
            diary.status_tracking.updated_at = datetime.utcnow()

        db.commit()
        print(f"일기 ID {diary_id}의 태그 추출 완료")

    except Exception as e:
        # 오류 발생 시 상태 업데이트
        if diary and diary.status_tracking:
            diary.status_tracking.status = ProcessingStatus.FAILED
            diary.status_tracking.updated_at = datetime.utcnow()
            db.commit()

        print(f"태그 추출 중 오류 발생: {str(e)}")
    finally:
        db.close()


@router.post("/{diary_id}/comment", response_model=DiaryResponse)
async def generate_comment(
        diary_id: int,
        comment_data: DiaryCommentGeneration,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    # 일기 확인
    diary = db.query(Diary).filter(
        Diary.id == diary_id,
        Diary.user_id == current_user.id
    ).first()

    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="일기를 찾을 수 없습니다."
        )

    # 태그 추출이 완료되었는지 확인
    if (not diary.status_tracking or
            diary.status_tracking.status != ProcessingStatus.COMPLETED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="태그 추출이 완료되지 않았습니다. 잠시 후 다시 시도해 주세요."
        )

    # 태그 이름 목록 추출
    diary_tags = [tag.name for tag in diary.tags]

    # 유사한 일기 찾기
    similar_diaries = find_similar_diaries(
        db,
        diary_id,
        current_user.id,
        diary_tags,
        min_matching_tags=2,
        limit=comment_data.similar_diaries_count
    )

    # 유사한 일기가 없는 경우
    if not similar_diaries:
        # 유사한 일기 없이 코멘트 생성
        comment = await generate_diary_comment(diary.content, [])
    else:
        # 유사한 일기의 내용만 추출
        similar_contents = [content for _, content in similar_diaries]

        # 코멘트 생성
        comment = await generate_diary_comment(diary.content, similar_contents)

    # 코멘트 저장
    diary.ai_comment = comment
    db.commit()
    db.refresh(diary)

    return diary


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

    # 기존 태그 연결 제거
    diary.tags = []

    # 일기 내용 업데이트
    diary.title = diary_data.title
    diary.content = diary_data.content
    diary.date = diary_data.date
    diary.updated_at = datetime.utcnow()

    # 상태 초기화
    if diary.status_tracking:
        diary.status_tracking.status = ProcessingStatus.QUEUED
        diary.status_tracking.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(diary)

    # 태그 재추출
    background_tasks.add_task(
        process_diary_tags,
        diary.id,
        diary.content,
        current_user.id
    )

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