#!/usr/bin/env python3
from marshmallow_sqlalchemy import ModelSchema
from marshmallow import fields, pre_load
from marshmallow.validate import Regexp, Length
from marshmallow import RAISE
from marshmallow_enum import EnumField

from model import VM, VMStatus

from .hardware_schema import HardwareSchema


class VMSchema(ModelSchema):
    name = fields.Str(validate=[Length(min=1, max=42), Regexp("^[a-z]+[a-z0-9]*$")])
    hardware = fields.Nested(HardwareSchema, many=False, required=True)

    status = EnumField(VMStatus)

    vnc_port = fields.Method("get_vnc_port", dump_only=True)

    def get_vnc_port(self, vm) -> str:
        return f":{vm.id}"

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
        model = VM
        unknown = RAISE
        exclude = ['id']  # Id is used internally only and should not be exposed
