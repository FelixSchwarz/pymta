#!/usr/bin/env python


import asyncore

from pymta import PythonMTA, IMTAPolicy


if __name__ == '__main__':
    server = PythonMTA('localhost', 8025, IMTAPolicy)
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass


