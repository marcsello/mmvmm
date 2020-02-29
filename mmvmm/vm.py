#!/usr/bin/env python3
import subprocess
import logging
import copy
import os
import time

from schema import VMDescriptionSchema, VMNameSchema
from expose import ExposedClass, exposed, transformational
from exception import VMRunningError, VMNotRunningError
from threading import RLock

from tap_device import TAPDevice
from qmp import QMPMonitor
from vnc import VNCAllocator

QEMU_BINARY = "/usr/bin/qemu-system-x86_64"


class VM(ExposedClass):

    description_schema = VMDescriptionSchema(many=False)
    name_schema = VMNameSchema(many=False)  # From the few bad solutions this is the least worse

    def __init__(self, name: str, description: dict):
        self._logger = logging.getLogger("vm")

        self._description = self.description_schema.load(description)
        self._name = self.name_schema.load({'name': name})['name']
        self._logger = logging.getLogger("vm").getChild(name)

        self._qmp = None
        self._tapdevs = []

        self._process = None
        self._vnc_port = None

        self._lock = RLock()

    @staticmethod
    def _preexec():  # do not forward signals (Like. SIGINT, SIGTERM)
        os.setpgrp()

    def _poweroff_cleanup(self, timeout: int = 5):

        if self.is_running():
            self._logger.info(f"Qemu process still running. Delaying cleanup. (max. {timeout}sec)")
            wait_started = time.time()
            while self.is_running():
                time.sleep(1)
                if (time.time() - wait_started) > 5:
                    self._logger.warning("Cleanup delay expired. Killing Qemu!")
                    self._process.kill()

        self._logger.debug("Cleaning up...")
        for tapdev in self._tapdevs:
            tapdev.free()

        self._tapdevs = []
        self._qmp.disconnect()  # Fun fact: This will be called from the qmp process
        self._qmp = None

    def _enforce_vm_state(self, running: bool):

        if running != self.is_running():
            if self.is_running():
                raise VMRunningError()
            else:
                raise VMNotRunningError()

    def destroy(self):
        with self._lock:
            if self.is_running():
                raise VMRunningError("Can not destory running VM")

    def autostart(self):
        """
        Starts the VM, if it's marked as autostart. Otherwise does nothing.
        """
        with self._lock:
            if self._description['autostart']:
                try:
                    self.start()
                except VMRunningError:
                    self._logger.debug("Not autostarting because already running... (wtf?)")

    @exposed
    @transformational
    def start(self):
        with self._lock:
            self._enforce_vm_state(False)

            self._logger.info("Starting VM...")

            # The VM is not running. It's safe to kill off the QMP Monitor
            if self._qmp and self._qmp.is_alive():
                self._logger.warning("Closing a zombie QMP Monitor... (maybe the VM was still running?)")
                self._qmp.disconnect(cleanup=True)
                self._qmp.join()

            # === QEMU Setup ===
            args = [QEMU_BINARY, '-monitor', 'none']  # Monitor none disables the QEMU command prompt

            # Could be set to telnet or other device
            args += ['-serial', 'null']

            # could be leaved out to disable kvm
            args += ['-enable-kvm', '-cpu', 'host']

            args += ['-name', self._name]

            # setup VNC
            if self._description['vnc']['enabled']:
                self._vnc_port = VNCAllocator.get_free_vnc_port()
                self._logger.debug(f"bindig VNC to :{self._vnc_port}")
            else:
                self._vnc_port = None
                self._logger.warning("Couldn't allocate a free port for VNC")

            if self._vnc_port:
                args += ['-vnc', f":{self._vnc_port}"]
            else:
                args += ['-display', 'none']

             # Create QMP monitor
            self._qmp = QMPMonitor(self._logger)
            self._qmp.register_event_listener('SHUTDOWN', lambda data: self._poweroff_cleanup())  # meh

            args += ['-qmp', f"unix:{self._qmp.get_sock_path()},server,nowait"]

            # === Virtual Hardware Setup ===
            hardware_desciption = self._description['hardware']

            args += ['-m', str(hardware_desciption['ram'])]
            args += ['-smp', str(hardware_desciption['cpu'])]
            args += ['-boot', str(hardware_desciption['boot'])]

            # stup RTC
            args += ['-rtc']
            if hardware_desciption['rtc_utc']:
                args += ['base=utc']
            else:
                args += ['base=localtime']

            # add media
            for media in hardware_desciption['media']:
                args += ['-drive', f"media={media['type']},format={media['format']},file={media['path'].replace(',',',,')},read-only={'on' if media['readonly'] else 'off'}"]

            # add nic
            for network in hardware_desciption['network']:
                tapdev = TAPDevice(network['master'])
                self._tapdevs.append(tapdev)

                netdevid = f"{self._name}net{len(self._tapdevs)-1}"

                args += ['-netdev', f"tap,id={netdevid},ifname={tapdev.device},script=no,downscript=no"]
                args += ['-device', f"{network['model']},netdev={netdevid},mac={network['mac']}"]

            # === Everything prepared... launch the QEMU process ===

            self._logger.debug(f"Executing command {' '.join(args)}")
            self._process = subprocess.Popen(args, preexec_fn=VM._preexec)  # start the qemu process itself
            self._qmp.start()  # Start the QMP monitor

    @exposed
    def poweroff(self):
        with self._lock:
            self._enforce_vm_state(True)

            self._logger.info("Powering off VM...")

            try:
                self._qmp.send_command({"execute": "system_powerdown"})
            except ConnectionError:  # There was a QMP connection error... Sending SIGTERM to process instead
                self._logger.warning("There was a QMP connection error while attempting to power off the VM. Sending SIGTERM to QEMU instead...")
                self.terminate(False)

    @exposed
    def terminate(self, kill=False):
        with self._lock:
            self._enforce_vm_state(True)

            self._logger.warning("VM is being terminated...")
            self._qmp.disconnect(cleanup=kill)
            if kill:
                self._process.kill()
                self._poweroff_cleanup()
            else:
                self._process.terminate()
                # Poweroff cleanup will be triggered by QMP event

    @exposed
    def reset(self):
        with self._lock:
            self._enforce_vm_state(True)
            self._logger.info("Resetting VM...")
            self._qmp.send_command({"execute": "system_reset"})

    @exposed
    def pause(self):
        with self._lock:
            self._enforce_vm_state(True)
            self._logger.info("Pausing VM...")
            self._qmp.send_command({"execute": "stop"})

    @exposed
    def cont(self):  # continue
        with self._lock:
            self._enforce_vm_state(True)
            self._logger.info("Continuing VM...")
            self._qmp.send_command({"execute": "cont"})

    @exposed
    def get_name(self) -> str:
        with self._lock:
            return self._name

    @exposed
    def get_vnc_port(self) -> int:
        with self._lock:
            self._enforce_vm_state(True)
            return self._vnc_port

    @exposed
    def is_running(self) -> bool:
        with self._lock:
            if not self._process:
                return False

            # the process object exists
            return self._process.poll() is None

    @exposed
    def dump_description(self) -> dict:
        with self._lock:
            return self.description_schema.dump(self._description)

    @exposed
    @transformational
    def update_description(self, new_description: dict):
        """
        Replaces the current description with the supplied one
        """
        with self._lock:
            self._enforce_vm_state(False)

            self._description = self.description_schema.load(new_description)

