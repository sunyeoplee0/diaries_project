from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from database import  engine
from models import Base
from routers import user_router, diary_router, analytics_router, social_router

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(user_router.router)
app.include_router(diary_router.router)
app.include_router(analytics_router.router)
app.include_router(social_router.router)

@app.get("/")
def read_root():
    return {"message": "FastAPI 서버가 실행 중입니다."}
