#!/usr/bin/env python3
import os
import sys
import logging
import signal

from config import Config

from vm_manager import VMManager
from control import DaemonControl
from model import create_all

from xmlrpc_unixsocket import UnixStreamXMLRPCServer


def main():
    logging.basicConfig(
        filename="", format="%(asctime)s - %(name)s [%(levelname)s]: %(message)s",
        level=logging.DEBUG if '--debug' in sys.argv else logging.INFO
    )
    if '--debug' in sys.argv:
        logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)

    logging.info("Starting Marcsello's Magical Virtual Machine Manager...")
    create_all()
    os.makedirs(Config.SOCKET_DIR, mode=0o770, exist_ok=True)
    os.makedirs(Config.QMP_SOCKETS_DIR, mode=0o770, exist_ok=True)

    vm_manager = VMManager()

    with UnixStreamXMLRPCServer(Config.CONTROL_SOCKET_PATH) as server:
        server.register_introspection_functions()
        server.register_instance(DaemonControl(vm_manager))

        def signal_handler(signum, frame):
            logging.warning(f"Signal {signum} recieved. Exiting...")
            server._BaseServer__shutdown_request = True
            # this really is the cleanest solution...
            # shutdown() would block until the server exists... but this would cause a dead-lock

        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        logging.info("MMVMM is ready!")

        if '--no-autostart' not in sys.argv:
            vm_manager.autostart()

        server.serve_forever()

    os.remove(Config.CONTROL_SOCKET_PATH)

    logging.info("Stopping MMVMM...")
    vm_manager.close()


if __name__ == "__main__":
    main()
