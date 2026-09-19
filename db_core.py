
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
from dotenv import load_dotenv

from db_options import connect_args_for, resolve_database_url

load_dotenv()

# DB_URL when there is one, otherwise the bundled database in pgdata\ - so a
# script run from a console on a portable PC finds the same database the app
# uses, instead of no database at all (see db_options.resolve_database_url).
DATABASE_URL = resolve_database_url()
if not DATABASE_URL:
    raise RuntimeError(
        "No database to connect to: DB_URL isn't set in .env, and there is no "
        "bundled database (pgdata\\) next to this project. Start the app once "
        "with START_HERE.bat (option 9 for the bundled database), or put a real "
        "DB_URL in .env."
    )
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
#
# connect_args (db_options.py) bounds how long a connection to a database on
# another PC can hang: a connect timeout, and TCP keepalives so a connection
# whose far end silently vanished becomes an error instead of a wait forever.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
    connect_args=connect_args_for(DATABASE_URL),
)
SessionFactory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
ScopedSession = scoped_session(SessionFactory)
Base = declarative_base()
