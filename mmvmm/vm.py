#!/usr/bin/env python3
import subprocess

from schema import VMDescriptionSchema
from expose import ExposedClass, exposed, transformational
from exception import VMRunningError, VMNotRunningError

from tap_device import TAPDevice


class VM(ExposedClass):

    description_schema = VMDescriptionSchema(many=False)

    def __init__(self, description: dict):
        self._description = self.description_schema.load(description)

    def destroy(self):
        if self.is_running():
            raise Exception("Can not destory running VM")

    @exposed
    @transformational
    def start(self):
        if self.is_running():
            raise VMRunningError()

    @exposed
    def poweroff(self):
        if not self.is_running():
            raise VMNotRunningError()

    @exposed
    def terminate(self):
        if not self.is_running():
            raise VMNotRunningError()

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

        if self.is_running():
            raise VMRunningError()

        self._description.update(
            self.description_schema.load(description, partial=True)
        )
