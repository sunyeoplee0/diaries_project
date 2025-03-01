import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import urllib.parse

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = urllib.parse.quote_plus(os.getenv("DB_PASSWORD"))
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_recycle=3600,  # 연결을 1시간마다 재생성
    pool_pre_ping=True,  # 쿼리 실행 전 연결 상태 확인
    pool_size=5,  # 기본 연결 풀 크기
    max_overflow=10,  # 추가로 생성할 수 있는 최대 연결 수
    # 연결 타임아웃 설정
    connect_args={
        "connect_timeout": 60,  # 연결 시도 타임아웃 (초)
    }
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)