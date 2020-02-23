#!/usr/bin/env python3
# TODO: This module could use a LOT of work
from bettersocket import BetterSocketIO
import json


class JSONSocketWrapper(object):

    def __init__(self, bsocket: BetterSocketIO):
        self._bsocket = socket

    def send_json(self, data: object):
        self._bsocket.sendframe(json.dumps(data).encode('utf-8'))

    def recv_json(self) -> object:
        data = self._bsocket.readframe()

        if data:
            return json.loads(data.decode('utf-8'))

        return None
