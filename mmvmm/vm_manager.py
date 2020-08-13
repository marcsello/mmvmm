#!/usr/bin/env python3
import logging
from vm import VM

from exception import UnknownCommandError, UnknownVMError, VMNotRunningError, VMRunningError

from expose import ExposedClass, exposed, transformational

import time


class VMMAnager(ExposedClass):  # TODO: Split this into two classes

    def __init__(self):
        self._logger = logging.getLogger("manager")

    ## PUBLIC ##

    def close(self, forced: bool = False, timeout: int = 60):
        at_least_one_powered_on = False
        for vm in self._vms:
            try:

                if forced:
                    vm.terminate()
                else:
                    vm.poweroff()

                self._logger.debug(f"VM {vm.get_name()} is still running...")
                at_least_one_powered_on = True  # Will be called if the above functions not raised an error, meaning that there is a runnning VM
            except VMNotRunningError:
                pass

        if at_least_one_powered_on:
            self._logger.warning(f"Virtual machines are still running... Waiting for them to power off properly... (timeout: {timeout}sec)")

            wait_started = time.time()

            while at_least_one_powered_on:
                time.sleep(1)

                if (time.time() - wait_started) > timeout:
                    self._logger.warning("Waiting for shutdown time expired. Killing VMs forcefully...")
                    for vm in self._vms:

                        try:
                            vm.terminate(kill=True)
                        except VMNotRunningError:
                            pass

                    break
                else:
                    at_least_one_powered_on = False
                    for vm in self._vms:
                        if vm.is_running():
                            at_least_one_powered_on = True

        self._vms = []

    def autostart(self):
        """
        Start all VMs marked as autostart.
        """
        self._logger.info("Starting all VMs marked as autostart.")
        for vm in self._vms:
            vm.autostart()

    @exposed
    def get_list(self) -> list:
        return list(self._vm_map.keys())

    @exposed
    @transformational
    def new(self, name: str, description: dict):
        self._logger.debug(f"Loading VM {name} from description: {description}")

        if name in self._vm_map.keys():
            raise KeyError("A virtual machine with this name already exists...")

        vm = VM(name, description)

        self._vms.append(vm)
        self._rebuild_map()
        self._save(vm)
        self._logger.info(f"New virtual machine created: {vm.get_name()}")

    @exposed
    @transformational
    def delete(self, name: str):
        vm = self._vm_map[name]
        vm.destroy()  # If not allowed, this should raise an error

        # no error raised... continuing
        self._vms.remove(vm)
        success = self._objectstore.delete_prefix(f"/virtualmachines/{name}/")
        if not success:
            self._logger.error(f"Failed to delete /virtualmachines/{name}/ from etcd!")

        self._rebuild_map()
        self._logger.info(f"Virtual machine deleted: {name}")

    @exposed
    @transformational
    def sync(self):
        # Delete all not running Virtual machines
        self._logger.info("Syncrhronizing all virtual machines with their descriptions....")
        nowarn = []
        for vm_name in self._vm_map.keys():

            try:
                self.delete(vm_name)
            except VMRunningError:
                nowarn.append(vm_name)
                self._logger.warning(f"Couldn't sync {vm_name}. It's still running")

        # Load them back
        descriptions = self._objectstore.get_prefix('/virtualmachines')
        for name, description in descriptions.items():
            try:
                self.new(name, description)
            except KeyError as e:
                if name not in nowarn:
                    self._logger.error(f"Couldn't reload {name}. {str(e)} (Duplicate id?)")

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
