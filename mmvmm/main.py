#!/usr/bin/env python3
import os
import sys
import logging
import signal

import pidfile

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
    if '--debug-sqlalchemy' in sys.argv:
        logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)
    if '--debug-scheduler' in sys.argv:
        logging.getLogger('apscheduler.executors.default').setLevel(logging.DEBUG)
        logging.getLogger('apscheduler.scheduler').setLevel(logging.DEBUG)
        logging.getLogger('apscheduler').setLevel(logging.DEBUG)
    else:
        logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
        logging.getLogger('apscheduler.scheduler').setLevel(logging.WARNING)
        logging.getLogger('apscheduler').setLevel(logging.WARNING)

    logging.info("Starting Marcsello's Magical Virtual Machine Manager...")
    create_all()

    vm_manager = VMManager()

    try:
        with UnixStreamXMLRPCServer(Config.CONTROL_SOCKET_PATH, log_requests='--debug-requests' in sys.argv) as server:
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

    except OSError as e:
        logging.error(str(e))
        # Address already in use
        pass

    logging.info("Stopping MMVMM...")
    vm_manager.close()


if __name__ == "__main__":
    os.makedirs(Config.RUN_DIR, mode=0o770, exist_ok=True)
    os.makedirs(Config.QMP_SOCKETS_DIR, mode=0o770, exist_ok=True)
    with pidfile.PIDFile(Config.PIDFILE_PATH):
        main()
