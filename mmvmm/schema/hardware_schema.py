#!/usr/bin/env python3
from marshmallow_sqlalchemy import ModelSchema
from marshmallow import fields, pre_load
from marshmallow.validate import OneOf, Range
from marshmallow import RAISE

from model import Hardware

from .nic_schema import NICSchema
from .media_schema import MediaSchema


class HardwareSchema(ModelSchema):
    cpus = fields.Int(validate=Range(min=1), required=True)  # Cpu SMP count
    ram_m = fields.Int(validate=Range(min=1), required=True)  # MByte
    boot = fields.Str(validate=OneOf(['c', 'n', 'd']), default='d', missing='d')

    product_uuid = fields.UUID()

    nic = fields.Nested(NICSchema, many=True, required=True)
    media = fields.Nested(MediaSchema, many=True, required=True)

    @pre_load
    def set_nested_session(self, data, **kwargs):
        """Allow nested schemas to use the parent schema's session. This is a
        longstanding bug with marshmallow-sqlalchemy.

        https://github.com/marshmallow-code/marshmallow-sqlalchemy/issues/67
        https://github.com/marshmallow-code/marshmallow/issues/658#issuecomment-328369199
        """
        nested_fields = {k: v for k, v in self.fields.items() if type(v) == fields.Nested}
        for field in nested_fields.values():
            field.schema.session = self.session

        return data

    class Meta:
        exclude = ['vm', 'vm_id']  # Do not allow to change it, and there is no point showing it either
        model = Hardware
        unknown = RAISE
