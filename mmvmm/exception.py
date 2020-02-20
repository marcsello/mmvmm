#!/usr/bin/env python3


class VMManagerError(Exception):
    pass


class UnknownCommandError(VMManagerError):
    pass


class UnknownVMError(VMManagerError):
    pass


class VMError(Exception):

    def __str__(self):
        return "Virtual machine error"


class VMRunningError(VMError):

    def __str__(self):
        return "The virtual machine is running"


class VMNotRunningError(VMError):

    def __str__(self):
        return "The virtual machine is not running"
