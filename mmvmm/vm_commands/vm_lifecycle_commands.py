#!/usr/bin/env python3
from .vm_command_base import VMCommandBase


class VMStartCommand(VMCommandBase):

    def execute(self, vm_instance):
        vm_instance._perform_start()


class VMPoweroffCommand(VMCommandBase):

    def execute(self, vm_instance):
        vm_instance._perform_poweroff()


class VMResetCommand(VMCommandBase):

    def execute(self, vm_instance):
        vm_instance._perform_reset()


class VMTerminateCommand(VMCommandBase):

    def __init__(self, kill: bool = False):
        self._kill = kill

    def execute(self, vm_instance):
        vm_instance._perform_terminate(self._kill)
