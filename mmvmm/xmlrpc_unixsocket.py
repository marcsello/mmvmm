from xmlrpc.server import SimpleXMLRPCDispatcher, SimpleXMLRPCRequestHandler
import socketserver
import os


class UnixStreamXMLRPCRequestHandler(SimpleXMLRPCRequestHandler):
    disable_nagle_algorithm = False

    def address_string(self):
        return self.client_address


class UnixStreamXMLRPCServer(socketserver.UnixStreamServer, SimpleXMLRPCDispatcher):
    def __init__(self, addr, log_requests=True, allow_none=True, encoding=None, bind_and_activate=True, use_builtin_types=True):
        self.logRequests = log_requests
        SimpleXMLRPCDispatcher.__init__(self, allow_none, encoding, use_builtin_types)
        socketserver.UnixStreamServer.__init__(self, addr, UnixStreamXMLRPCRequestHandler, bind_and_activate)
        os.chmod(addr, 0o660)
