#!/usr/bin/env python3
from typing import List
import time
import logging
from vm_instance import VMInstance

from exception import UnknownVMError, VMNotRunningError, VMRunningError
from schema import VMSchema

from model import VM, VMStatus, Session

from apscheduler.schedulers.background import BackgroundScheduler
from threading import Lock


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

                # Wait until the event loop actually starts...
                while not self._vm_instances[vm.id].is_alive():
                    time.sleep(0.5)

        self._periodic_tasks_scheduler = BackgroundScheduler()
        self._periodic_tasks_scheduler.add_job(func=lambda: self._run_periodic_tasks(), trigger="interval", seconds=10)
        self._periodic_tasks_scheduler.start()

        self._vm_instances_lock = Lock()  # We'll need this, because the background scheduler runs on a separate thread

    def _run_periodic_tasks(self):
        with self._vm_instances_lock:
            vms_to_respawn = []
            for vm_id, vm_instance in self._vm_instances.items():
                if not vm_instance.is_alive():
                    self._logger.warning(
                        f"The event loop of vm {vm_instance.name} seems to be crashed. Respawning VM instance and marking it funky"
                    )
                    vms_to_respawn.append(vm_id)
                    if vm_instance.is_process_alive:
                        # more ebbül baj lesz...
                        try:
                            vm_instance._perform_terminate(True)
                        except Exception as e:
                            self._logger.error(f"Error terminating QEMU process while breaking the law: {e}")
                            self._logger.exception(e)

                    vm_instance.flag_funky()

            for vm_id in vms_to_respawn:
                vm_instance = VMInstance(vm_id)
                vm_instance.start_eventloop()
                vm_instance.flag_funky()

                self._vm_instances[vm_id] = vm_instance

    def close(self, forced: bool = False, timeout: int = 60):
        """
        Closes the VM manager.
        After calling this this manager instance should be discarded
        """

        self._periodic_tasks_scheduler.shutdown()  # This blocks until the scheduler actually stopped
        # We don't need to use the lock from now on, because the background scheduler is no longer running
        # Therefore no other threads will access to that dict

        at_least_one_powered_on = False
        for vm in self._vm_instances.values():

            if vm.status not in [VMStatus.STOPPED, VMStatus.NEW]:
                self._logger.debug(
                    f"VM {vm.vm_name} is running. Terminating {'forcefully' if forced else 'gracefully'}")

                if forced:
                    vm.terminate()
                else:
                    vm.poweroff()

                at_least_one_powered_on = True

        if at_least_one_powered_on:
            self._logger.warning(
                f"Virtual machines are still running... Waiting for them to power off properly... (timeout: {timeout}sec)"
            )

            wait_started = time.time()

            while at_least_one_powered_on:
                time.sleep(1)

                if (time.time() - wait_started) > timeout:
                    self._logger.warning("Waiting for shutdown time expired. Killing VMs...")
                    for vm in self._vm_instances.values():

                        if vm.status not in [VMStatus.STOPPED, VMStatus.NEW]:
                            # We can't just kill all then ignore the VMNotRunningError anymore because of the event loop
                            vm.terminate(kill=True)

                    break  # exit the while at_least_powered_on
                else:

                    at_least_one_powered_on = False
                    for vm in self._vm_instances.values():
                        if vm.status not in [VMStatus.STOPPED, VMStatus.NEW]:
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

            with self._vm_instances_lock:
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

            with self._vm_instances_lock:
                self._vm_instances[new_vm.id] = VMInstance(new_vm.id)
                self._vm_instances[new_vm.id].start_eventloop()
            # can not display uuid, because it would require a session to lazy load the hardware info
            self._logger.info(f"New virtual machine created: {new_vm.name}")

    def delete(self, name: str):
        """
        Delete a specific VM
        Ensures the VM to be stopped
        """
        with self._vm_instances_lock:
            with Session() as s:
                vm = s.query(VM).filter_by(name=name).first()

                if not vm:
                    raise UnknownVMError()

                if vm.status != VMStatus.STOPPED:
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
        with self._vm_instances_lock:
            return list(self._vm_instances.values())

    def get_vm_instance(self, name: str) -> VMInstance:
        """
        Get a VM instance
        """
        with self._vm_instances_lock:
            with Session() as s:
                vm = s.query(VM).filter_by(name=name).first()

                if not vm:
                    raise UnknownVMError()

                _id = vm.id

            return self._vm_instances[_id]
