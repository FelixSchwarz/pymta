# -*- coding: UTF-8 -*-
"""
This module contains some classes which are probably useful for writing unit
tests using pymta:
- MTAThread enables you to run a MTA in a separate thread so that you can test
  interaction with an in-process MTA.
- DebuggingMTA provides a very simple MTA which just collects all incoming 
  messages so that you can examine then afterwards.
"""
# The MIT License
# 
# Copyright (c) 2008 Felix Schwarz <felix.schwarz@oss.schwarz.eu>
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

from Queue import Queue
import random
import socket
import threading
import time

from pymta.api import IMessageDeliverer, IMTAPolicy
from pymta.lib import PythonicTestCase
from pymta.mta import PythonMTA


__all__ = ['BlackholeDeliverer', 'DebuggingMTA', 'MTAThread', 'SMTPTestCase']


class BlackholeDeliverer(IMessageDeliverer):
    """BlackholeDeliverer just stores all received messages in memory in the 
    class attribute 'received_messages' (which implements a Queue-like 
    interface) so that you can examine the received messages later. """
    
    received_messages = None
    
    def __init__(self):
        super(BlackholeDeliverer, self).__init__()
        self.__class__.received_messages = Queue()
    
    def new_message_accepted(self, msg):
        self.__class__.received_messages.put(msg)


class DebuggingMTA(PythonMTA):
    """DebuggingMTA is a very simple implementation of PythonMTA which just 
    collects all incoming messages so that you can examine then afterwards."""
    
    def __init__(self, *args, **kwargs):
        PythonMTA.__init__(self, *args, **kwargs)
        self.queue = Queue()
    
    def serve_forever(self):
        return super(DebuggingMTA, self).serve_forever(use_multiprocessing=False)


class MTAThread(threading.Thread):
    """This class runs a PythonMTA in a separate thread which is helpful for 
    unit testing.
    
    Attention: Do not use this class together with multiprocessing! 
    http://www.viraj.org/b2evolution/blogs/index.php/2007/02/10/threads_and_fork_a_bad_idea
    """
    
    def __init__(self, server):
        threading.Thread.__init__(self)
        self.server = server
    
    def run(self):
        """Create a new thread which runs the server until stop() is called."""
        self.server.serve_forever()
    
    def stop(self, timeout_seconds=5.0):
        """Stop the mail sink and shut down this thread. timeout_seconds
        specifies how long the caller should wait for the mailsink server to
        close down (default: 5 seconds). If the server did not stop in time, a
        warning message is printed."""
        self.server.shutdown_server()
        threading.Thread.join(self, timeout=timeout_seconds)
        if self.isAlive():
            print "WARNING: Thread still alive. Timeout while waiting for " + \
                      "termination!"


class SMTPTestCase(PythonicTestCase):
    """The SMTPTestCase is a unittest.TestCase and provides you with a running
    MTA listening on 'localhost:[8000-40000]' which you can use in your 
    tests. No messages will be delivered to the outside world because the MTA
    configured by default uses the BlackholeDeliverer.
    
    Please make sure that you call the super method for setUp and tearDown."""
    
    def setUp(self):
        self.super()
        self.hostname = 'localhost'
        self.listen_port = random.randint(8000, 40000)
        self.mta_thread = None
        self.init_mta()
    
    def build_mta(self, hostname, listen_port, deliverer, policy_class=None):
        """Return a PythonMTA instance which is configured according to your
        needs."""
        return DebuggingMTA(hostname, listen_port, deliverer,
                            policy_class=policy_class)
    
    def init_mta(self, policy_class=IMTAPolicy):
        """Starts the MTA in a separate thread with a BlackholeDeliver. This
        method also ensures that the MTA is really listening on the specified
        port."""
        self.stop_mta()
        self.deliverer = BlackholeDeliverer
        self.mta = self.build_mta(self.hostname, self.listen_port, 
                                  self.deliverer, policy_class)
        self.mta_thread = MTAThread(self.mta)
        self.mta_thread.start()
        
        self._try_to_connect_to_mta(self.hostname, self.listen_port)
    
    def _try_to_connect_to_mta(self, host, port):
        tries = 0
        while tries < 10:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, port))
            except socket.error:
                tries += 1
                time.sleep(0.1)
            else:
                return
        assert False, 'MTA not reachable'
    
    def stop_mta(self):
        if self.mta_thread is not None:
            self.mta_thread.stop()
            self.mta_thread = None
    
    def tearDown(self):
        """Stops the MTA thread."""
        self.stop_mta()
        self.super()
    
    def get_received_messages(self):
        """Return a list of received messages which are stored in the 
        BlackholeDeliverer."""
        return self.deliverer.received_messages


