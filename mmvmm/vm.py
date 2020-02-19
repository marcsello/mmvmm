#!/usr/bin/env python3
import subprocess
from marshmallow import Schema, fields
from marshmallow.validate import Regexp, Length


class VMDescriptionSchema(Schema):
    name = fields.Str(validate=[Length(min=1, max=42), Regexp("^[a-z]+[a-z0-1]*$")])


class VMMeta(type):
    def __new__(meta, name, bases, dct):
        exposed_functions = []

        for key, value in dct.items():
            if hasattr(value, 'exposed'):
                exposed_functions.append(value)
            else:
                setattr(value, 'exposed', False)

            if not hasattr(value, 'transformational'):
                setattr(value, 'transformational', False)

        dct['exposed_functions'] = exposed_functions

        return super(VMMeta, meta).__new__(meta, name, bases, dct)


def exposed(func):
        func.exposed = True
        return func


def transformational(func):
        func.transformational = True
        return func


class VM(object):

    __metaclass__ = VMMeta

    description_schema = VMDescriptionSchema(many=False)

    def __init__(self, description: dict):
        self._description = self.description_schema.load(description)

    def destroy(self):
        if self.is_running():
            raise Exception("Can not destory running VM")

    @exposed
    @transformational
    def start(self):
        pass

    @exposed
    def stop(self):
        pass

    @exposed
    def terminate(self):
        pass

    @exposed
    def get_name(self) -> str:
        return self._description['name']

    @exposed
    def is_running(self) -> bool:
        return False

    @exposed
    def dump_description(self) -> dict:
        return self.description_schema.dump(self._description)

    @exposed
    @transformational
    def update_description(self, description):
        self._description.update(
            self.description_schema.load(description, partial=True)
        )
