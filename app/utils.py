import os
import jwt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
import httpx
from dotenv import load_dotenv
import json

load_dotenv()

# JWT 토큰 설정
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7

# ChatGPT API 설정
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"


class TokenError(Exception):
    """토큰 관련 오류 처리를 위한 사용자 정의 예외"""
    pass


def create_access_token(data: dict):
    """Access 토큰 생성"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict):
    """Refresh 토큰 생성"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str):
    """Access 토큰 검증"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenError("만료된 토큰입니다")
    except jwt.DecodeError:
        raise TokenError("잘못된 토큰입니다")
    except Exception:
        raise TokenError("토큰 검증 과정에서 오류가 발생했습니다")


def verify_refresh_token(token: str):
    """Refresh 토큰 검증"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenError("만료된 리프레시 토큰입니다. 다시 로그인해주세요")
    except jwt.DecodeError:
        raise TokenError("잘못된 리프레시 토큰입니다")
    except Exception:
        raise TokenError("리프레시 토큰 검증 과정에서 오류가 발생했습니다")


async def extract_tags_from_diary(diary_content: str) -> List[Dict[str, str]]:
    """
    일기 내용에서 중심 단어를 추출하고 태그로 변환하는 함수

    Args:
        diary_content: 일기 내용

    Returns:
        List[Dict[str, str]]: 태그 목록 (이름과 카테고리 포함)
    """
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }

        prompt = f"""
        다음 일기 내용에서 중심 단어를 추출해 주세요. 다음 카테고리별로 태그를 분류해 주세요:
        - 취미
        - 고민거리
        - 생활습관
        - 몸에 나타나는 증상
        - 좋아하는 것
        - 싫어하는 것
        - 인간관계

        JSON 형식으로 반환해 주세요. 예시:
        [
            {{"name": "등산", "category": "취미"}},
            {{"name": "두통", "category": "몸에 나타나는 증상"}},
            {{"name": "친구", "category": "인간관계"}}
        ]

        일기 내용:
        {diary_content}
        """

        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "당신은 텍스트에서 중요한 주제와 키워드를 추출하는 전문가입니다."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 500
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                OPENAI_API_URL,
                headers=headers,
                json=payload,
                timeout=30.0
            )

            if response.status_code != 200:
                print(f"API 오류: {response.status_code} - {response.text}")
                return []

            result = response.json()
            content = result['choices'][0]['message']['content']

            # JSON 문자열 추출 및 파싱
            try:
                # JSON 부분만 추출
                json_str = content
                if "[" in content and "]" in content:
                    start_idx = content.find("[")
                    end_idx = content.rfind("]") + 1
                    json_str = content[start_idx:end_idx]

                tags = json.loads(json_str)
                return tags
            except json.JSONDecodeError as e:
                print(f"JSON 파싱 오류: {e}")
                print(f"응답 내용: {content}")
                return []

    except Exception as e:
        print(f"태그 추출 중 오류 발생: {str(e)}")
        return []


async def generate_diary_comment(diary_content: str, similar_contents: List[str]) -> str:
    """
    현재 일기와 유사한 과거 일기들을 바탕으로 개인화된 코멘트 생성

    Args:
        diary_content: 현재 일기 내용
        similar_contents: 유사한 과거 일기 내용 목록

    Returns:
        str: 생성된 코멘트
    """
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }

        # 유사 일기 내용 결합
        similar_texts = "\n\n".join([f"유사 일기 {i + 1}:\n{content}" for i, content in enumerate(similar_contents)])

        prompt = f"""
        사용자의 현재 일기와 과거에 작성한 유사한 일기들을 분석하여 개인화된 코멘트를 작성해 주세요.

        코멘트는 다음과 같은 내용을 포함해야 합니다:
        1. 사용자의 감정 상태 분석
        2. 우울함이 감지된다면 적절한 조언
        3. 사용자의 패턴이나 습관에 대한 통찰
        4. 긍정적인 측면 강조 및 격려
        5. 필요하다면 전문가 상담 권유

        코멘트는 따뜻하고 공감적이며 지지적인 톤으로 작성해 주세요.

        현재 일기:
        {diary_content}

        과거 유사 일기들:
        {similar_texts}
        """

        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "system", "content": "당신은 공감적이고 전문적인 심리 상담사입니다. 사용자가 자신의 감정을 이해하고 정신 건강을 개선할 수 있도록 도와주세요."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                OPENAI_API_URL,
                headers=headers,
                json=payload,
                timeout=30.0
            )

            if response.status_code != 200:
                print(f"API 오류: {response.status_code} - {response.text}")
                return "코멘트 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."

            result = response.json()
            content = result['choices'][0]['message']['content']
            return content

    except Exception as e:
        print(f"코멘트 생성 중 오류 발생: {str(e)}")
        return "코멘트 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요."


def find_similar_diaries(db_session, current_diary_id: int, user_id: int, tags: List[str], min_matching_tags: int = 2,
                         limit: int = 3) -> List[Tuple[int, str]]:
    """
    현재 일기와 태그가 유사한 과거 일기를 찾는 함수

    Args:
        db_session: DB 세션
        current_diary_id: 현재 일기 ID
        user_id: 사용자 ID
        tags: 현재 일기의 태그 목록
        min_matching_tags: 최소 매칭되어야 하는 태그 수
        limit: 반환할 최대 일기 수

    Returns:
        List[Tuple[int, str]]: (일기ID, 일기내용) 튜플 목록
    """
    from sqlalchemy import text

    # 태그 이름만 추출
    tag_names = [tag for tag in tags]

    if not tag_names:
        return []

    # 태그 목록을 문자열로 변환 (SQL 쿼리용)
    tags_str = ", ".join(f"'{tag}'" for tag in tag_names)

    # SQL 쿼리
    sql = text(f"""
    SELECT d.id, d.content, COUNT(t.id) as matching_tags
    FROM diaries d
    JOIN diary_tag dt ON d.id = dt.diary_id
    JOIN tags t ON dt.tag_id = t.id
    WHERE d.user_id = :user_id
    AND d.id != :current_diary_id
    AND t.name IN ({tags_str})
    GROUP BY d.id
    HAVING COUNT(t.id) >= :min_matching_tags
    ORDER BY matching_tags DESC, d.date DESC
    LIMIT :limit
    """)

    # 쿼리 실행
    result = db_session.execute(
        sql,
        {"user_id": user_id, "current_diary_id": current_diary_id, "min_matching_tags": min_matching_tags,
         "limit": limit}
    )

    # 결과 반환
    return [(row.id, row.content) for row in result]