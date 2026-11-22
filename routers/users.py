from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schemas import UserCreate, UserResponce, UserUpdate, PostReponce

router = APIRouter()


@router.get(
    "",
)
async def get_users(db: Annotated[AsyncSession, Depends(get_db)]) -> list[UserResponce]:
    result = await db.execute(select(models.User))
    users = result.scalars().all()
    return users  # type: ignore


@router.get(
    "/{user_id}",
)
async def get_user(
    user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> UserResponce:
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if user:
        return user  # type: ignore

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found",
    )


@router.post(
    "",
    response_model=UserResponce,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.User).where(models.User.username == user.username)
    )
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    result = await db.execute(
        select(models.User).where(models.User.email == user.email)
    )
    existing_email = result.scalars().first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )

    new_user = models.User(username=user.username, email=user.email)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@router.get(
    "/{user_id}/posts",
)
async def get_user_posts(
    user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> list[PostReponce]:

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    result = await db.execute(
        select(models.User.posts).where(models.User.id == user_id)
    )
    posts = result.scalars().first()
    return posts  # type: ignore


@router.patch(
    "/{user_id}",
)
async def update_user(
    user_id: int, db: Annotated[AsyncSession, Depends(get_db)], user_data: UserUpdate
) -> UserResponce:
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    if user_data.username is not None and user.username != user_data.username:
        result = await db.execute(
            select(models.User).where(models.User.username == user_data.username)
        )
        existing_username = result.scalars().first()
        if existing_username:
            raise HTTPException(status_code=404, detail="Username already exists")
    if user_data.email is not None and user.email != user_data.email:
        result = await db.execute(
            select(models.User).where(models.User.email == user_data.email)
        )
        existing_email = result.scalars().first()
        if existing_email:
            raise HTTPException(status_code=404, detail="Email already exists")

    user_dict = user_data.model_dump(exclude_unset=True)
    for key, value in user_dict.items():
        setattr(user, key, value)

    await db.commit()
    await db.refresh(user)
    return user  # type: ignore


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
