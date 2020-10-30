#!/usr/bin/env python3
from typing import Tuple
import subprocess
import logging
import os
import time

from sqlalchemy.orm import Session

from threading import Thread, Lock
import queue

from config import Config
from exception import VMRunningError, VMNotRunningError, VMError
from tap_device import TAPDevice
from qmp import QMPMonitor

from model import VM, VMStatus, Session
from schema import VMSchema
from sqlalchemy import func

from vm_commands import VMTerminateCommand, VMPoweroffCommand, VMStartCommand



class VMInstance(Thread):
    vm_schema = VMSchema(many=False, dump_only=['status', 'since', 'pid'])

    def __init__(self, _id: int):
        super().__init__()
        self._id = _id

        self._qmp = None
        self._tapdevs = []

        self._process = None

        self._lock = Lock()
        self._command_queue = queue.Queue()

        name = self.vm_name

        self._logger = logging.getLogger("vm").getChild(name)
        self.setName("Event Loop of " + name)

    def _update_status(self, new_status: VMStatus, session=None):
        """
        Updates the VM status stored in the database

        If no session is provided, than it will create a new one, and commit it.
        If you do provide a session, do not forget to commit it manually.
        """
        if session:
            vm = session.query(VM).get(self._id)
            vm.status = new_status
            vm.since = func.now()
            session.add(vm)
        else:
            with Session() as s:
                vm = s.query(VM).get(self._id)
                vm.status = new_status
                vm.since = func.now()
                s.add(vm)
                s.commit()

    @staticmethod
    def _preexec():  # do not forward signals (Like. SIGINT, SIGTERM)
        os.setpgrp()

    def _poweroff_cleanup(self, qmp_cleanup: bool = False, timeout: int = 5):
        """
        Ideally this is called after a SHUTDOWN event is recieved from the QMP
        OR the process is forcefully killed
        """
        self._update_status(VMStatus.STOPPING)  # In case it wasn't set

        if self._is_process_alive():
            self._logger.info(f"Qemu process still running. Delaying cleanup. (max. {timeout}sec)")
            wait_started = time.time()
            while self._is_process_alive():
                time.sleep(1)
                if (time.time() - wait_started) > timeout:
                    self._logger.warning("Cleanup delay expired. Killing Qemu!")
                    self._process.kill()
                    self._process.wait()
                    break

        self._logger.debug("Cleaning up...")
        for tapdev in self._tapdevs:
            tapdev.free()

        self._tapdevs = []
        self._qmp.disconnect(cleanup=qmp_cleanup)
        self._qmp = None
        self._update_status(VMStatus.STOPPED)

    def _enforce_vm_state(self, running: bool):
        if running != self._is_process_alive():
            if self._is_process_alive():
                raise VMRunningError()
            else:
                raise VMNotRunningError()

    @staticmethod
    def _compile_args(vm: VM, qmp_path: str) -> list:
        # === QEMU Setup ===
        args = [Config.QEMU_PATH, '-monitor', 'none']  # Monitor none disables the QEMU command prompt

        # Could be set to telnet or other device
        args += ['-serial', 'null']

        # could be leaved out to disable kvm
        args += ['-enable-kvm', '-cpu', 'host']

        args += ['-name', vm.name]
        args += ['-vnc', f":{vm.id}"]

        args += ['-qmp', f"unix:{qmp_path},server,nowait"]

        args += ['-m', str(vm.hardware.ram_m)]
        args += ['-smp', str(vm.hardware.cpus)]
        args += ['-boot', vm.hardware.boot]

        # stup RTC
        args += ['-rtc']
        if vm.hardware.rtc_utc:
            args += ['base=utc']
        else:
            args += ['base=localtime']

        # add media
        for media in vm.hardware.media:
            escaped_path = media.path.replace(',', ',,')
            read_only = 'on' if media.readonly else 'off'
            cache = 'writeback' if media.host_cache else 'none'
            args += [
                '-drive',
                f"media={media.type},format={media.format},file={escaped_path},read-only={read_only},if={media.interface},cache={cache}"
            ]

        # add nic
        for nic in vm.hardware.nic:
            # Tapdevs created manually outside
            netdevid = f"{vm.name}net{nic.id}"
            ifname = TAPDevice.create_tapdev_name(nic.id)

            args += ['-netdev', f"tap,id={netdevid},ifname={ifname},script=no,downscript=no"]
            args += ['-device', f"{nic.model},netdev={netdevid},mac={nic.mac}"]

        return args

    def _mark_running(self):
        # Called when the QMP negotiation is complete
        self._update_status(VMStatus.RUNNING)

    def _investigate_vm_onlineness(self):
        # Called when there are problems with the QMP connection or the negotiation is straight up failed
        # Meaning that an existing process is expected to be there
        with Session() as s:
            vm = s.query(VM).get(self._id)
            if not self._is_process_alive():
                if vm.status != VMStatus.STOPPED:
                    self._update_status(VMStatus.STOPPED, s)
                    self._logger.warning("It seems like the QEMU process have crashed")
                    s.commit()

    def _perform_start(self):
        self._enforce_vm_state(False)
        self._update_status(VMStatus.STARTING)
        with Session() as s:
            vm = s.query(VM).get(self._id)
            self._logger.info("Starting VM...")

            # The VM is not running. It's safe to kill off the QMP Monitor
            if self._qmp and self._qmp.is_alive():
                self._logger.warning("Closing a zombie QMP Monitor... (maybe the VM was still running?)")
                self._qmp.disconnect(cleanup=True)
                self._qmp.join()

            # Create QMP monitor
            self._qmp = QMPMonitor(self._logger, self._command_queue)

            qemu_command = self._compile_args(vm, self._qmp.get_sock_path())

            # Create tap devices
            self._logger.debug("Creating tap devices...")
            for nic in vm.hardware.nic:
                try:
                    tapdev = TAPDevice(nic.id, nic.master, nic.mtu)
                except subprocess.CalledProcessError as e:
                    self._logger.error(f"Could not create TAP device: {e}! Aborting VM startup...")
                    self._update_status(VMStatus.STOPPED)
                    return

                self._logger.debug(f"{tapdev.device} created!")
                self._tapdevs.append(tapdev)

            self._logger.debug(f"Executing command {' '.join(qemu_command)}")
            try:
                self._process = subprocess.Popen(qemu_command, preexec_fn=self._preexec)  # start the qemu process itself
            except FileNotFoundError as e:
                self._logger.error(f"Could not launch VM: {e}")
                self._update_status(VMStatus.STOPPED)
                return

            vm.pid = self._process.pid
            self._qmp.start()  # Start the QMP monitor (A negotiation event will mark the VM running)
            s.add(vm)
            s.commit()

    def _perform_poweroff(self):
        self._enforce_vm_state(True)
        self._update_status(VMStatus.STOPPING)
        self._logger.info("Powering off VM...")

        try:
            self._qmp.send_command({"execute": "system_powerdown"})
        except ConnectionError:  # There was a QMP connection error... Sending SIGTERM to process instead
            self._logger.warning(
                "There was a QMP connection error while attempting to power off the VM. Sending SIGTERM to QEMU instead..."
            )
            self._qmp.disconnect()  # We don't want to stuck with a half-working connection
            self.terminate(False)
            self._poweroff_cleanup()  # This won't be called because the QMP connection is not alive

    def _perform_terminate(self, kill=False):
        self._enforce_vm_state(True)
        self._update_status(VMStatus.STOPPING)

        self._logger.warning("VM is being terminated...")
        if kill:
            self._process.kill()
            self._poweroff_cleanup(True)  # Sets the state in the db
        else:
            self._process.terminate()
            # Poweroff cleanup will be triggered by QMP event

    def _perform_reset(self):
        self._enforce_vm_state(True)
        self._logger.info("Resetting VM...")
        self._qmp.send_command({"execute": "system_reset"})


    def _is_process_alive(self) -> bool:
        if not self._process:
            return False

        # the process object exists
        return self._process.poll() is None

    def _run_periodic_tasks(self):
        with Session() as s:
            vm = s.query(VM).get(self._id)
            if not self._is_process_alive():
                if vm.status == VMStatus.RUNNING:
                    # It might be expected for the process to not exists in NEW, STARTING, STOPPING and STOPPED state
                    self._update_status(VMStatus.STOPPED, s)
                    self._logger.warning("It seems like the QEMU process have crashed, and it went unnoticed")
                    s.commit()


    def run(self):  # Main event loop
        self._update_status(VMStatus.STOPPED)  # Ensure that it's stopped before performing any commands
        self._logger.debug("Event loop ready!")
        while True:
            try:
                cmd = self._command_queue.get(timeout=2)
            except queue.Empty:
                with self._lock:
                    self._run_periodic_tasks()
            else:
                if not cmd:
                    break

                with self._lock:
                    try:
                        cmd.execute(self)
                    except VMError as e:
                        self._logger.error(str(e))

        self._logger.debug("Event loop exited!")

    def start(self):
        self._command_queue.put(VMStartCommand())

    def poweroff(self):
        self._command_queue.put(VMPoweroffCommand())

    def terminate(self, kill: bool = False):
        self._command_queue.put(VMTerminateCommand(kill))

    def stop_eventloop(self):
        self._command_queue.put(None)

    def start_eventloop(self):
        # Thread.start() basically
        super(VMInstance, self).start()

    def dump_info(self) -> dict:
        with self._lock:
            with Session() as s:
                vm = s.query(VM).get(self._id)
                return self.vm_schema.dump(vm)

    # Basic getters

    @property
    def is_process_alive(self) -> bool:
        with self._lock:
            return self._is_process_alive()

    @property
    def status(self) -> VMStatus:
        with Session() as s:
            vm = s.query(VM).get(self._id)
            return vm.status

    @property
    def id(self) -> int:
        return self._id

    @property
    # Fun fact: ''name'' overrides Thread.name causing SQLAlchemy logging to go nuts, when it tries to lookup the thread name to log the looking up the name of the thread
    def vm_name(self) -> str:
        with Session() as s:
            vm = s.query(VM).get(self._id)
            return vm.name
