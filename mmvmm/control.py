#!/usr/bin/env python3
from functools import wraps
from vm_instance import VMInstance
from vm_manager import VMManager


def _vm_mapped(f):
    @wraps(f)
    def call(self, vm_name: str, *args, **kwargs):
        vm = self._lookup_vm(vm_name)
        return f(self, vm, *args, **kwargs)

    return call


class DaemonControlBase:
    """
    This is the base class for the class exposed to clients over XMLRPC
    Support for vm mapping is implemented here
    """

    def __init__(self, vm_manager: VMManager):
        self._vm_manager = vm_manager

    def _lookup_vm(self, vm_name: str) -> VMInstance:
        return self._vm_manager.get_vm_instance(vm_name)


class DaemonControl(DaemonControlBase):
    """
    This is the class exposed to clients over XMLRPC
    """

    def new(self, description: dict):
        return self._vm_manager.new(description)

    def delete(self, vm_name: str):
        return self._vm_manager.delete(vm_name)

    def get_vm_list(self):
        vms = self._vm_manager.get_all_vms()
        return [vm.vm_name for vm in vms]

    @_vm_mapped
    def start(self, vm: VMInstance):
        return vm.start()

    @_vm_mapped
    def poweroff(self, vm: VMInstance):
        return vm.poweroff()

    @_vm_mapped
    def terminate(self, vm: VMInstance, kill: bool = False):
        return vm.terminate(kill)

    @_vm_mapped
    def reset(self, vm: VMInstance):
        return vm.reset()

    @_vm_mapped
    def is_running(self, vm: VMInstance):
        return vm.is_process_alive

    @_vm_mapped
    def set_autostart(self, vm: VMInstance, autostart: bool):
        return vm.set_autostart(autostart)

    @_vm_mapped
    def update_hardware(self, vm: VMInstance, description: dict):
        return vm.update_hardware(description)

    # NIC stuff

    @_vm_mapped
    def add_nic(self, vm: VMInstance, description: dict):
        return vm.add_nic(description)

    @_vm_mapped
    def del_nic(self, vm: VMInstance, _id: int):
        return vm.del_nic(_id)

    # Media stuff

    @_vm_mapped
    def add_media(self, vm: VMInstance, description: dict):
        return vm.add_media(description)

    @_vm_mapped
    def del_media(self, vm: VMInstance, _id: int):
        return vm.del_media(_id)

    @_vm_mapped
    def info(self, vm: VMInstance):
        return vm.dump_info()
