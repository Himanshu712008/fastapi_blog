from sqlalchemy.orm import Session, DeclarativeBase
from sqlalchemy import create_engine

SQLALCHEMY_DATABASE_URL = 'sqlite:///./blog.db'

engine = create_engine(SQLALCHEMY_DATABASE_URL)

class Base(DeclarativeBase):
    pass

def get_db():
    with Session(engine, autoflush=False) as db:
        yield db
