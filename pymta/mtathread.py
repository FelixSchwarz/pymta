# -*- coding: UTF-8 -*-
# 
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

import asyncore
import select
import threading

__all__ = ['MTAThread']


class MTAThread(threading.Thread):
    """This class is not needed for the MTA but a helper class to run a server
    in a separate thread which is helpful for unit testing. I guess others will
    need a class like this too so I added it to the library code itself."""

    def __init__(self, server):
        threading.Thread.__init__(self)
        self.stop_event = threading.Event()
        self.server = server

    def run(self):
        "Just run in a loop until stop() is called."
        while not self.stop_event.isSet():
            try:
                asyncore.loop(timeout=0.1)
            except select.error, e:
                if e.args[0] != errno.EBADF:
                    raise

    def stop(self, timeout_seconds=5.0):
        """Stop the mailsink and shut down this thread. timeout_seconds
        specifies how long the caller should wait for the mailsink server to
        close down (default: 5 seconds). If the server did not stop in time, a
        warning message is printed."""
        self.stop_event.set()
        self.server.close()
        threading.Thread.join(self, timeout=timeout_seconds)
        if self.isAlive():
            print "WARNING: Thread still alive. Timeout while waiting for " + \
                      "termination!"

