#!/usr/bin/env python3
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

Base = declarative_base()
engine = create_engine('sqlite:////tmp/mmvmm.db', echo=False)
SessionMaker = sessionmaker(bind=engine)


def create_all():
    Base.metadata.create_all(engine)
