#!/usr/bin/env python3
import os
import sys
import logging

from vm_manager import VMManager


def main():
    logging.basicConfig(
        filename="", format="%(asctime)s - %(name)s [%(levelname)s]: %(message)s",
        level=logging.DEBUG if '--debug' in sys.argv else logging.INFO
    )
    logging.info("Starting Marcsello's Magical Virtual Machine Manager...")
    os.makedirs("/run/mmvmm", mode=0o770, exist_ok=True)

    vm_manager = VMManager()

    logging.info("MMVMM is ready!")

    if '--no-autostart' not in sys.argv:
        vm_manager.autostart()


if __name__ == "__main__":
    main()
