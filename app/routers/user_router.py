import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Header, UploadFile, File
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List
from database import SessionLocal
from models import User, Follow, Like, Diary, Comment, DiaryStatus
from schemas import UserCreate, UserLogin, UserResponse, UserProfileUpdate, PasswordChange, UserProfileResponse, FeedDiaryResponse
from utils import create_access_token, create_refresh_token, verify_refresh_token, TokenError

from .diary_router import get_current_user

router = APIRouter(prefix="/user", tags=["User"])

http_bearer = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


UPLOAD_DIR = "static/profile_images"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/signup")
def signup(user_data: UserCreate, db: Session = Depends(get_db)):
    # 이메일 중복 확인
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 가입된 이메일입니다."
        )

    # 비밀번호 해싱
    hashed_password = pwd_context.hash(user_data.password)

    # 새 사용자 생성
    new_user = User(
        email=user_data.email,
        password=hashed_password,
        nickname=user_data.nickname
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 토큰 생성
    access_token = create_access_token({"user_id": new_user.id})
    refresh_token = create_refresh_token({"user_id": new_user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/signin")
def signin(user_data: UserLogin, db: Session = Depends(get_db)):
    # 사용자 확인
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user or not pwd_context.verify(user_data.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다."
        )

    # 토큰 생성
    access_token = create_access_token({"user_id": user.id})
    refresh_token = create_refresh_token({"user_id": user.id})

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }


@router.post("/token/refresh")
def refresh_token(
        credentials: HTTPAuthorizationCredentials = Depends(http_bearer),
        db: Session = Depends(get_db)
):
    refresh_token = credentials.credentials

    try:
        # 리프레시 토큰 검증
        payload = verify_refresh_token(refresh_token)
        user_id = payload.get("user_id")

        # 사용자 존재 여부 확인
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="존재하지 않는 사용자입니다."
            )

        # 새 토큰 생성
        new_access_token = create_access_token({"user_id": user_id})
        new_refresh_token = create_refresh_token({"user_id": user_id})

        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
            "token_type": "bearer"
        }
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )


@router.post("/signout")
def signout(credentials: HTTPAuthorizationCredentials = Depends(http_bearer)):
    # 실제 토큰 무효화는 클라이언트 측에서 처리
    return {"message": "로그아웃 되었습니다"}


@router.post("/profile/image")
async def upload_profile_image(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user)
):
    try:
        print(f"Received file: {file.filename}")
        print(f"Content type: {file.content_type}")

        ext = file.filename.split('.')[-1]
        if ext.lower() not in ['jpg', 'jpeg', 'png']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="지원하지 않는 파일 형식입니다."
            )

        file_name = f"{current_user.id}_{int(datetime.now().timestamp())}.{ext}"
        file_path = os.path.join(UPLOAD_DIR, file_name)

        print(f"Saving file to: {file_path}")

        content = await file.read()
        print(f"File size: {len(content)} bytes")

        with open(file_path, "wb") as buffer:
            buffer.write(content)

        base_url = "https://daily-momento.duckdns.org"
        image_url = f"{base_url}/static/profile_images/{file_name}"
        print(f"Image URL: {image_url}")

        return {"image_url": image_url}

    except Exception as e:
        print(f"Error uploading image: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.get("/profile", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # 팔로워/팔로잉 수 계산
    followers_count = db.query(Follow).filter(
        Follow.following_id == current_user.id
    ).count()
    following_count = db.query(Follow).filter(
        Follow.follower_id == current_user.id
    ).count()

    # 자기 자신의 프로필을 볼 때는 is_following이 항상 False
    is_following = False

    return {
        'id': current_user.id,
        'email': current_user.email,
        'nickname': current_user.nickname,
        'profile_image_url': current_user.profile_image_url,
        'followers_count': followers_count,
        'following_count': following_count,
        'is_following': is_following
    }


@router.put("/profile", response_model=UserResponse)
def update_profile(
    user_data: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        # 현재 세션에서 사용자 다시 가져오기
        user = db.query(User).filter(User.id == current_user.id).first()

        # 이메일 변경 시 중복 체크
        if user_data.email and user_data.email != user.email:
            existing_user = db.query(User).filter(User.email == user_data.email).first()
            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="이미 사용 중인 이메일입니다."
                )
            user.email = user_data.email

        # 닉네임 변경
        if user_data.nickname:
            user.nickname = user_data.nickname

        # 프로필 이미지 URL 변경
        if user_data.profile_image_url:
            user.profile_image_url = user_data.profile_image_url

        db.commit()
        db.refresh(user)

        # 팔로워/팔로잉 수 계산
        followers_count = db.query(Follow).filter(
            Follow.following_id == user.id
        ).count()
        following_count = db.query(Follow).filter(
            Follow.follower_id == user.id
        ).count()

        # 자기 자신의 프로필을 수정할 때는 is_following이 항상 False
        is_following = False

        return {
            'id': user.id,
            'email': user.email,
            'nickname': user.nickname,
            'profile_image_url': user.profile_image_url,
            'followers_count': followers_count,
            'following_count': following_count,
            'is_following': is_following
        }

    except Exception as e:
        db.rollback()
        print(f"Error updating profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@router.put("/password")
def change_password(
        password_data: PasswordChange,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    try:
        # 현재 비밀번호 확인
        if not pwd_context.verify(password_data.current_password, current_user.password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="현재 비밀번호가 일치하지 않습니다."
            )

        print("비밀번호 변경 중")
        # 새 비밀번호로 업데이트
        user = db.query(User).filter(User.id == current_user.id).first()
        user.password = pwd_context.hash(password_data.new_password)
        db.commit()
        db.refresh(user)
        print("비밀번호 변경 성공:", password_data.new_password)
        return {"message": "비밀번호가 변경되었습니다."}
    except Exception as e:
        print("비밀번호 변경 실패:", e)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )



# api_user_router.py에 추가
@router.get("/search")
async def search_users(
        query: str,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    users = db.query(User).filter(
        User.nickname.ilike(f"%{query}%"),
        User.id != current_user.id
    ).all()

    # 각 사용자에 대해 팔로우 상태 확인
    results = []
    for user in users:
        is_following = db.query(Follow).filter(
            Follow.follower_id == current_user.id,
            Follow.following_id == user.id
        ).first() is not None

        followers_count = db.query(Follow).filter(
            Follow.following_id == user.id
        ).count()

        following_count = db.query(Follow).filter(
            Follow.follower_id == user.id
        ).count()

        user_dict = {
            "id": user.id,
            "nickname": user.nickname,
            "email": user.email,
            "profile_image_url": user.profile_image_url,
            "is_following": is_following,
            "followers_count": followers_count,
            "following_count": following_count
        }
        results.append(user_dict)

    return results


@router.get("/{user_id}/profile", response_model=UserProfileResponse)
async def get_user_profile(
        user_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    followers_count = db.query(Follow).filter(
        Follow.following_id == user_id
    ).count()

    following_count = db.query(Follow).filter(
        Follow.follower_id == user_id
    ).count()

    is_following = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first() is not None

    return {
        "id": user.id,
        "email": user.email,
        "nickname": user.nickname,
        "profile_image_url": user.profile_image_url,
        "followers_count": followers_count,
        "following_count": following_count,
        "is_following": is_following
    }


@router.get("/{user_id}/diaries", response_model=List[FeedDiaryResponse])
async def get_user_diaries(
        user_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    diaries = db.query(Diary).filter(
        Diary.user_id == user_id,
        Diary.shared == True
    ).order_by(Diary.created_at.desc()).all()

    results = []
    for diary in diaries:
        # 좋아요 수 계산
        likes_count = db.query(Like).filter(Like.diary_id == diary.id).count()
        # 댓글 수 계산
        comments_count = db.query(Comment).filter(Comment.diary_id == diary.id).count()
        # 현재 사용자의 좋아요 여부 확인
        is_liked = db.query(Like).filter(
            Like.diary_id == diary.id,
            Like.user_id == current_user.id
        ).first() is not None

        # status_tracking 정보 가져오기
        status = db.query(DiaryStatus).filter(DiaryStatus.diary_id == diary.id).first()

        diary_dict = {
            **diary.__dict__,
            'likes_count': likes_count,
            'comments_count': comments_count,
            'is_liked': is_liked,
            'user': diary.owner,
            'status_tracking': status
        }
        results.append(diary_dict)

    return results