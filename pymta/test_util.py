# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT
"""
This module contains some classes which are probably useful for writing unit
tests using pymta:
- MTAThread enables you to run a MTA in a separate thread so that you can test
  interaction with an in-process MTA.
- DebuggingMTA provides a very simple MTA which just collects all incoming
  messages so that you can examine then afterwards.
"""

from __future__ import print_function, unicode_literals

import random
import socket
import threading
import time

from pythonic_testcase import *
from pycerberus.errors import InvalidDataError

from .api import IAuthenticator, IMessageDeliverer, IMTAPolicy
from .compat import b64encode, queue
from .mta import PythonMTA
from .session import SMTPSession


__all__ = ['BlackholeDeliverer', 'DebuggingMTA', 'MTAThread', 'SMTPTestCase']


class BlackholeDeliverer(IMessageDeliverer):
    """BlackholeDeliverer just stores all received messages in memory in the
    class attribute 'received_messages' (which implements a Queue-like
    interface) so that you can examine the received messages later. """

    received_messages = None

    def __init__(self):
        super(BlackholeDeliverer, self).__init__()
        self.__class__.received_messages = queue.Queue()

    def new_message_accepted(self, msg):
        self.__class__.received_messages.put(msg)


class DebuggingMTA(PythonMTA):
    """DebuggingMTA is a very simple implementation of PythonMTA which just
    collects all incoming messages so that you can examine then afterwards."""

    def __init__(self, *args, **kwargs):
        super(DebuggingMTA, self).__init__(*args, **kwargs)
        self.queue = queue.Queue()

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
            print("WARNING: Thread still alive. Timeout while waiting for termination!")


class SMTPTestCase(PythonicTestCase):
    """The SMTPTestCase is a unittest.TestCase and provides you with a running
    MTA listening on 'localhost:[8000-40000]' which you can use in your
    tests. No messages will be delivered to the outside world because the MTA
    configured by default uses the BlackholeDeliverer.

    Please make sure that you call the super method for setUp and tearDown."""

    def setUp(self):
        super(SMTPTestCase, self).setUp()
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
                sock.close()
                return
        assert False, 'MTA not reachable'

    def stop_mta(self):
        if self.mta_thread is not None:
            self.mta_thread.stop()
            self.mta_thread = None

    def tearDown(self):
        """Stops the MTA thread."""
        self.stop_mta()
        super(SMTPTestCase, self).tearDown()

    def get_received_messages(self):
        """Return a list of received messages which are stored in the
        BlackholeDeliverer."""
        return self.deliverer.received_messages



class MockCommandParser(object):
    primary_hostname = 'localhost'

    def __init__(self):
        self.replies = []
        self.messages = []
        self.open = True

    def set_maximum_message_size(self, max_size):
        pass

    def push(self, code, text):
        assert self.open
        self.replies.append((code, text))

    def multiline_push(self, code, lines):
        assert self.open
        self.replies.append((code, lines))

    def close_when_done(self):
        assert self.open
        self.open = False

    def new_message_received(self, msg):
        self.messages.append(msg)

    def switch_to_auth_login_mode(self):
        pass

    def switch_to_command_mode(self):
        pass

    def switch_to_data_mode(self):
        pass


class MockChannel(object):
    def __init__(self):
        self.replies = []

    def write(self, data):
        self.replies.append(data)

    def close(self):
        pass


class DummyAuthenticator(IAuthenticator):
    def authenticate(self, username, password, peer):
        return username == password


class CommandParserTestCase(PythonicTestCase):

    def setUp(self, policy=None):
        super(CommandParserTestCase, self).setUp()
        self.init(policy=policy)

    def tearDown(self):
        if self.command_parser.open:
            self.close_connection()
        super(CommandParserTestCase, self).tearDown()

    def init(self, policy=None, authenticator=None):
        self.command_parser = MockCommandParser()
        self.deliverer = BlackholeDeliverer()
        self.session = SMTPSession(command_parser=self.command_parser,
                                   deliverer=self.deliverer,
                                   policy=policy, authenticator=authenticator)
        self.session.new_connection('127.0.0.1', 4567)

    def check_reply_code(self, code, reply_text, expected_first_digit):
        first_code_digit = int(str(code)[0])
        smtp_reply = "%s %s" % (code, reply_text)
        if expected_first_digit is not None:
            assert_equals(expected_first_digit, first_code_digit, smtp_reply)

    def send(self, command, data=None, expected_first_digit=2):
        number_replies_before = len(self.command_parser.replies)
        self.session.handle_input(command, data)
        assert_length(number_replies_before + 1, self.command_parser.replies)
        code, reply_text = self.command_parser.replies[-1]
        self.check_reply_code(code, reply_text, expected_first_digit=int(expected_first_digit))
        return (code, reply_text)

    def last_reply(self):
        return self.command_parser.replies[-1]

    def send_auth_login(self, username_b64=None, password_b64=None, expect_username_error=False, reduce_roundtrips=True):
        previous_replies = len(self.command_parser.replies)
        expected_code = 334 if not expect_username_error else 501
        if reduce_roundtrips:
            self.send('AUTH LOGIN', username_b64, expected_first_digit=str(expected_code)[0])
            nr_replies = 1
        else:
            self.send('AUTH LOGIN', expected_first_digit=3)
            code, reply_text = self._handle_auth_credentials(username_b64)
            assert_equals(334, code)
            nr_replies = 2
        if expect_username_error:
            assert_length(previous_replies+nr_replies, self.command_parser.replies)
            return self.last_reply()
        assert_not_none(password_b64)

        reply_text = self._check_last_code(expected_code)
        assert_equals(b64encode('Password:'), reply_text)
        self._handle_auth_credentials(password_b64)
        assert_length(previous_replies+nr_replies+1, self.command_parser.replies)
        return self.last_reply()

    def _handle_auth_credentials(self, b64_data):
        try:
            # in production the (non-mock) CommandParser would call this method
            # instead of "session.handle_input()"
            self.session.handle_auth_credentials(b64_data)
        except InvalidDataError as e:
            # emulate code in ".handle_input()"
            reply = (501, e.msg())
            self.command_parser.replies.append(reply)
        return self.last_reply()

    def close_connection(self):
        self.send('quit', expected_first_digit=2)
        code, reply_text = self.command_parser.replies[-1]
        assert_equals(221, code)
        assert_equals('localhost closing connection', reply_text)
        assert_false(self.command_parser.open)

