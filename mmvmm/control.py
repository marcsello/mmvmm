#!/usr/bin/env python3
import json
import os
import socket
import select
import logging
from bettersocket import BetterSocketIO
from vm_manager import VMMAnager


from exception import UnknownVMError, UnknownCommandError


class SocketCommandProvider(object):

    SOCKET_PATH = "/run/mmvmm/control.sock"

    def __init__(self):

        try:
            os.unlink(self.SOCKET_PATH)
        except OSError:
            pass

        self._server_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server_sock.bind(self.SOCKET_PATH)
        self._server_sock.listen(5)
        os.chmod(self.SOCKET_PATH, 0o660)

        self._client_sockios = []

        self._active = True

    def get_command_object(self) -> tuple:  # format: {"target" : "vm name", "cmd" : "command", "args" : {}}

        cmd_obj = None

        while (not cmd_obj) and self._active:

            rlist = [self._server_sock] + self._client_sockios

            try:
                readables, _, _ = select.select(rlist, [], [])
            except OSError:
                continue

            for readable in readables:

                if readable is self._server_sock:
                    try:
                        new_client, addr = self._server_sock.accept()
                    except OSError:  # Socket closed
                        continue

                    logging.debug("New control connection!")

                    self._client_sockios.append(BetterSocketIO(new_client))

                else:

                    try:

                        rawdata = readable.readframe()  # may return None... but it does not matter

                    except (ConnectionResetError, BrokenPipeError):
                        readable.close()
                        self._client_sockios.remove(readable)
                        continue

                    try:
                        data = json.loads(rawdata.decode('utf-8'))
                    except (json.JSONDecodeError, UnicodeError) as e:  # JSON and Unicode exceptions
                        logging.error("Connection dropped. Reason: {}".format(str(e)))
                        readable.close()
                        self._client_sockios.remove(readable)
                        continue

                    def result_pusher(result: dict):
                        if readable:
                            readable.sendframe(json.dumps(result).encode('utf-8'))

                    cmd_obj = (data, result_pusher)

        return cmd_obj

    def close(self):
        for client_sockio in self._client_sockios:
            client_sockio.close()

        self._server_sock.close()

        try:
            os.unlink(self.SOCKET_PATH)
        except OSError:
            pass

        self._active = False


class SimpleCommandExecuter(object):

    def __init__(self, command_provider: SocketCommandProvider, vmmanager: VMMAnager):
        self._command_provider = command_provider
        self._vmmanager = vmmanager
        self._active = True

    def loop(self):

        while self._active:
            cmd, result_pusher = self._command_provider.get_command_object() or (None, None)

            if not self._active:  # ha a socket closed, akkor az vissza fog térni none-al, a push command meg fasságot küld a geciba
                break

            if (not isinstance(cmd, dict)) or ('cmd' not in cmd) or ('args' not in cmd) or ('target' not in cmd):  # TODO: use schema
                result_pusher(None)
                continue

            # execute the command

            logging.debug("Executing command: {}".format(cmd['cmd']))
            try:

                result = self._vmmanager.execute_command(
                    cmd['target'],
                    cmd['cmd'],
                    cmd['args']
                )

                result_pusher({"success": True, "result": result})

            except Exception as e:
                logging.exception(e)
                result_pusher({"success": False, "error": str(e)})

    def stop(self):
        self._active = False
        self._command_provider.close()
