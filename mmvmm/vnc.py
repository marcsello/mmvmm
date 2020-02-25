import socket


class VNCAllocator(object):

    @staticmethod
    def _check_free_port(port: int) -> bool:
        """
        Returns true if the port is free.
        False if something listens on that port
        """
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()

        return result != 0

    @staticmethod
    def get_free_vnc_port() -> int:
        """
        Checks ports starting from 5901...
        returns the first aviliable port.
        Returns None when 5999 reached and no ports aviliable
        """
        for i in range(1, 100):
            if VNCAllocator._check_free_port(5900 + i):
                return i

        return None
