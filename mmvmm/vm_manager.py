#!/usr/bin/env python3
from typing import List
import time
import logging
from vm_instance import VMInstance

from exception import UnknownVMError, VMNotRunningError, VMRunningError
from schema import VMSchema

from model import VM, Session


class VMManager:
    vm_schema = VMSchema(many=False, dump_only=['status', 'since', 'pid'])

    def __init__(self):
        self._logger = logging.getLogger("manager")
        self._vm_instances = {}

        with Session() as s:
            vms = s.query(VM).all()

            for vm in vms:
                self._vm_instances[vm.id] = VMInstance(vm.id)
                self._vm_instances[vm.id].start_eventloop()

    def close(self, forced: bool = False, timeout: int = 60):
        """
        Closes the VM manager.
        After calling this this manager instance should be discarded
        """
        at_least_one_powered_on = False
        for vm in self._vm_instances.values():
            try:

                if forced:
                    vm.terminate()
                else:
                    vm.poweroff()

                self._logger.debug(f"VM {vm.vm_name} is still running...")
                at_least_one_powered_on = True  # Will be called if the above functions not raised an error, meaning that there is a runnning VM
            except VMNotRunningError:
                pass

        if at_least_one_powered_on:
            self._logger.warning(
                f"Virtual machines are still running... Waiting for them to power off properly... (timeout: {timeout}sec)"
            )

            wait_started = time.time()

            while at_least_one_powered_on:
                time.sleep(1)

                if (time.time() - wait_started) > timeout:
                    self._logger.warning("Waiting for shutdown time expired. Killing VMs forcefully...")
                    for vm in self._vm_instances.values():

                        try:
                            vm.terminate(kill=True)
                        except VMNotRunningError:
                            pass

                    break
                else:

                    at_least_one_powered_on = False
                    for vm in self._vm_instances.values():
                        if vm.is_process_alive:
                            at_least_one_powered_on = True

        for vm in self._vm_instances.values():
            # The request to stop event loops arrives after the terminate request
            # So if the terminate could not kill the vm there's no hope
            vm.stop_eventloop()

        self._vm_instances = {}

    def autostart(self):
        """
        Start all VMs marked as autostart.
        """
        with Session() as s:
            autostart_vms = s.query(VM).filter_by(autostart=True).all()

            for vm in autostart_vms:
                self._vm_instances[vm.id].start()

        self._logger.info(f"VMs marked for autostart are started")

    def new(self, description: dict):
        """
        Creates a new vm based on the description
        """
        self._logger.debug(f"Loading VM from description: {description}")
        with Session() as s:

            new_vm = self.vm_schema.load(description, session=s)

            s.add(new_vm)
            s.commit()

            self._vm_instances[new_vm.id] = VMInstance(new_vm.id)
            self._vm_instances[new_vm.id].start_eventloop()
            self._logger.info(f"New virtual machine created: {new_vm.name} with id: {new_vm.id}")

    def delete(self, name: str):
        """
        Delete a specific VM
        Ensures the VM to be stopped
        """
        with Session() as s:
            vm = s.query(VM).filter_by(name=name).first()

            if not vm:
                raise UnknownVMError()

            if vm.is_process_alive:
                raise VMRunningError()

            self._vm_instances[vm.id].stop_eventloop()
            old_name = vm.name
            old_id = vm.id

            s.delete(vm)
            s.commit()
        del self._vm_instances[old_id]  # delete from instances

        self._logger.info(f"Virtual machine deleted: {old_name}")

    def get_all_vms(self) -> List[VMInstance]:
        """
        Get a list of all valid VM instances
        """
        return list(self._vm_instances.values())

    def get_vm_instance(self, name: str) -> VMInstance:
        """
        Get a VM instance
        """
        with Session() as s:
            vm = s.query(VM).filter_by(name=name).first()

            if not vm:
                raise UnknownVMError()

            _id = vm.id

        return self._vm_instances[_id]
