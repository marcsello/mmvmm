#!/usr/bin/env python3
from marshmallow_sqlalchemy import ModelSchema
from marshmallow import fields
from marshmallow.validate import OneOf, Range
from marshmallow import RAISE

from model import Hardware

from .nic_schema import NICSchema
from .media_schema import MediaSchema


class HardwareSchema(ModelSchema):
    cpus = fields.Int(validate=Range(min=1), required=True)  # Cpu SMP count
    ram_m = fields.Int(validate=Range(min=1), required=True)  # MByte
    boot = fields.Str(validate=OneOf(['c', 'n', 'd']), default='d', missing='d')

    nic = fields.Nested(NICSchema, many=True, required=True)
    media = fields.Nested(MediaSchema, many=True, required=True)

    class Meta:
        model = Hardware
        unknown = RAISE
