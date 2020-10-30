#!/usr/bin/env python3
from abc import ABC, abstractmethod


# Note: The VMInstance can not be imported here, because it would cause circular-dependency
# Some sane restructuring of the VMInstance (super)class should solve this issue

class VMCommandBase(ABC):

    @abstractmethod
    def execute(self, vm_instance):
        pass
