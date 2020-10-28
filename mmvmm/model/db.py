#!/usr/bin/env python3
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session

Base = declarative_base()
engine = create_engine('sqlite://', echo=True)
Session = scoped_session(sessionmaker(bind=engine))

_registry = {}


def register_to_handle(what: str, when: str, handler: callable):

    if when not in ["after_flush", "before_flush"]:
        raise ValueError(f"{when} is invalid for when")

    if not _registry[when]:
        _registry[when] = {}

    _registry[when][what] = handler


def handles(what: str, when: str):
    def decorator(call):
        register_to_handle(what, when, call)
        return call
