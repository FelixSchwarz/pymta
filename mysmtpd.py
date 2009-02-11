#!/usr/bin/env python


from pymta import PythonMTA, IMTAPolicy


if __name__ == '__main__':
    server = PythonMTA('localhost', 8025, IMTAPolicy)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


