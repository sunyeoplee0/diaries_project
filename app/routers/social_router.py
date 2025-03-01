# routers/social_router.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import SessionLocal
from models import User, Follow, Diary, Like, Comment, DiaryStatus
from schemas import (FollowResponse, FeedDiaryResponse, CommentResponse,
                     CommentCreate, CommentUpdate)
from .diary_router import get_current_user, get_db

router = APIRouter(prefix="/social", tags=["Social"])


@router.post("/follow/{user_id}", response_model=FollowResponse)
async def follow_user(
        user_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot follow yourself"
        )

    existing_follow = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first()

    if existing_follow:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already following"
        )

    new_follow = Follow(follower_id=current_user.id, following_id=user_id)
    db.add(new_follow)
    db.commit()
    db.refresh(new_follow)
    return new_follow


@router.delete("/unfollow/{user_id}")
async def unfollow_user(
        user_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    follow = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == user_id
    ).first()

    if not follow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not following this user"
        )

    db.delete(follow)
    db.commit()
    return {"message": "Unfollowed successfully"}


@router.get("/feed", response_model=List[FeedDiaryResponse])
async def get_feed(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    following_ids = db.query(Follow.following_id).filter(
        Follow.follower_id == current_user.id
    ).all()
    following_ids = [id for (id,) in following_ids]

    diaries = db.query(Diary).filter(
        Diary.user_id.in_(following_ids),
        Diary.shared == True
    ).order_by(Diary.created_at.desc()).all()

    results = []
    for diary in diaries:
        likes_count = db.query(Like).filter(Like.diary_id == diary.id).count()
        comments_count = db.query(Comment).filter(Comment.diary_id == diary.id).count()
        is_liked = db.query(Like).filter(
            Like.diary_id == diary.id,
            Like.user_id == current_user.id
        ).first() is not None

        # 사용자의 팔로워/팔로잉 수 계산
        followers_count = db.query(Follow).filter(
            Follow.following_id == diary.user_id
        ).count()
        following_count = db.query(Follow).filter(
            Follow.follower_id == diary.user_id
        ).count()

        # 현재 사용자가 작성자를 팔로우하고 있는지 확인
        is_following = diary.user_id in following_ids

        # SQLAlchemy 모델을 딕셔너리로 변환할 때 _sa_instance_state 제거
        user_dict = {
            'id': diary.owner.id,
            'email': diary.owner.email,
            'nickname': diary.owner.nickname,
            'profile_image_url': diary.owner.profile_image_url,
            'followers_count': followers_count,
            'following_count': following_count,
            'is_following': is_following
        }

        status = db.query(DiaryStatus).filter(DiaryStatus.diary_id == diary.id).first()

        # 일기 데이터에서 _sa_instance_state 제거
        diary_dict = {
            'id': diary.id,
            'title': diary.title,
            'content': diary.content,
            'date': diary.date,
            'created_at': diary.created_at,
            'updated_at': diary.updated_at,
            'user_id': diary.user_id,
            'emotion': diary.emotion,
            'image_url': diary.image_url,
            'shared': diary.shared,
            'likes_count': likes_count,
            'comments_count': comments_count,
            'is_liked': is_liked,
            'user': user_dict,
            'status_tracking': status
        }
        results.append(diary_dict)

    return results


@router.post("/diaries/{diary_id}/like")
async def like_diary(
        diary_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    diary = db.query(Diary).filter(Diary.id == diary_id).first()
    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diary not found"
        )

    existing_like = db.query(Like).filter(
        Like.diary_id == diary_id,
        Like.user_id == current_user.id
    ).first()

    if existing_like:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Already liked"
        )

    new_like = Like(diary_id=diary_id, user_id=current_user.id)
    db.add(new_like)
    db.commit()

    return {"message": "Liked successfully"}


@router.delete("/diaries/{diary_id}/like")
async def unlike_diary(
        diary_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    like = db.query(Like).filter(
        Like.diary_id == diary_id,
        Like.user_id == current_user.id
    ).first()

    if not like:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Like not found"
        )

    db.delete(like)
    db.commit()

    return {"message": "Unliked successfully"}


@router.get("/diaries/{diary_id}/comments", response_model=List[CommentResponse])
async def get_comments(
        diary_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    comments = db.query(Comment).filter(Comment.diary_id == diary_id).all()

    results = []
    for comment in comments:
        # 각 댓글 작성자의 팔로워/팔로잉 정보 계산
        followers_count = db.query(Follow).filter(
            Follow.following_id == comment.user_id
        ).count()
        following_count = db.query(Follow).filter(
            Follow.follower_id == comment.user_id
        ).count()
        is_following = db.query(Follow).filter(
            Follow.follower_id == current_user.id,
            Follow.following_id == comment.user_id
        ).first() is not None

        # 사용자 정보에 팔로우 관련 정보 추가
        user_dict = {
            'id': comment.user.id,
            'email': comment.user.email,
            'nickname': comment.user.nickname,
            'profile_image_url': comment.user.profile_image_url,
            'followers_count': followers_count,
            'following_count': following_count,
            'is_following': is_following
        }

        # 댓글 정보 생성
        comment_dict = {
            'id': comment.id,
            'content': comment.content,
            'diary_id': comment.diary_id,
            'user_id': comment.user_id,
            'user': user_dict,
            'created_at': comment.created_at,
            'updated_at': comment.updated_at
        }
        results.append(comment_dict)

    return results


@router.post("/diaries/{diary_id}/comments", response_model=CommentResponse)
async def create_comment(
        diary_id: int,
        comment: CommentCreate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    diary = db.query(Diary).filter(Diary.id == diary_id).first()
    if not diary:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Diary not found"
        )

    new_comment = Comment(
        content=comment.content,
        diary_id=diary_id,
        user_id=current_user.id
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)

    # 댓글 작성자의 팔로워/팔로잉 정보 계산
    followers_count = db.query(Follow).filter(
        Follow.following_id == new_comment.user_id
    ).count()
    following_count = db.query(Follow).filter(
        Follow.follower_id == new_comment.user_id
    ).count()
    is_following = db.query(Follow).filter(
        Follow.follower_id == current_user.id,
        Follow.following_id == new_comment.user_id
    ).first() is not None

    # 사용자 정보에 팔로우 관련 정보 추가
    user_dict = {
        'id': new_comment.user.id,
        'email': new_comment.user.email,
        'nickname': new_comment.user.nickname,
        'profile_image_url': new_comment.user.profile_image_url,
        'followers_count': followers_count,
        'following_count': following_count,
        'is_following': is_following
    }

    # 댓글 정보 생성
    comment_dict = {
        'id': new_comment.id,
        'content': new_comment.content,
        'diary_id': new_comment.diary_id,
        'user_id': new_comment.user_id,
        'user': user_dict,
        'created_at': new_comment.created_at,
        'updated_at': new_comment.updated_at
    }

    return comment_dict


@router.put("/diaries/comments/{comment_id}", response_model=CommentResponse)
async def update_comment(
        comment_id: int,
        comment_update: CommentUpdate,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    comment = db.query(Comment).filter(
        Comment.id == comment_id,
        Comment.user_id == current_user.id
    ).first()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )

    comment.content = comment_update.content
    db.commit()
    db.refresh(comment)

    return comment


@router.delete("/diaries/comments/{comment_id}")
async def delete_comment(
        comment_id: int,
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    comment = db.query(Comment).filter(
        Comment.id == comment_id,
        Comment.user_id == current_user.id
    ).first()

    if not comment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Comment not found"
        )

    db.delete(comment)
    db.commit()

    return {"message": "Comment deleted successfully"}


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
        likes_count = db.query(Like).filter(Like.diary_id == diary.id).count()
        comments_count = db.query(Comment).filter(Comment.diary_id == diary.id).count()
        is_liked = db.query(Like).filter(
            Like.diary_id == diary.id,
            Like.user_id == current_user.id
        ).first() is not None

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
