#!/usr/bin/env python3
import enum
from sqlalchemy import Column, Integer, String, Enum, DateTime
from sqlalchemy.sql import func

from .db import Base


class VMStatus(enum.Enum):
    NEW = 0
    CONFIGURING = 1
    STOPPED = 2
    STARTING = 3
    RUNNING = 4
    STOPPING = 5


class VM(Base):
    __tablename__ = "vm"

    id = Column(Integer, nullable=False, primary_key=True, autoincrement=True)
    name = Column(String(42), nullable=False, unique=True)

    status = Column(Enum(VMStatus), nullable=False, default=VMStatus.NEW)
    since = Column(DateTime, nullable=False, server_default=func.now())
    pid = Column(Integer, nullable=True, unique=True)
