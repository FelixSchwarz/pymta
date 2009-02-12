#!/usr/bin/env python


from pymta import PythonMTA
from pymta.test_util import BlackholeDeliverer


if __name__ == '__main__':
    server = PythonMTA('localhost', 8025, BlackholeDeliverer)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


