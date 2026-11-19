from fastapi import FastAPI, Request, HTTPException, status, Path, Depends
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Annotated, List
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select, delete
from sqlalchemy.orm import Session

from schemas import PostCreate, PostReponce, UserResponce, UserCreate, PostUpdate, UserUpdate
from database import Base, engine, get_db
import models

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.mount('/static', StaticFiles(directory='static'), name='static')

app.mount('/media', StaticFiles(directory='media'), name='media')

templates = Jinja2Templates(directory='templates')





# HTML responces api endpoints---------------------------------
@app.get('/', include_in_schema=False, name='home')
@app.get('/posts', include_in_schema=False, name='posts')
def home(request: Request, db: Annotated[Session, Depends(get_db)]):
    posts = db.execute(
        select(models.Post)
    ).scalars().all()
    return templates.TemplateResponse(
        request, 
        "home.html", 
        {"posts": posts, "title": "Home"},
    )


@app.get("/posts/{post_id}", include_in_schema=False)
def post_page(
    request: Request,
    post_id: Annotated[int, Path()], 
    db: Annotated[Session, Depends(get_db)]
):
    post = db.execute(
        select(models.Post).where(models.Post.id == post_id)
    ).scalars().first()
    if post:
        return templates.TemplateResponse(
            request, 
            "post.html", 
            {"post": post, "title": post.title},
        )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail='Post not found'
    )


@app.get('/users/{user_id}/posts', include_in_schema=False)
def user_posts_page(
    request: Request,
    user_id: Annotated[int, Path()],
    db: Annotated[Session, Depends(get_db)]
):
    user = db.execute(select(models.User).where(models.User.id == user_id)).scalars().first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail='User not found'
        )
    posts= db.execute(select(models.Post).where(models.Post.user_id == user_id)).scalars().all()
    return templates.TemplateResponse(
        request,
        'user_posts.html',
        {'posts': posts, 'user': user, 'title': f"{user.username}'s posts"},
    )







# user related api endpoints -----------------------------
@app.post(
        '/api/users',
        response_model=UserResponce,
        status_code=status.HTTP_201_CREATED,
        tags=['User Oprations']
)
def create_user(user: UserCreate, db: Annotated[Session, Depends(get_db)]):
    result = db.execute(
        select(models.User).where(models.User.username == user.username)
    )
    existing_user= result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Username already exists',
        )

    result = db.execute(
            select(models.User).where(models.User.email == user.email)
        )
    existing_email= result.scalars().first()
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Email already exists',
        )

    new_user = models.User(
        username=user.username,
        email=user.email
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


@app.get("/api/users/{user_id}", response_model=UserResponce, tags=['User Oprations'])
def get_user(user_id: int, db: Annotated[Session, Depends(get_db)]):
    user = db.execute(
        select(models.User).where(models.User.id == user_id)
    ).scalars().first()

    if user: 
        return user

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail='User not found',
    )


@app.get('/api/users/{user_id}/posts', tags=['User Oprations'])
def get_user_posts(
    user_id: int,
    db: Annotated[Session, Depends(get_db)]
) -> List[PostReponce]:

    user = db.execute(
        select(models.User).where(models.User.id == user_id)
    ).scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )

    posts = db.execute(
        select(models.User.posts).where(models.User.id == user_id)
    ).scalars().all()

    return posts    # type: ignore



@app.patch("/api/users/{user_id}", tags=['User Oprations'])
def update_user(
    user_id: int, 
    db: Annotated[Session, Depends(get_db)],
    user_data: UserUpdate
) -> UserResponce:
    user = db.execute(select(models.User).where(models.User.id == user_id)).scalars().first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail='user not found'
        )
    if user_data.username is not None and user.username != user_data.username:
        existing_username= db.execute(
            select(models.User).where(models.User.username == user_data.username)
        ).scalars().first()
        if existing_username:
            raise HTTPException(
                status_code=404,
                detail='Username already exists'
        )
    if user_data.email is not None and user.email != user_data.email:
        existing_email= db.execute(
            select(models.User).where(models.User.email == user_data.email)
        ).scalars().first()
        if existing_email:
            raise HTTPException(
                status_code=404,
                detail='Email already exists'
        )
    user_dict= user_data.model_dump(exclude_unset=True)
    for key, value in user_dict:
        setattr(user, key, value)

    db.commit()
    db.refresh(user)
    return user        # type: ignore


@app.delete("/api/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT, tags=['User Oprations'])
def delete_user(
    user_id: int, 
    db: Annotated[Session, Depends(get_db)]
):
    user = db.execute(select(models.User).where(models.User.id == user_id)).scalars().first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail='User not found'
        )
    db.delete(user)
    db.commit()
    




        


# post related api endpoints -----------------------------------

@app.get("/api/posts", tags=['Post Oprations'])
def get_posts(db: Annotated[Session, Depends(get_db)]) -> List[PostReponce]:
    posts = db.execute(select(models.Post)).scalars().all()
    return posts    # type: ignore



@app.post('/api/posts',status_code=status.HTTP_201_CREATED, tags=['Post Oprations'])
def create_post(post: PostCreate, db: Annotated[Session, Depends(get_db)]) -> PostReponce:
    user = db.execute(select(models.User).where(models.User.id == post.user_id)).scalars().all()
    if not user:
        raise HTTPException(
            status_code=404,
            detail='user not found'
        )
    new_post = models.Post(
        title=post.title,
        content=post.content,
        user_id=post.user_id
    )
    db.add(new_post)
    db.commit()
    db.refresh(new_post)
    return new_post   # type: ignore

        

@app.get("/api/posts/{post_id}", tags=['Post Oprations'])
def get_post(post_id: int, db: Annotated[Session, Depends(get_db)]) -> PostReponce:
    post = db.execute(select(models.Post).where(models.Post.id == post_id)).scalars().first()
    if not post:
        raise HTTPException(
            status_code=404,
            detail='Post not found'
        )
    return post   # type: ignore



@app.put("/api/posts/{post_id}", tags=['Post Oprations'])
def update_post_full(
    post_id: int, 
    db: Annotated[Session, Depends(get_db)],
    post_data: PostCreate
) -> PostReponce:
    post = db.execute(select(models.Post).where(models.Post.id == post_id)).scalars().first()
    if not post:
        raise HTTPException(
            status_code=404,
            detail='Post not found'
        )
    if post_data.user_id != post.user_id:
        author = db.execute(
            select(models.User).where(models.User.id == post_data.user_id)
        ).scalars().first()
        if not author:
            raise HTTPException(
                status_code=404,
                detail='User not found'
            )
    post.title = post_data.title
    post.content = post_data.content
    post.user_id = post_data.user_id
    db.commit()
    db.refresh(post)
    return post        #type: ignore



@app.patch("/api/posts/{post_id}", tags=['Post Oprations'])
def update_post_partial(
    post_id: int, 
    db: Annotated[Session, Depends(get_db)],
    post_data: PostUpdate
) -> PostReponce:
    post = db.execute(select(models.Post).where(models.Post.id == post_id)).scalars().first()
    if not post:
        raise HTTPException(
            status_code=404,
            detail='Post not found'
        )
    updated_post= post_data.model_dump(exclude_unset=True)
    for key, value in updated_post.items():
        setattr(post, key, value)

    db.commit()
    db.refresh(post)
    return post       # type: ignore



@app.delete("/api/posts/{post_id}", status_code=status.HTTP_204_NO_CONTENT, tags=['Post Oprations'])
def delete_post(
    post_id: int, 
    db: Annotated[Session, Depends(get_db)]
):
    post = db.execute(select(models.Post).where(models.Post.id == post_id)).scalars().first()
    if not post:
        raise HTTPException(
            status_code=404,
            detail='Post not found'
        )
    db.delete(post)
    db.commit()
    




# excepption Handkers ----------------------------
@app.exception_handler(StarletteHTTPException)
def general_http_exception_handler(request: Request, exception: StarletteHTTPException):
    messege = (
        exception.detail
        if exception.detail
        else "An error occured, please check your request and try again"
    )

    if request.url.path.startswith('/api'):
        return JSONResponse(
            status_code=exception.status_code,
            content={'detail': messege}
        )

    return templates.TemplateResponse(
        request,
        'error.html',
        {
            'status_code': exception.status_code,
            'title': exception.status_code,
            'messege': messege
        },
        status_code=exception.status_code,
    )

@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exception: RequestValidationError):
    if request.url.path.startswith('/api'):
        return JSONResponse(
            status_code=422,
            content={'details': exception.errors()}
        )

    return templates.TemplateResponse(
        request,
        'error.html',
        {
            'status_code': status.HTTP_422_UNPROCESSABLE_CONTENT,
            'title': status.HTTP_422_UNPROCESSABLE_CONTENT,
            'messege': 'An error occured, please check your request and try again',
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )