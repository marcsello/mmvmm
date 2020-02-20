#!/usr/bin/env python3
import os
import sys
import logging
import signal
from objectstore import ObjectStore
from vm_manager import VMMAnager
from control import SocketCommandProvider, SimpleCommandExecuter


def main():
    logging.basicConfig(filename="", format="%(asctime)s - %(levelname)s: %(message)s", level=logging.DEBUG if '--debug' in sys.argv else logging.INFO)
    logging.info("Starting Marcsello's Magical Virtual Machine Manager...")
    os.makedirs("/run/mmvmm", mode=0o770, exist_ok=True)
    objectstore = ObjectStore(port=2379)
    vmmanager = VMMAnager(objectstore)
    command_executer = SimpleCommandExecuter(SocketCommandProvider(), vmmanager)

    # register signal handlers
    def signal_handler(signum, frame):
        command_executer.stop()  # will exit the loop() so sessions can be terminated after

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logging.info("MMVMM is ready!")
    command_executer.loop()

    logging.info("Shutting down MMVMM...")
    vmmanager.close()


if __name__ == "__main__":
    main()
