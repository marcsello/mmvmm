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
    objectstore = ObjectStore(
        port=os.environ.get("ETCD_PORT", 2379),
        host=os.environ.get("ETCD_HOST", 'localhost'),
        user=os.environ.get("ETCD_USER"),
        password=os.environ.get("ETCD_PASSWORD")
    )
    vmmanager = VMMAnager(objectstore)
    command_executer = SimpleCommandExecuter(SocketCommandProvider(), vmmanager)

    # register signal handlers
    def signal_handler(signum, frame):
        logging.info(f"Signal {signum} recieved... exiting.")
        command_executer.stop()  # will exit the loop() so sessions can be terminated after

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    logging.info("MMVMM is ready!")
    command_executer.loop()

    logging.info("Shutting down MMVMM...")
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    vmmanager.close()


if __name__ == "__main__":
    main()
