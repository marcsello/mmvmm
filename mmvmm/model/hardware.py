#!/usr/bin/env python3
import uuid
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import backref, relationship

from .db import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Hardware(Base):
    __tablename__ = "hardware"

    vm_id = Column(Integer, ForeignKey('vm.id'), primary_key=True)
    vm = relationship("VM", backref=backref("hardware", lazy="joined", uselist=False,
                                            cascade="save-update, merge, delete, delete-orphan"))

    product_uuid = Column(String(36), nullable=False, default=generate_uuid)

    ram_m = Column(Integer, nullable=False)
    cpus = Column(Integer, nullable=False)
    boot = Column(String(1), nullable=False, default='d')

    rtc_utc = Column(Boolean, nullable=False, default=True)

    __table_args__ = (
        CheckConstraint(ram_m >= 1, name='ram_positive'),
        CheckConstraint(cpus >= 1, name='cpus_positive'),
        CheckConstraint("boot IN ('c', 'n', 'd')", name='boot_valid'),
        {}
    )
