
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DB_URL")
# pool_pre_ping tests a pooled connection before handing it to a page. After a
# network blip, a Postgres restart or a laptop waking from sleep, the pool is
# holding connections that are already dead and nobody has been told. Without
# this the next page gets one of those and errors, so an operator sees a broken
# screen for a fault that had already fixed itself. With it, that connection is
# thrown away and a fresh one opened, and the page never finds out. Costs one
# short round trip per render, which is under a millisecond on this network.
#
# pool_recycle is the other half. Plant networks and firewalls quietly drop
# connections that have sat idle too long and tell neither end, so this retires
# them at thirty minutes before the network does it for us.
#
# The sizes raise the ceiling from SQLAlchemy's default 5 + 10 to 10 + 20, so
# thirty page renders can be querying at once instead of fifteen. Postgres here
# allows 100. An idle pooled connection costs almost nothing.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
)
SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
ScopedSession = scoped_session(SessionFactory)
Base = declarative_base()
