#!/usr/bin/env python3
from vm_instance import VMInstance
from .vm_command_base import VMCommandBase


class VMCleanupAfterQMPExitsCommand(VMCommandBase):

    def execute(self, vm_instance: VMInstance):
        vm_instance._poweroff_cleanup()


class VMQMPNegotiationCompleteCommand(VMCommandBase):

    def execute(self, vm_instance: VMInstance):
        vm_instance._mark_running()