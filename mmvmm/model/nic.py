#!/usr/bin/env python3
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, CheckConstraint
from sqlalchemy.orm import backref, relationship

from .db import Base


class NIC(Base):
    __tablename__ = "nic"

    id = Column(Integer, nullable=False, primary_key=True, autoincrement=True)

    hardware_id = Column(Integer, ForeignKey('hardware.id'))
    hardware = relationship("Hardware", backref=backref("nic", lazy=True, uselist=True))

    model = Column(String(15), default='virtio-net', nullable=False)
    mac = Column(String(17), nullable=False)
    master = Column(String(50), nullable=False)
    mtu = Column(Integer, nullable=False, default=1500)

    __table_args__ = (
        CheckConstraint(mtu >= 0, name='mtu_positive'),
        {}
    )
