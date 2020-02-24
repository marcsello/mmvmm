#!/usr/bin/env python3

from marshmallow import Schema, fields
from marshmallow.validate import Regexp, Length, OneOf, Range


class MediaDescriptionSchema(Schema):
    type = fields.Str(validate=OneOf(['disk', 'cdrom']))
    path = fields.Str(validate=Regexp('^\/+[^\\0]+$'))  # Only absolute path allowed
    format = fields.Str(validate=OneOf(['raw', 'qcow2']))
    readonly = fields.Boolean()


class NICDesciptionSchema(Schema):
    model = fields.Str(validate=OneOf(['virtio', 'sungem', 'usb-net', 'rtl8139', 'pcnet', 'e1000']))
    mac = fields.Str(validate=Regexp('^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$'))
    master = fields.Str(allow_none=False,)


class VMHardwareDescriptionSchema(Schema):
    cpu = fields.Int(validate=Range(min=1))  # Cpu SMP count
    ram = fields.Int(validate=Range(min=1))  # MByte
    boot = fields.Str(validate=OneOf(['c', 'n', 'd']))
    rtc_utc = fields.Boolean()

    network = fields.Nested(NICDesciptionSchema, many=True)
    media = fields.Nested(MediaDescriptionSchema, many=True)


class VNCDescription(Schema):
    enabled = fields.Boolean()
    port = fields.Int(validate=Range(min=1))


class VMDescriptionSchema(Schema):
    name = fields.Str(validate=[Length(min=1, max=42), Regexp("^[a-z]+[a-z0-1]*$")])
    hardware = fields.Nested(VMHardwareDescriptionSchema, many=False)
    vnc = fields.Nested(VNCDescription, many=False)

