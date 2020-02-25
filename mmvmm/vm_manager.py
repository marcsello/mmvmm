#!/usr/bin/env python3
import logging
from vm import VM
from objectstore import ObjectStore

from exception import UnknownCommandError, UnknownVMError, VMNotRunningError, VMRunningError

from expose import ExposedClass, exposed, transformational

import time


class VMMAnager(ExposedClass):  # TODO: Split this into two classes

    def __init__(self, objectstore: ObjectStore):
        self._vms = []
        self._vm_map = {}

        self._objectstore = objectstore

        self._load()

    def _rebuild_map(self):
        self._vm_map = {vm.get_name(): vm for vm in self._vms}

    def _load(self):

        descriptions = self._objectstore.get_prefix('/virtualmachines')

        for name, description in descriptions.items():
            try:
                self.new(description)
            except Exception as e:
                logging.error(f"Something went wrong while loading virtual machine {description['name'] if 'name' in description else 'UNKNOWN'}: {str(e)} - VM skipped!")

    def _save(self, vm: VM):
        description = vm.dump_description()
        self._objectstore.put(f"/virtualmachines/{vm.get_name()}", description)

    def _save_all(self):

        for vm in self._vms:
            self._save(vm)

    ## PUBLIC ##

    def close(self, forced=False):
        at_least_one_powered_on = False
        for vm in self._vms:
            try:

                if forced:
                    vm.terminate()
                else:
                    vm.poweroff()

                at_least_one_powered_on = True  # Will be called if the above functions not raised an error, meaning that there is a runnning VM
            except VMNotRunningError:
                pass

        if at_least_one_powered_on:
            logging.warning("Virtual machines are still running... Waiting for them to power off properly...")

        while at_least_one_powered_on:
            time.sleep(1)
            at_least_one_powered_on = False
            for vm in self._vms:
                if vm.is_running():
                    at_least_one_powered_on = True

    @exposed
    def get_list(self) -> list:
        return list(self._vm_map.keys())

    @exposed
    @transformational
    def new(self, description):
        logging.debug(f"Loading VM from description: {description}")
        vm = VM(description)

        if vm.get_name() in self._vm_map.keys():
            raise KeyError("A virtual machine with this name already exists...")

        self._vms.append(vm)
        self._rebuild_map()
        self._save(vm)
        logging.info(f"New virtual machine created: {vm.get_name()}")

    @exposed
    @transformational
    def delete(self, name: str):
        vm = self._vm_map[name]
        vm.destroy()  # If not allowed, this should raise an error

        self._vms.remove(vm)
        self._objectstore.delete(f"/virtualmachines/{name}")
        self._rebuild_map()
        logging.info(f"Virtual machine deleted: {name}")

    @exposed
    @transformational
    def sync(self):
        # Delete all not running Virtual machines
        logging.info("Syncrhronizing all virtual machines with their descriptions....")
        nowarn = []
        for vm_name in self._vm_map.keys():

            try:
                self.delete(vm_name)
            except VMRunningError:
                nowarn.append(vm_name)
                logging.warning(f"Couldn't sync {vm_name}. It's still running")

        # Load them back
        descriptions = self._objectstore.get_prefix('/virtualmachines')
        for name, description in descriptions.items():
            try:
                self.new(description)
            except KeyError as e:
                if description['name'] not in nowarn:
                    logging.error(f"Couldn't reload {description['name']}. {str(e)} (Duplicate id?)")

    def execute_command(self, target: str, cmd: str, args: dict) -> object:

        if not target:
            try:
                func = self.exposed_functions[cmd]
            except KeyError:
                raise UnknownCommandError()

            result = func(self, **args)

        else:

            try:
                vm = self._vm_map[target]
            except KeyError:
                raise UnknownVMError()

            try:
                func = vm.exposed_functions[cmd]
            except KeyError:
                raise UnknownCommandError()

            result = func(vm, **args)  # TODO: The func should be an object member already

            if func.transformational:
                self._save(vm)

        return result
