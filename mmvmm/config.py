#!/usr/bin/env python3
import os
import os.path


class Config:
    SOCKET_DIR = os.environ.get("SOCKET_DIR", "/run/mmvmm")
    CONTROL_SOCKET_PATH = os.path.join(os.environ.get("SOCKET_DIR", "/run/mmvmm"), 'control.sock')
    QMP_SOCKETS_DIR = os.path.join(os.environ.get("SOCKET_DIR", "/run/mmvmm"), 'internal')
    QEMU_PATH = os.environ.get("QEMU_PATH", "/usr/bin/qemu-system-x86_64")
    IP_PATH = os.environ.get("IP_PATH", "/sbin/ip")
    DATABASE_URI = os.environ.get("DATABASE_URI", "sqlite:////var/lib/mmvmm/mmvmm.db")
