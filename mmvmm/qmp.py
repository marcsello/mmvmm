#!/usr/bin/env python3
import os
import time
import socket
import json
import random
import string
import weakref
from threading import Thread, Lock
import queue

import logging

from bettersocket import BetterSocketIO
from utils import JSONSocketWrapper

from vm_commands import VMCommandBase, VMQMPShutdownCommand, VMQMPNegotiationCompleteCommand, \
    VMQMPNegotiationFailedCommand, VMQMPConnectionProblemsCommand


class QMPMonitor(Thread):

    def __init__(self, upper_level_logger: logging.Logger, vm_command_queue: queue.Queue):
        super().__init__()

        self._logger = upper_level_logger.getChild('qmp')

        self._socket_path = QMPMonitor._create_socket_path()

        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._jsonsock = None

        self._active = True  # Exit condition for the reading loop
        self._online = False  # Became true when the QMP connection is negotiated

        self._command_sender_lock = Lock()
        self._response_queue = queue.Queue(1)  # one element only, this is a thread safe class

        self._vm_comand_queue_ref = weakref.ref(vm_command_queue)

    @staticmethod
    def _create_socket_path():
        matches = 0
        while True:
            random_string = ''.join(random.choice(string.ascii_lowercase) for _ in range(12 + matches))
            sock_path = os.path.join("/run", "mmvmm", f"qmp_{random_string}.sock")
            if not os.path.exists(sock_path):
                matches += 1
            else:
                return sock_path

    def _connect(self):
        self._socket.connect(self._socket_path)
        self._jsonsock = JSONSocketWrapper(BetterSocketIO(self._socket))

    def _negotiation(self):  # returns: bool successful negotiation

        banner = self._jsonsock.recv_json()

        if not "QMP" in banner:
            return False

        self._jsonsock.send_json({"execute": "qmp_capabilities"})

        response = self._jsonsock.recv_json()

        return "return" in response

    def _enqueue_vm_command(self, vm_command: VMCommandBase):
        queue = self._vm_comand_queue_ref()
        if queue:
            queue.put(vm_command)
        else:
            self._logger.warning("Could not access VM command queue (VM deleted while running?)")

    def _handle_event(self, event: string, data: dict):
        if event == 'SHUTDOWN':
            self._enqueue_vm_command(VMQMPShutdownCommand())

    def run(self):
        # connect

        retries = 5  # Only retries if the socket is not present
        connected = False  # Becomes true when the connection is established
        while self._active:  # wait for qemu
            time.sleep(2)
            try:
                self._connect()
                connected = True
                break  # no exception raised during connect

            except FileNotFoundError:  # QEMU is slooooooow, and the socket is not created yet

                retries -= 1
                if retries == 0:
                    self._logger.error("Couldn't connect after 5 attempts")
                    self._enqueue_vm_command(VMQMPNegotiationFailedCommand())
                    return
                else:
                    self._logger.debug("Failed to connect. Retrying...")

            except ConnectionRefusedError:  # The socket is there... but it refuses connection... probably QEMU crashed or something. Returning unconditionally
                self._logger.error("Connection refused while connecting. (vm crashed?)")
                self._enqueue_vm_command(VMQMPNegotiationFailedCommand())
                return

            except OSError as e:
                self._logger.error(f"Could not connect: {str(e)}")
                self._enqueue_vm_command(VMQMPNegotiationFailedCommand())
                return

        if not connected:  # probably active turned to false
            self._enqueue_vm_command(VMQMPNegotiationFailedCommand())
            return

        # negotiate

        if not self._negotiation():
            self._logger.warning(f"Negotiation failed with QMP protocol on: {self._socket_path}")
            self._socket.close()
            self._enqueue_vm_command(VMQMPNegotiationFailedCommand())
            return
        else:
            self._logger.debug("Negotiated!")
            self._enqueue_vm_command(VMQMPNegotiationCompleteCommand())

        # run
        # from now on, this thread simply functions as a reciever thread for the issued commands

        self._online = True

        while self._active:

            try:
                data = self._jsonsock.recv_json()
            except (BrokenPipeError, OSError):  # Socket is closed unexpectedly
                self._enqueue_vm_command(VMQMPConnectionProblemsCommand())
                break

            except (json.JSONDecodeError, UnicodeError):
                self._logger.warning("Malformed message received!")
                continue

            if not data:
                continue

            if "event" in data:
                event = data['event']
                self._logger.debug(f"Event happened: {event}")
                self._handle_event(event, data['data'])

            elif "return" in data:
                self._logger.debug("Command successful")
                # this also signals the thread to continue, and also blocks this thread if the previous response is not processed yet
                self._response_queue.put(data)

            elif "error" in data:
                self._logger.error(f"Command returned error: {data['error']['class']}")
                self._response_queue.put(data)

            else:
                self._logger.warning("Unknown message recieved")

        # active became false (or connection closed unexpectedly):

        self._online = False
        self._socket.close()

        self._logger.debug("Session closed")
        self._active = False

    def get_sock_path(self):
        return self._socket_path

    def disconnect(self, cleanup: bool = False):
        self._active = False
        self._socket.close()

        if cleanup and os.path.exists(self._socket_path):  # useful when using SIGKILL on QEMU
            os.remove(self._socket_path)

    def is_online(self):
        return self._online  # changing this is atomic, thus not requiring a lock

    def send_command(self, cmd: dict, _timeout: float = None):
        """
        This function sends a command to the QMP and waits it's response.
        """

        with self._command_sender_lock:

            # this is moved inside the locked area to ensure that if a command caused QMP to disconnect, others waiting for the lock will fail
            if not self._online:
                raise ConnectionError("QMP is offline")

            try:
                self._jsonsock.send_json(cmd)
            except (BrokenPipeError, OSError):  # The pipe have borked
                self._logger.debug("Error while sending command. (VM crashed?)")
                self._online = False
                self._enqueue_vm_command(VMQMPConnectionProblemsCommand())
                return None

            try:
                return self._response_queue.get(timeout=_timeout)

            except queue.Empty:  # there was no response
                return None
