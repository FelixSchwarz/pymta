# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

import socket
import time
from threading import Event

from pymta.command_parser import WorkerProcess


__all__ = ['PythonMTA']



def run_worker(queue, server_socket, deliverer_class, policy_class,
                 authenticator_class, shutdown_event=None):
    child = WorkerProcess(queue, server_socket, deliverer_class, policy_class,
                          authenticator_class, shutdown_event=shutdown_event)
    child.run()



class PythonMTA(object):
    """Create a new MTA which listens for new connections afterwards.
    local_address is a string containing either the IP oder the DNS
    host name of the interface on which PythonMTA should listen.
    deliverer_class, policy_class and authenticator_class are callables which
    can be used to add custom behavior. Please note that they must be picklable
    if you use forked worker processes (default).
    Every new connection gets their own instance of policy_class and
    authenticator_class so these classes don't have to be thread-safe. If
    you omit the policy, all syntactically valid SMTP commands are
    accepted. If there is no authenticator specified, authentication will
    not be available."""

    def __init__(self, local_address, bind_port, deliverer_class,
                 policy_class=None, authenticator_class=None):
        self._local_address = local_address
        self._bind_port = bind_port
        self._deliverer_class = deliverer_class
        self._policy_class = policy_class
        self._authenticator_class = authenticator_class

        self._queue = None
        self._processes = []
        self._shutdown_server = Event()
        self._server_address = None
        self._server_ready = Event()

    def _try_to_bind_to_socket(self, server_socket):
        tries = 0
        while tries < 10:
            try:
                server_socket.bind((self._local_address, self._bind_port))
            except socket.error:
                tries += 1
                time.sleep(0.1)
            else:
                break

    def _build_server_socket(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # If the server crashed and we restarted it within a very short time
        # frame, prevent 'address already in use' errors.
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        # We want to terminate all children within a reasonable time
        server_socket.settimeout(1)
        self._try_to_bind_to_socket(server_socket)
        # Don't loose connections in the time frame when a new connection was
        # accepted. Python's documentation says the maximum is system dependent
        # but usually 5 so we take that.
        server_socket.listen(5)
        return server_socket

    def _get_child_args(self, server_socket):
        return (self._queue, server_socket, self._deliverer_class,
                self._policy_class, self._authenticator_class,
                self._shutdown_server)

    def _start_new_worker_process(self, server_socket):
        """Start a new child worker process which will listen on the given
        socket and return a reference to the new process."""
        from multiprocessing import Process
        p = Process(target=run_worker, args=self._get_child_args(server_socket))
        p.start()
        return p

    def serve_forever(self, use_multiprocessing=True):
        if use_multiprocessing:
            try:
                from multiprocessing import Event, Queue
            except ImportError:
                use_multiprocessing = False
        if not use_multiprocessing:
            from threading import Event

            from pymta.compat import queue
            Queue = queue.Queue

        # The worker processes need an event which is shared across processes
        # if we use multiprocessing.
        self._shutdown_server = Event()
        self._queue = Queue()
        # Put the initial token in the Queue
        self._queue.put(True)
        server_socket = self._build_server_socket()
        self._server_address = server_socket.getsockname()
        # The server socket is listening already so new connections will be
        # accepted even if the workers were not started yet.
        self._server_ready.set()
        if use_multiprocessing:
            for i in range(5):
                p = self._start_new_worker_process(server_socket)
                self._processes.append(p)
            while not self._shutdown_server.is_set():
                self._shutdown_server.wait(1)
            for process in self._processes:
                process.join()
        else:
            run_worker(*self._get_child_args(server_socket))
        self._server_ready.clear()
        self._server_address = None
        server_socket.close()
        self._queue = None

    def wait_until_ready(self, timeout_seconds=None):
        """Block until the server accepts new connections. Returns False if
        the server was not ready within timeout_seconds."""
        return self._server_ready.wait(timeout_seconds)

    @property
    def server_address(self):
        """The address (host, port) of the server socket or None if the
        server is not running. This is useful if the MTA was started with
        port 0 (the operating system selects a free port)."""
        return self._server_address

    def shutdown_server(self, timeout_seconds=None):
        """This method notifies the server that it should stop listening for
        new messages and shut down itself. If timeout_seconds was given, the
        method will block for this many seconds at most."""
        self._queue.put(None)
        self._shutdown_server.set()
        self._wake_up_worker()
        # TODO: Looks like we're quitting too fast here.

    def _wake_up_worker(self):
        """Connect to the server socket so the worker blocked in "accept()"
        notices the shutdown request immediately. Otherwise the worker would
        only notice the shutdown after the socket timeout."""
        server_address = self._server_address
        if server_address is None:
            return
        host, port = server_address[:2]
        if host in ('', '0.0.0.0'):
            host = '127.0.0.1'
        try:
            sock = socket.create_connection((host, port), timeout=1)
        except socket.error:
            # the worker will notice the shutdown after the socket timeout
            return
        sock.close()
