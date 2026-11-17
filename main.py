from fastapi import FastAPI, Request, HTTPException, status, Path
from fastapi.responses import HTMLResponse, JSONResponse
from typing import List, Dict
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Annotated
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

app = FastAPI()

app.mount('/static', StaticFiles(directory='static'), name='static')

templates = Jinja2Templates(directory='templates')

posts: List[dict] = [
    {
        "id": 1,
        "author": "Himanshu_Chandera",
        "title": "FastAPI is best",
        "content": "FastAPI is best framework cause it is fast and easy to use",
        "date_posted": "30th November, 2026"
    },
    {
        "id": 2,
        "author": "Jay Patel",
        "title": "Viart is the GOAT",
        "content": "At 38 what he is doing in incredible",
        "date_posted": "27th November, 2026"
    }
]


@app.get('/', include_in_schema=False, name='home')
@app.get('/posts', include_in_schema=False, name='posts')
def home(request: Request):
    return templates.TemplateResponse(
        request, 
        "home.html", 
        {"posts": posts, "title": "Home"},
    )


@app.get("/posts/{post_id}", include_in_schema=False)
def post_page(post_id: Annotated[int, Path()], request: Request):
    for post in posts:
        if post['id'] == post_id:
            title = post['title']
            return templates.TemplateResponse(
                request, 
                "post.html", 
                {"post": post, "title": title},
            )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail='Post not found'
    )


@app.get("/api/posts")
def get_posts():
    return posts


@app.get("/api/posts/{post_id}")
def get_post(post_id: int):
    for post in posts:
        if post['id'] == post_id:
            return post
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail='Post not found'
    )


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