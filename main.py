from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from typing import List, Dict
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

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


@app.get('/', include_in_schema=False)
@app.get('/posts', include_in_schema=False)
def home(request: Request):
    return templates.TemplateResponse(
        request, 
        "home.html", 
        {"posts": posts, "title": "Home"},
    )

@app.get("/api/posts")
def get_posts():
    return posts


