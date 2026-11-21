from fastapi import FastAPI, Request, HTTPException, status, Path, Depends
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Annotated, List
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from contextlib import asynccontextmanager
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from sqlalchemy.ext.asyncio import AsyncSession
from schemas import (
    PostCreate,
    PostReponce,
    UserResponce,
    UserCreate,
    PostUpdate,
    UserUpdate,
)
from database import Base, engine, get_db
import models


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # startup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # shutdown
    await engine.dispose()


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.mount("/media", StaticFiles(directory="media"), name="media")

templates = Jinja2Templates(directory="templates")


# HTML responces api endpoints---------------------------------


@app.get("/", include_in_schema=False, name="home")
@app.get("/posts", include_in_schema=False, name="posts")
async def home(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Post).options(selectinload(models.Post.author))
    )
    posts = result.scalars().all()
    return templates.TemplateResponse(
        request,
        "home.html",
        {"posts": posts, "title": "Home"},
    )


@app.get("/posts/{post_id}", include_in_schema=False)
async def post_page(
    request: Request,
    post_id: Annotated[int, Path()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id)
    )
    post = result.scalars().first()
    if post:
        return templates.TemplateResponse(
            request,
            "post.html",
            {"post": post, "title": post.title},
        )
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")


@app.get("/users/{user_id}/posts", include_in_schema=False)
async def user_posts_page(
    request: Request,
    user_id: Annotated[int, Path()],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.user_id == user_id)
    )
    posts = result.scalars().all()
    return templates.TemplateResponse(
        request,
        "user_posts.html",
        {"posts": posts, "user": user, "title": f"{user.username}'s posts"},
    )


# user related api endpoints -----------------------------


@app.get("/api/users", tags=["User Oprations"])
async def get_users(db: Annotated[AsyncSession, Depends(get_db)]) -> List[UserResponce]:
    result = await db.execute(select(models.User))
    users = result.scalars().all()
    return users  # type: ignore


@app.get("/api/users/{user_id}", tags=["User Oprations"])
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


@app.post(
    "/api/users",
    response_model=UserResponce,
    status_code=status.HTTP_201_CREATED,
    tags=["User Oprations"],
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


@app.get("/api/users/{user_id}/posts", tags=["User Oprations"])
async def get_user_posts(
    user_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> List[PostReponce]:

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


@app.patch("/api/users/{user_id}", tags=["User Oprations"])
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


@app.delete(
    "/api/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["User Oprations"],
)
async def delete_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()


# post related api endpoints -----------------------------------


@app.get("/api/posts", tags=["Post Oprations"])
async def get_posts(db: Annotated[AsyncSession, Depends(get_db)]) -> List[PostReponce]:
    result = await db.execute(
        select(models.Post).options(selectinload(models.Post.author))
    )
    posts = result.scalars().all()
    return posts  # type: ignore


@app.post("/api/posts", status_code=status.HTTP_201_CREATED, tags=["Post Oprations"])
async def create_post(
    post: PostCreate, db: Annotated[AsyncSession, Depends(get_db)]
) -> PostReponce:
    result = await db.execute(select(models.User).where(models.User.id == post.user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    new_post = models.Post(title=post.title, content=post.content, user_id=post.user_id)
    db.add(new_post)
    await db.commit()
    await db.refresh(new_post, attribute_names=["author"])
    return new_post  # type: ignore


@app.get("/api/posts/{post_id}", tags=["Post Oprations"])
async def get_post(
    post_id: int, db: Annotated[AsyncSession, Depends(get_db)]
) -> PostReponce:
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id)
    )
    post = result.scalars().first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post  # type: ignore


@app.put("/api/posts/{post_id}", tags=["Post Oprations"])
async def update_post_full(
    post_id: int,
    post_data: PostCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PostReponce:
    result = await db.execute(select(models.Post).where(models.Post.id == post_id))
    post = result.scalars().first()
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Post not found",
        )
    if post_data.user_id != post.user_id:
        result = await db.execute(
            select(models.User).where(models.User.id == post_data.user_id),
        )
        user = result.scalars().first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

    post.title = post_data.title
    post.content = post_data.content
    post.user_id = post_data.user_id

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post  # type: ignore


@app.patch("/api/posts/{post_id}", tags=["Post Oprations"])
async def update_post_partial(
    post_id: int, db: Annotated[AsyncSession, Depends(get_db)], post_data: PostUpdate
) -> PostReponce:
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id)
    )
    post = result.scalars().first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    updated_post = post_data.model_dump(exclude_unset=True)
    for key, value in updated_post.items():
        setattr(post, key, value)

    await db.commit()
    await db.refresh(post, attribute_names=["author"])
    return post  # type: ignore


@app.delete(
    "/api/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Post Oprations"],
)
async def delete_post(post_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(
        select(models.Post)
        .options(selectinload(models.Post.author))
        .where(models.Post.id == post_id)
    )
    post = result.scalars().first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    await db.delete(post)
    await db.commit()


# exception Handlers ----------------------------


@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(
    request: Request, exception: StarletteHTTPException
):
    if request.url.path.startswith("/api"):
        return await http_exception_handler(request, exception)
    messege = (
        exception.detail
        if exception.detail
        else "An error occured, please check your request and try again"
    )
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": exception.status_code,
            "title": exception.status_code,
            "messege": messege,
        },
        status_code=exception.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exception: RequestValidationError
):
    if request.url.path.startswith("/api"):
        return await request_validation_exception_handler(request, exception)

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "title": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "messege": "An error occured, please check your request and try again",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
