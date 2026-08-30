
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DB_URL")
engine = create_engine(DATABASE_URL)
SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
ScopedSession = scoped_session(SessionFactory)
Base = declarative_base()
