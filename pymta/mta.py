# -*- coding: UTF-8 -*-
# 
# The MIT License
# 
# Copyright (c) 2008-2009 Felix Schwarz <felix.schwarz@oss.schwarz.eu>
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

import socket
from threading import Event
import time

from pymta.command_parser import WorkerProcess

__all__ = ['PythonMTA']



def forked_child(queue, server_socket, deliverer_class, policy_class, 
                 authenticator_class):
    child = WorkerProcess(queue, server_socket, deliverer_class, policy_class, 
                          authenticator_class)
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
                self._policy_class, self._authenticator_class)
    
    def _start_new_worker_process(self, server_socket):
        """Start a new child worker process which will listen on the given 
        socket and return a reference to the new process."""
        from multiprocessing import Process
        p = Process(target=forked_child, args=self._get_child_args(server_socket))
        p.start()
        return p
    
    def serve_forever(self, use_multiprocessing=True):
        if use_multiprocessing:
            try:
                from multiprocessing import Queue
            except ImportError:
                use_multiprocessing = False
        if not use_multiprocessing:
            from Queue import Queue
        
        self._shutdown_server.clear()
        self._queue = Queue()
        # Put the initial token in the Queue
        self._queue.put(True)
        server_socket = self._build_server_socket()
        if use_multiprocessing:
            for i in range(5):
                p = self._start_new_worker_process(server_socket)
                self._processes.append(p)
            while not self._shutdown_server.isSet():
                time.sleep(1)
            for process in self._processes:
                process.join()
        else:
            forked_child(*self._get_child_args(server_socket))
        server_socket.close()
        self._queue = None
    
    def shutdown_server(self, timeout_seconds=None):
        """This method notifies the server that it should stop listening for 
        new messages and shut down itself. If timeout_seconds was given, the
        method will block for this many seconds at most."""
        self._queue.put(None)
        self._shutdown_server.set()
        # TODO: Looks like we're quitting too fast here.


