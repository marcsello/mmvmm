#!/usr/bin/env python3
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import backref, relationship

from .db import Base


class Media(Base):
    __tablename__ = "media"

    id = Column(Integer, nullable=False, primary_key=True, autoincrement=True)

    hardware_id = Column(Integer, ForeignKey('hardware.vm_id'))
    hardware = relationship("Hardware", backref=backref("media", lazy=True, uselist=True))

    type = Column(String(5), nullable=False)  # disk or cdrom
    path = Column(String(4096), nullable=False)  # Only absolute path allowed; limits.h PATH_MAX
    format = Column(String(4), default='raw', nullable=False)  # Raw or qcow2
    readonly = Column(Boolean, nullable=False, default=False)
    interface = Column(String(7), default='virtio', nullable=False)  # virtio, ide, floppy
    host_cache = Column(Boolean, nullable=False, default=False)

    __table_args__ = (
        CheckConstraint("type IN ('cdrom', 'disk')", name='type_valid'),
        {}
    )
