#!/usr/bin/env python3
import os
import time
import socket
import json
from threading import Thread, Lock
import queue

import logging

# TODO: This module could use a LOT of work


class QMPMonitor(Thread):

    def __init__(self):
        Thread.__init__(self)

        matches = 0
        while True:  # Amugy megvan az eselye, hogy ez a vegtelensegig porog
            self._socket_path = os.path.join("/run", "mmvmm", "qmp_" + ''.join(random.choice(string.ascii_lowercase) for i in range(12 + matches)) + ".sock")
            if os.path.exists(self._socket_path):
                matches += 1
            else:
                break

        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket_fileio = None

        self._active = True
        self._online = False

        self._command_sender_lock = Lock()
        self._response_queue = queue.Queue(1)  # one element only, this is a thread safe class

    def __connect(self):
        self._socket.connect(self._socket_path)
        self._socket_fileio = self._socket.makefile()

    def __recieve_json(self):  # throws: JSON error
        data_raw = self._socket_fileio.readline()  # Idea stolen from here: https://git.qemu.org/?p=qemu.git;a=blob;f=scripts/qmp/qmp.py;h=5c8cf6a05658979ce235c53bdf0a3064f5e00d09;hb=HEAD

        if data_raw:
            return json.loads(data_raw)
        else:
            return None

    def __send_json(self, data):
        data_raw = json.dumps(data).encode('utf-8')
        return self.__socket.sendall(data_raw)  # should raise exception

    def __negotiation(self):  # returns: bool successful negotiation

        banner = self.__recieve_json()

        if not "QMP" in banner:
            return False

        self.__send_json({"execute": "qmp_capabilities"})

        response = self.__recieve_json()

        return "return" in response

    def get_sock_path(self):
        return self.__socket_path

    def disconnect(self, cleanup=False):
        self._active = False
        self.__socket.close()

        if cleanup and os.path.exists(self.__socket_path):  # useful when using SIGKILL on QEMU
            os.remove(self.__socket_path)

    def run(self):
        # connect

        retries = 5
        connected = False
        while self._active:  # wait for qemu
            time.sleep(2)
            try:
                self.__connect()
                connected = True
                break  # no exception raised during connect

            except FileNotFoundError:  # QEMU is slooooooow, and the socket is not created yet

                retries -= 1
                if retries == 0:
                    logging.log(logging.ERROR, "Couldn't connect to QMP after 5 attempts")
                    return
                else:
                    logging.log(logging.DEBUG, "Failed to connect to QMP. Retrying...")

            except ConnectionRefusedError:  # The socket is there... but it refuses connection... probably QEMU crashed or something
                logging.log(logging.ERROR, "Connection refused while connecting to QMP (vm crashed?)")
                return

        if not connected:  # probably active turned to false
            return

        # negotiate

        if not self.__negotiation():
            logging.log(logging.ERROR, "Negotiation failed with QMP protocol on: " + self.__socket_path)
            self.__socket.close()
            return
        else:
            logging.log(logging.DEBUG, "Negotiated with QMP")

        # run
        # from now on, this thread simply functions as a reciever thread for the issued commands

        self._online = True

        while self._active:

            data = self.__recieve_json()

            if not data:  # None indicates closed stuff
                break

            if "event" in data:  # we are going to ignore those for now
                logging.log(logging.DEBUG, "QMP event happened: " + data['event'])

            elif "return" in data:
                logging.log(logging.DEBUG, "QMP command successful")
                self.__response_queue.put(data)  # this also signals the thread to continue, and also blocks this thread if the previous response is not processed yet

            elif "error" in data:
                logging.log(logging.ERROR, "QMP command returned error: " + data['error']['class'])
                self.__response_queue.put(data)

            else:
                logging.log(logging.WARNING, "Unknown QMP message recieved")

            # so we ignore everything

        # not run

        self._online = False
        self.__socket.close()

        logging.log(logging.DEBUG, "QMP session closed")
        self._active = False

    def qmp_is_online(self):
        return self._online  # changing this is atomic, thus not requiring a lock

    def qmp_send_command(self, cmd, _timeout=None):  # this should be used internally BUT only for user command (not negotiating and stuff)
        # we must ensure that only one command is processed at a given moment, so that any response the reciever thread recieves is belongs to this command
        # This method should never be called from the reviecer thread, because that might cause dead lock!

        with self.__command_sender_lock:

            if not self._online:  # this also prevents invoking this command, while the thread is dead (only if it was closed gracefully)
                raise ConnectionError()

            self.__send_json(cmd)

            try:
                return self.__response_queue.get(timeout=_timeout)

            except Queue.Empty:  # there was no response
                return None
