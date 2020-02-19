#!/usr/bin/env python3
from objectstore import ObjectStore
from vm_manager import VMMAnager


def main():
    objectstore = ObjectStore(port=2379)
    vmmanager = VMMAnager(objectstore)


if __name__ == "__main__":
    main()
