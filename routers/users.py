from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

import models
from database import get_db
from schemas import UserCreate, UserUpdate, PostReponce, UserPublic, UserPrivate, Token
from datetime import timedelta
from fastapi.security import OAuth2PasswordRequestForm
from starlette.concurrency import run_in_threadpool
from config import settings
from PIL import UnidentifiedImageError
from image_utils import process_profile_image, delete_profile_image
from auth import (
    create_access_token,
    hash_password,
    verify_password,
    CurrentUser,
)

router = APIRouter()


# ------------------------------------------------------------------------------------------------------
@router.get(
    "",
)
async def get_users(db: Annotated[AsyncSession, Depends(get_db)]) -> list[UserPublic]:
    result = await db.execute(select(models.User))
    users = result.scalars().all()
    return users  # type: ignore


# ------------------------------------------------------------------------------------------------------
@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(models.User).where(
            func.lower(models.User.email) == form_data.username.lower(),
        ),
    )
    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires,
    )
    return Token(access_token=access_token, token_type="bearer")


# ------------------------------------------------------------------------------------------------------
@router.post(
    "",
    response_model=UserPrivate,
    status_code=status.HTTP_201_CREATED,
)
async def create_user(user: UserCreate, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.User).where(
            func.lower(models.User.username) == user.username.lower()
        ),
    )
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists",
        )

    result = await db.execute(
        select(models.User).where(func.lower(models.User.email) == user.email.lower())
    )
    existing_email = result.scalars().first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )

    new_user = models.User(
        username=user.username,
        email=user.email.lower(),
        password_hash=hash_password(user.password),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user  # type: ignore


# ------------------------------------------------------------------------------------------------------


@router.get(
    "/me",
)
async def get_current_user(current_user: CurrentUser) -> UserPrivate:
    return current_user  # type: ignore


# ------------------------------------------------------------------------------------------------------


@router.get(
    "/{user_id}",
)
async def get_user(
    user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> UserPublic:
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if user:
        return user  # type: ignore

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found",
    )


# ------------------------------------------------------------------------------------------------------
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
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.user_id == user_id)
        .order_by(models.Post.date_posted.desc())
    )
    posts = result.scalars().all()
    return posts  # type: ignore


# ------------------------------------------------------------------------------------------------------
@router.patch(
    "/{user_id}",
)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserPrivate:

    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user",
        )

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")

    if (
        user_data.username is not None
        and user.username.lower() != user_data.username.lower()
    ):
        result = await db.execute(
            select(models.User).where(
                func.lower(models.User.username) == user_data.username.lower()
            )
        )
        existing_username = result.scalars().first()
        if existing_username:
            raise HTTPException(status_code=404, detail="Username already exists")

    if user_data.email is not None and user.email.lower() != user_data.email.lower():
        result = await db.execute(
            select(models.User).where(
                func.lower(models.User.email) == user_data.email.lower()
            )
        )
        existing_email = result.scalars().first()
        if existing_email:
            raise HTTPException(status_code=404, detail="Email already exists")

    if user_data.username is not None:
        user.username = user_data.username
    if user_data.email is not None:
        user.email = user_data.email.lower()

    await db.commit()
    await db.refresh(user)
    return user  # type: ignore


# ------------------------------------------------------------------------------------------------------
@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_user(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this user",
        )

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    old_filename = user.image_file

    await db.delete(user)
    await db.commit()

    if old_filename:
        delete_profile_image(old_filename)


# ------------------------------------------------------------------------------------------------------


@router.patch("/{user_id}/picture")
async def upload_user_image(
    user_id: int,
    file: UploadFile,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserPrivate:

    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not Authorized to perform this operation",
        )

    content = await file.read()

    if len(content) > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. maximum size is {settings.max_upload_size_bytes // (1024 * 1024)}MB",
        )

    try:
        new_file = await run_in_threadpool(process_profile_image, content)
    except UnidentifiedImageError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file. Please upload a valid image (JPEG, PNG, GIF, WebP).",
        ) from err

    old_filename = current_user.image_file

    current_user.image_file = new_file
    await db.commit()
    await db.refresh(current_user)

    if old_filename:
        delete_profile_image(old_filename)

    return current_user  # type: ignore


# ------------------------------------------------------------------------------------------------------


@router.delete("/{user_id}/picture")
async def delete_profile_picture(
    user_id: int,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserPrivate:

    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not Authorized to perform this operation",
        )

    old_filename = current_user.image_file

    if not old_filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No profile picture to delete",
        )

    current_user.image_file = None
    await db.commit()
    await db.refresh(current_user)

    delete_profile_image(old_filename)

    return current_user  # type: ignore


# ------------------------------------------------------------------------------------------------------
