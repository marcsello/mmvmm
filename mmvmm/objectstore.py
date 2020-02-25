#!/usr/bin/env python3
import etcd3
import jsonplus
from flatten_dict import flatten, unflatten
import os.path


class ObjectStore(etcd3.Etcd3Client):

    def _put_encoded(self, key: str, value: object):
        encoded_value = jsonplus.dumps(value).encode('utf-8')
        super().put(key, encoded_value)

    def _get_encoded(self, key: str) -> object:
        encoded_value = super().get(key)[0]

        if encoded_value is None:
            return None

        return jsonplus.loads(encoded_value.decode('utf-8'))

    def put(self, basekey: str, value: object):

        if isinstance(value, dict):
            for key, value in flatten(value, reducer='path').items():
                self._put_encoded(os.path.join(basekey, str(key)), value)
        else:
            self._put_encoded(basekey, value)

    def get(self, key: str) -> object:
        return self._get_encoded(key)

    def get_prefix(self, basekey: str) -> list:
        encoded_values = super().get_prefix(basekey)
        flat_dict = {}
        for encoded_value in encoded_values:
            decoded_value = jsonplus.loads(encoded_value[0].decode('utf-8'))
            flat_dict[os.path.relpath(encoded_value[1].key.decode('utf-8'), start=basekey)] = decoded_value

        # print(flat_dict)
        return unflatten(flat_dict, splitter='path')


if __name__ == '__main__':
    data = {
        "name": "demo",
        "hardware": {
            "cpu": 10,
            "ram": 512,
            "boot": "c",
            "network": [
                {"mac": "12:21:12:22:32:11", "master": "br0", "model": "e1000"},
                {"mac": "12:21:12:22:3311", "master": "br0", "model": "virtio-net"}
            ],
            "media": [
                {"path": "/dev/sdb", "readonly": False, "type": "cdrom", "format": "raw"}
            ]
        },
        "vnc": {
            "enabled": True,
            "port": 3
        }
    }
    objs = ObjectStore(port=2379)
    objs.put("/demovirtualmachines/demo", data)
    print(objs.get("/demovirtualmachines/demo/name"))
    print(objs.get("/demovirtualmachines/demo/hardware/network/0/mac"))
    print(objs.get_prefix("/demovirtualmachines/demo"))
