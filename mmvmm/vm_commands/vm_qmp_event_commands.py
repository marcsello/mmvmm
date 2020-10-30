#!/usr/bin/env python3
from .vm_command_base import VMCommandBase


class VMQMPShutdownCommand(VMCommandBase):

    def execute(self, vm_instance):
        vm_instance._poweroff_cleanup()


class VMQMPNegotiationCompleteCommand(VMCommandBase):

    def execute(self, vm_instance):
        vm_instance._mark_running()

class VMQMPNegotiationFailedCommand(VMCommandBase):

    def execute(self, vm_instance):
        vm_instance._investigate_vm_onlineness()

class VMQMPConnectionProblemsCommand(VMCommandBase):

    def execute(self, vm_instance):
        vm_instance._investigate_vm_onlineness()