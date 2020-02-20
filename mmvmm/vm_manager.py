#!/usr/bin/env python3
from vm import VM
from objectstore import ObjectStore

from exception import UnknownCommandError, UnknownVMError


class VMMAnager(object):

    def __init__(self, objectstore: ObjectStore):
        self._vms = []
        self._vm_map = {}

        self._objectstore = objectstore

        self._load()

    def _rebuild_map(self):
        self._vm_map = {vm.get_name(): vm for vm in self._vms}

    def _load(self):

        descriptions = self._objectstore.get_prefix('/virtualmachines')

        for description in descriptions:
            self.new(description)

    def _save(self, vm: VM):
        description = vm.dump_description()
        self._objectstore.put(f"/virtualmachines/{vm.get_name()}", description)

    def _save_all(self):

        for vm in self._vms:
            self._save(vm)

    ## PUBLIC ##

    def close(self):
        # TODO
        pass

    def get_list(self) -> list:
        return list(self._vm_map.keys())

    def new(self, description):
        vm = VM(description)
        self._vms.append(vm)
        self._rebuild_map()
        self._save(vm)

    def delete(self, name: str):
        vm = self._vm_map[name]
        vm.destroy()  # If not allowed, this should raise an error

        self._vms.remove(vm)
        self._objectstore.delete(f"/virtualmachines/{name}")
        self._rebuild_map()

    def execute_command(self, target: str, cmd: str, args: dict) -> object:

        try:
            vm = self._vm_map[target]
        except KeyError:
            raise UnknownVMError()

        try:
            func = vm.exposed_functions[cmd]
        except KeyError:
            raise UnknownCommandError()

        result = func(**args)

        if func.transformational:
            self._save(vm)

        return result
