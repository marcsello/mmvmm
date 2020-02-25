#!/usr/bin/env python3
import subprocess
import logging
from schema import VMDescriptionSchema
from expose import ExposedClass, exposed, transformational
from exception import VMRunningError, VMNotRunningError
from threading import RLock

from tap_device import TAPDevice
from qmp import QMPMonitor
from vnc import VNCAllocator

QEMU_BINARY = "/usr/bin/qemu-system-x86_64"


class VM(ExposedClass):

    description_schema = VMDescriptionSchema(many=False)

    def __init__(self, description: dict):
        self._description = self.description_schema.load(description, many=False)
        self._qmp = None
        self._tapdevs = []

        self._process = None
        self._vnc_port = None

        self._lock = RLock()

    def _poweroff_cleanup(self):
        logging.debug("Cleaning up...")
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

    @exposed
    @transformational
    def start(self):
        with self._lock:
            self._enforce_vm_state(False)

            # The VM is not running. It's safe to kill off the QMP Monitor
            if self._qmp and self._qmp.is_alive():
                logging.warning("Closing a zombie QMP Monitor... (maybe the VM was still running?)")
                self._qmp.disconnect(cleanup=True)
                self._qmp.join()

            # === QEMU Setup ===
            args = [QEMU_BINARY, '-monitor', 'none']  # Monitor none disables the QEMU command prompt

            # Could be set to telnet or other device
            args += ['-serial', 'null']

            # could be leaved out to disable kvm
            args += ['-enable-kvm', '-cpu', 'host']

            args += ['-name', self._description['name']]

            # setup VNC
            if self._description['vnc']['enabled']:
                self._vnc_port = VNCAllocator.get_free_vnc_port()
                logging.debug(f"bindig VNC to :{self._vnc_port}")
            else:
                self._vnc_port = None
                logging.warning("Couldn't allocate a free port for VNC")

            if self._vnc_port:
                args += ['-vnc', f":{self._vnc_port}"]
            else:
                args += ['-display', 'none']

             # Create QMP monitor
            self._qmp = QMPMonitor()
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

                netdevid = f"{self._description['name']}net{len(self._tapdevs)-1}"

                args += ['-netdev', f"tap,id={netdevid},ifname={tapdev.device},script=no,downscript=no"]
                args += ['-device', f"{network['model']},netdev={netdevid},mac={network['mac']}"]

            # === Everything prepared... launch the QEMU process ===

            logging.debug(f"Executing command {' '.join(args)}")
            self._process = subprocess.Popen(args)  # start the qemu process itself
            self._qmp.start()  # Start the QMP monitor

    @exposed
    def poweroff(self):
        with self._lock:
            self._enforce_vm_state(True)
            self._qmp.send_command({"execute": "system_powerdown"})

    @exposed
    def terminate(self, kill=False):
        with self._lock:
            self._enforce_vm_state(True)

            logging.warning("Virtual machine is being terminated...")
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
            self._qmp.send_command({"execute": "system_reset"})

    @exposed
    def pause(self):
        with self._lock:
            self._enforce_vm_state(True)
            self._qmp.send_command({"execute": "stop"})

    @exposed
    def cont(self):  # continue
        with self._lock:
            self._enforce_vm_state(True)
            self._qmp.send_command({"execute": "cont"})

    @exposed
    def get_name(self) -> str:
        with self._lock:
            return self._description['name']

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
    def update_description(self, description):
        with self._lock:
            self._enforce_vm_state(False)

            self._description.update(
                self.description_schema.load(description, partial=True)
            )
