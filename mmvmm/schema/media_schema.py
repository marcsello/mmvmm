#!/usr/bin/env python3
from marshmallow_sqlalchemy import ModelSchema
from marshmallow import fields
from marshmallow.validate import Regexp, OneOf
from marshmallow import RAISE

from model import Media


class MediaSchema(ModelSchema):
    type = fields.Str(validate=OneOf(['disk', 'cdrom']), required=True)
    path = fields.Str(validate=Regexp('^\/+[^\\0]+$'), required=True)  # Only absolute path allowed
    format = fields.Str(validate=OneOf(['raw', 'qcow2']))
    interface = fields.Str(validate=OneOf(['virtio', 'floppy', 'ide']))

    class Meta:
        model = Media
        unknown = RAISE
