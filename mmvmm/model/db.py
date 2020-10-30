#!/usr/bin/env python3
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from config import Config

Base = declarative_base()

engine = create_engine(Config.DATABASE_URI, echo=False)
session_maker_factory = sessionmaker(bind=engine)
scoped_session_factory = scoped_session(session_maker_factory)


class Session:
    def __init__(self):
        self.session = scoped_session_factory()

    def __enter__(self):
        return self.session

    def __exit__(self, exc_type, exc_value, tb):
        self.session.close()


def create_all():
    Base.metadata.create_all(engine)
