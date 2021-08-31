#!/usr/bin/env python3
from marshmallow_sqlalchemy import SQLAlchemyAutoSchema
from marshmallow import fields
from marshmallow.validate import Regexp, Length
from marshmallow import RAISE
from marshmallow_enum import EnumField

from model import VM, VMStatus

from .hardware_schema import HardwareSchema


class VMSchema(SQLAlchemyAutoSchema):
    name = fields.Str(validate=[Length(min=1, max=42), Regexp("^[a-z]+[a-z0-9]*$")])
    hardware = fields.Nested(HardwareSchema, many=False, required=True)

    status = EnumField(VMStatus)

    vnc_port = fields.Method("get_vnc_port", dump_only=True)

    def get_vnc_port(self, vm) -> str:
        return f":{vm.id}"

    class Meta:
        model = VM
        unknown = RAISE
        exclude = ['id']  # Id is used internally only and should not be exposed
        include_relationships = True
        load_instance = True
        include_fk = True
