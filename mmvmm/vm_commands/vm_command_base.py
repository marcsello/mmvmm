#!/usr/bin/env python3
from abc import ABC, abstractmethod

from vm_instance import VMInstance


class VMCommandBase(ABC):

    @abstractmethod
    def execute(self, vm_instance: VMInstance):
        pass
