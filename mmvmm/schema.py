#!/usr/bin/env python3

from marshmallow import Schema, fields
from marshmallow.validate import Regexp, Length, OneOf, Range
from marshmallow import RAISE


class MediaDescriptionSchema(Schema):
    type = fields.Str(validate=OneOf(['disk', 'cdrom']), required=True)
    path = fields.Str(validate=Regexp('^\/+[^\\0]+$'), required=True)  # Only absolute path allowed
    format = fields.Str(validate=OneOf(['raw', 'qcow2']), required=True)
    readonly = fields.Boolean(default=False, missing=False)


class NICDesciptionSchema(Schema):
    model = fields.Str(validate=OneOf(['virtio-net', 'sungem', 'usb-net', 'rtl8139', 'pcnet', 'e1000']), default='virtio-net', missing='virtio-net')
    mac = fields.Str(validate=Regexp('^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$'), required=True)
    master = fields.Str(allow_none=False, required=True)


class VMHardwareDescriptionSchema(Schema):
    cpu = fields.Int(validate=Range(min=1), required=True)  # Cpu SMP count
    ram = fields.Int(validate=Range(min=1), required=True)  # MByte
    boot = fields.Str(validate=OneOf(['c', 'n', 'd']), default='d', missing='d')
    rtc_utc = fields.Boolean(default=True, missing=True)

    network = fields.Nested(NICDesciptionSchema, many=True, required=True)
    media = fields.Nested(MediaDescriptionSchema, many=True, required=True)


class VNCDescription(Schema):
    enabled = fields.Boolean(required=True)


class VMDescriptionSchema(Schema):
    hardware = fields.Nested(VMHardwareDescriptionSchema, many=False, required=True)
    vnc = fields.Nested(VNCDescription, many=False, required=True)
    autostart = fields.Boolean(default=False, missing=False)

    class Meta:
        unknown = RAISE


class VMNameSchema(Schema):
        name = fields.Str(validate=[Length(min=1, max=42), Regexp("^[a-z]+[a-z0-9]*$")])

        class Meta:
            unknown = RAISE


class ControlCommandSchema(Schema):
        cmd = fields.Str(validate=Length(min=1), required=True, allow_none=False)
        args = fields.Dict(missing={})
        target = fields.Str(allow_none=True, missing=None)

        class Meta:
            unknown = RAISE
