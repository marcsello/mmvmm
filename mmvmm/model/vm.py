#!/usr/bin/env python3
import subprocess
import logging
import os
import time

from .db import Base, handles
from sqlalchemy import String, Column, Integer, Boolean

from exception import VMRunningError, VMNotRunningError
from threading import RLock

from tap_device import TAPDevice
from qmp import QMPMonitor
from vnc import VNCAllocator

QEMU_BINARY = "/usr/bin/qemu-system-x86_64"


class VM(Base):

    __tablename__ = "vms"

    id = Column(Integer, nullable=False, primary_key=True, autoincrement=True)
    name = Column(String(42), nullable=False, unique=True)
    pid = Column(Integer, nullable=True, unique=True)

    def __init__(self):
        self._logger = logging.getLogger("vm").getChild(self.name)

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

    def _start(self):
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

    def _poweroff(self):
        with self._lock:
            self._enforce_vm_state(True)

            self._logger.info("Powering off VM...")

            try:
                self._qmp.send_command({"execute": "system_powerdown"})
            except ConnectionError:  # There was a QMP connection error... Sending SIGTERM to process instead
                self._logger.warning("There was a QMP connection error while attempting to power off the VM. Sending SIGTERM to QEMU instead...")
                self.terminate(False)

    def _terminate(self, kill=False):
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


    def _reset(self):
        with self._lock:
            self._enforce_vm_state(True)
            self._logger.info("Resetting VM...")
            self._qmp.send_command({"execute": "system_reset"})


    def _pause(self):
        with self._lock:
            self._enforce_vm_state(True)
            self._logger.info("Pausing VM...")
            self._qmp.send_command({"execute": "stop"})


    def _cont(self):  # continue
        with self._lock:
            self._enforce_vm_state(True)
            self._logger.info("Continuing VM...")
            self._qmp.send_command({"execute": "cont"})

    def _is_running(self) -> bool:
        with self._lock:
            if not self._process:
                return False

            # the process object exists
            return self._process.poll() is None

