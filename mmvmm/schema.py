#!/usr/bin/env python3

from marshmallow import Schema, fields
from marshmallow.validate import Regexp, Length


class VMDescriptionSchema(Schema):
    name = fields.Str(validate=[Length(min=1, max=42), Regexp("^[a-z]+[a-z0-1]*$")])
    cpu = fields.Int(validate=Length(min=1))  # Cpu SMP count
    ram = fields.Int(validate=Length(min=1))  # MByte


