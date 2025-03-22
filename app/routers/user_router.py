import os
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Header, UploadFile, File
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from database import SessionLocal
from models import User
from schemas import UserCreate, UserLogin, UserResponse, UserProfileUpdate, PasswordChange
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


@router.get("/profile", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user)
):
    return {
        'id': current_user.id,
        'email': current_user.email,
        'nickname': current_user.nickname,
        'profile_image_url': current_user.profile_image_url
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

        return {
            'id': user.id,
            'email': user.email,
            'nickname': user.nickname,
            'profile_image_url': user.profile_image_url
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

        # 새 비밀번호로 업데이트
        user = db.query(User).filter(User.id == current_user.id).first()
        user.password = pwd_context.hash(password_data.new_password)
        db.commit()
        db.refresh(user)
        return {"message": "비밀번호가 변경되었습니다."}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )