#!/usr/bin/env python3
import subprocess
from threading import RLock


class TAPDevice(object):
    """
    This class issues iproute2 commands to add and remove tap devices required for VM networking
    """

    _allocated_device_ids = []
    NAMING_SCHEME = "tap{id}"

    _global_network_lock = RLock()  # protects the _allocated_device_ids list, and the adding and removing of tap devices

    def __init__(self, master: str):

        self._active = True

        with TAPDevice._global_network_lock:

            self._devid = 0
            while True:
                if self._devid not in TAPDevice._allocated_device_ids:
                    break
                else:
                    self._devid += 1

            TAPDevice._allocated_device_ids.append(self._devid)
            self._devname = TAPDevice.NAMING_SCHEME.format(id=self._devid)
            self._masterdevname = None

            subprocess.check_call(["ip", "tuntap", "add", "name", self._devname, "mode", "tap"])
            subprocess.check_call(["ip", "link", "set", self._devname, "up"])

            self.update_master(master)

    def update_master(self, master: str):  # This raises exception if master is not available
        if not self._active:
            raise RuntimeError("Device is no longer available")

        with TAPDevice._global_network_lock:
            subprocess.check_call(["ip", "link", "set", self._devname, "master", master])
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
            subprocess.check_call(["ip", "link", "set", self._devname, "down"])
            subprocess.check_call(["ip", "tuntap", "del", "name", self._devname, "mode", "tap"])
            TAPDevice._allocated_device_ids.remove(self._devid)

        self._active = False


