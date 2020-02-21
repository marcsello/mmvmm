#!/usr/bin/env python3

from marshmallow import Schema, fields
from marshmallow.validate import Regexp, Length, OneOf


class MediaDescriptionSchema(Schema):
    type = fields.Str(validate=OneOf(['hda', 'cdrom']))
    path = fields.Str(validate=Regexp('^\/+[^\\0]+$'))


class NICDesciptionSchema(Schema):
    model = fields.Str(validate=OneOf(['virtio', 'sungem', 'usb-net', 'rtl8139', 'pcnet']))
    mac = fields.Str(validate=Regexp('^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$'))


class VMHardwareDescriptionSchema(Schema):
    cpu = fields.Int(validate=Length(min=1))  # Cpu SMP count
    ram = fields.Int(validate=Length(min=1))  # MByte
    boot = fields.Str(validate=OneOf(['c', 'n', 'd']))
    rtc_utc = fields.Boolean()

    network = fields.Nested(NICDesciptionSchema, many=True)
    media = fields.Nested(MediaDescriptionSchema, many=True)


class VMDescriptionSchema(Schema):
    name = fields.Str(validate=[Length(min=1, max=42), Regexp("^[a-z]+[a-z0-1]*$")])
    hardware = fields.Nested(VMHardwareDescriptionSchema, many=False)


