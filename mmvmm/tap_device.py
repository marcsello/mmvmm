#!/usr/bin/env python3
import subprocess
from threading import Lock

from config import Config


class TAPDevice:
    """
    This class issues iproute2 commands to add and remove tap devices required for VM networking
    """
    NAMING_SCHEME = "mmvmm{id}"

    _global_network_lock = Lock()  # protects the _allocated_device_ids list, and the adding and removing of tap devices

    def __init__(self, _devid: int, master: str, mtu: int = 1500):

        self._active = True
        self._devid = _devid
        self._devname = self.create_tapdev_name(self._devid)
        self._masterdevname = master

        with TAPDevice._global_network_lock:
            subprocess.check_call([Config.IP_PATH, "tuntap", "add", "name", self._devname, "mode", "tap"])
            subprocess.check_call([Config.IP_PATH, "link", "set", self._devname, "master", master])
            subprocess.check_call([Config.IP_PATH, "link", "set", self._devname, "mtu", str(mtu)])
            subprocess.check_call([Config.IP_PATH, "link", "set", self._devname, "up"])

    @classmethod
    def create_tapdev_name(cls, _id: int) -> str:
        return cls.NAMING_SCHEME.format(id=_id)

    def update_master(self, master: str):  # This raises exception if master is not available
        if not self._active:
            raise RuntimeError("Device is no longer available")

        with TAPDevice._global_network_lock:
            subprocess.check_call([Config.IP_PATH, "link", "set", self._devname, "master", master])

        self._masterdevname = master

    @property
    def device(self) -> str:
        if not self._active:
            raise RuntimeError("Device is no longer available")

        return self._devname

    @property
    def master(self) -> str:
        if not self._active:
            raise RuntimeError("Device is no longer available")

        return self._masterdevname

    def free(self):
        """
        Free up the tap device. 
        After calling this function, subsequent calls to the objects should not be made. 
        """
        if not self._active:
            raise RuntimeError("Device is no longer available")

        with TAPDevice._global_network_lock:
            subprocess.check_call([Config.IP_PATH, "link", "set", self._devname, "down"])
            subprocess.check_call([Config.IP_PATH, "tuntap", "del", "name", self._devname, "mode", "tap"])

        self._active = False
