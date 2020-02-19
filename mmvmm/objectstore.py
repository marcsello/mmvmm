#!/usr/bin/env python3
import etcd3
import jsonplus


class ObjectStore(etcd3.Etcd3Client):

    def put(self, key: str, value: object):
        encoded_value = jsonplus.dumps(value).encode('utf-8')

        super().put(key, encoded_value)

    def get(self, *args, **kwargs) -> object:
        encoded_value = super().get(*args, **kwargs)
        return jsonplus.loads(encoded_value.decode('utf-8'))

    def get_prefix(self, *args, **kwargs) -> list:
        encoded_values = super().get_prefix(*args, **kwargs)
        decoded_values = []
        for encoded_value in encoded_values:
            decoded_values.append(jsonplus.loads(encoded_value[0].decode('utf-8')))

        return decoded_values
