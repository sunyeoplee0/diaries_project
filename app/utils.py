import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv
from jose import JWTError, jwt
from fastapi import HTTPException, status

load_dotenv()

X_API_KEY_VALUE = os.getenv("X-API-KEY")
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
REFRESH_SECRET_KEY = os.getenv("JWT_REFRESH_SECRET_KEY")
ALGORITHM = os.getenv("JWT_ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", 30))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", 7))
AI_SERVER_URL = os.getenv("AI_SERVER_URL")
BASE_URL = os.getenv("BASE_URL")

class TokenError(Exception):
    def __init__(self, detail: str):
        self.detail = detail


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "token_type": "access"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("token_type") != "access":
            raise TokenError("Invalid token type")
        return payload
    except JWTError as e:
        raise TokenError("Invalid access token") from e


def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "token_type": "refresh"})
    return jwt.encode(to_encode, REFRESH_SECRET_KEY, algorithm=ALGORITHM)


def verify_refresh_token(token: str):
    try:
        payload = jwt.decode(token, REFRESH_SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("token_type") != "refresh":
            raise TokenError("Invalid token type")
        return payload
    except JWTError as e:
        raise TokenError("Invalid refresh token") from e


def analyze_emotion_and_get_image(diary_id: int, content: str):
    url = f"{AI_SERVER_URL}/api/analyze_diary"

    headers = {
        "Content-Type": "application/json",
        "X-API-KEY": X_API_KEY_VALUE
    }

    payload = {
        "diary_id": diary_id,
        "content": content
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 서버 통신 오류: {str(e)}"
        )



def get_diary_status_from_ai_server(diary_id: int):
    url = f"https://daily-momento.duckdns.org:20929/api/status/{diary_id}"
    api_key = os.getenv("X-API-KEY")

    headers = {
        "X-API-KEY": api_key
    }

    try:
        response = requests.get(url, headers=headers, verify=True)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI 서버 통신 오류: {str(e)}"
        )