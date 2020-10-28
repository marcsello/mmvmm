#!/usr/bin/env python3
from marshmallow_sqlalchemy import ModelSchema
from marshmallow import fields
from marshmallow.validate import Regexp, Length, OneOf, Range
from marshmallow import RAISE

from model import NIC


class NICSchema(ModelSchema):
    model = fields.Str(validate=OneOf(['virtio-net', 'sungem', 'usb-net', 'rtl8139', 'pcnet', 'e1000']),
                       default='virtio-net', missing='virtio-net')
    mac = fields.Str(validate=Regexp('^([0-9A-Fa-f]{2}[:]){5}([0-9A-Fa-f]{2})$'), required=True)
    master = fields.Str(validate=Length(50), allow_none=False, required=True)
    mtu = fields.Integer(validate=Range(min_inclusive=True, min=1), allow_none=False, default=1500, missing=1500)

    class Meta:
        model = NIC
        unknown = RAISE
