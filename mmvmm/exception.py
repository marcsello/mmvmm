#!/usr/bin/env python3


class VMManagerError(Exception):

    def __str__(self):
        return "Virtual machine manager error"


class UnknownCommandError(VMManagerError):

    def __str__(self):
        return "Unknown command error"


class UnknownVMError(VMManagerError):

    def __str__(self):
        return "Unknown VM error"


class VMError(Exception):

    def __str__(self):
        return "Virtual machine error"


class VMRunningError(VMError):

    def __str__(self):
        return "The virtual machine is running"


class VMNotRunningError(VMError):

    def __str__(self):
        return "The virtual machine is not running"
