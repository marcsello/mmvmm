#!/usr/bin/env python3
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import fields
from marshmallow.validate import OneOf, Range
from marshmallow import RAISE

from model import Hardware

from .nic_schema import NICSchema
from .media_schema import MediaSchema


class HardwareSchema(SQLAlchemyAutoSchema):
    cpus = fields.Int(validate=Range(min=1), required=True)  # Cpu SMP count
    ram_m = fields.Int(validate=Range(min=1), required=True)  # MByte
    boot = fields.Str(validate=OneOf(['c', 'n', 'd']), default='d', missing='d')

    product_uuid = fields.UUID()

    nic = fields.Nested(NICSchema, many=True, required=True)
    media = fields.Nested(MediaSchema, many=True, required=True)

    class Meta:
        exclude = ['vm', 'vm_id']  # Do not allow to change it, and there is no point showing it either
        model = Hardware
        unknown = RAISE
        include_relationships = True
        load_instance = True
        include_fk = True
