#!/usr/bin/env python3


class ExposedClassMeta(type):
    def __new__(meta, name, bases, dct):
        exposed_functions = {}

        for key, value in dct.items():
            if hasattr(value, 'exposed'):
                exposed_functions[key] = value
            else:
                if callable(value):
                    setattr(value, 'exposed', False)

            if not hasattr(value, 'transformational') and callable(value):
                setattr(value, 'transformational', False)

        dct['exposed_functions'] = exposed_functions

        return super(ExposedClassMeta, meta).__new__(meta, name, bases, dct)


def exposed(func):
        func.exposed = True
        return func


def transformational(func):
        func.transformational = True
        return func


class ExposedClass(metaclass=ExposedClassMeta):
    __metaclass__ = ExposedClassMeta
