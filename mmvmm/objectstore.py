#!/usr/bin/env python3
import etcd3
import jsonplus
from morph import flatten, unflatten
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
            for key, value in flatten(value, separator='/').items():
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

        return unflatten(flat_dict, separator='/')



