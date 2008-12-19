#!/usr/bin/env python


import asyncore

from pymta import PythonMTA, DefaultMTAPolicy


if __name__ == '__main__':
    server = PythonMTA('localhost', 8025, DefaultMTAPolicy)
    try:
        asyncore.loop()
    except KeyboardInterrupt:
        pass


