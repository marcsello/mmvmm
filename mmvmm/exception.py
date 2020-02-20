#!/usr/bin/env python3


class VMManagerError(Exception):
    pass


class UnknownCommandError(VMManagerError):
    pass


class UnknownVMError(VMManagerError):
    pass
