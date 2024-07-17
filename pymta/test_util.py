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
from unittest import TestCase
import warnings

from pycerberus.errors import InvalidDataError

from .api import IAuthenticator, IMessageDeliverer, IMTAPolicy
from .compat import b64encode, queue
from .mta import PythonMTA
from .session import SMTPSession


__all__ = [
    'BlackholeDeliverer',
    'CommandParserHelper',
    'DebuggingMTA',
    'MTAThread',
    'SMTPTestCase',
    'SMTPTestHelper',
]


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
        # Python 2 compat
        is_alive = self.is_alive() if hasattr(self, 'is_alive') else self.isAlive()
        if is_alive:
            print("WARNING: Thread still alive. Timeout while waiting for termination!")



class SMTPTestHelper(object):
    def __init__(self, policy_class=IMTAPolicy, authenticator_class=None):
        self.hostname = 'localhost'
        self.listen_port = random.randint(8000, 40000)
        self.deliverer = BlackholeDeliverer
        self.mta = DebuggingMTA(
            self.hostname,
            self.listen_port,
            deliverer_class     = self.deliverer,
            policy_class        = policy_class,
            authenticator_class = authenticator_class,
        )
        self.mta_thread = None

    def start_mta(self, wait_until_ready=True):
        """Starts the MTA in a separate thread."""
        if self.mta_thread is not None:
            self.stop_mta()
        self.mta_thread = MTAThread(self.mta)
        self.mta_thread.start()
        if wait_until_ready:
            self._try_to_connect_to_mta(self.hostname, self.listen_port)
        return (self.hostname, self.listen_port)

    def _try_to_connect_to_mta(self, host, port):
        tries = 0
        while tries < 10:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.connect((host, port))
            except socket.error:
                try:
                    sock.close()
                except socket.error:
                    pass
                tries += 1
                time.sleep(0.1)
            else:
                sock.close()
                return
        raise AssertionError('MTA not reachable on port %d' % (port,))

    def stop_mta(self):
        if self.mta_thread is not None:
            self.mta_thread.stop()
            self.mta_thread = None

    def get_received_messages(self):
        """Return a list of received messages which are stored in the
        BlackholeDeliverer."""
        return self.deliverer.received_messages


class SMTPTestCase(TestCase):
    """The SMTPTestCase is a unittest.TestCase and provides you with a running
    MTA listening on 'localhost:[8000-40000]' which you can use in your
    tests. No messages will be delivered to the outside world because the MTA
    configured by default uses the BlackholeDeliverer.

    Please make sure that you call the super method for setUp and tearDown."""

    def setUp(self):
        warnings.warn(f'SMTPTestCase is deprecated, use SMTPTestHelper instead', DeprecationWarning, stacklevel=2)
        super(SMTPTestCase, self).setUp()
        self._helper = SMTPTestHelper()
        self._helper.start_mta()

    @property
    def hostname(self):
        return self._helper.hostname

    @property
    def listen_port(self):
        return self._helper.listen_port

    def tearDown(self):
        """Stops the MTA thread."""
        self._helper.stop_mta()
        super(SMTPTestCase, self).tearDown()

    def get_received_messages(self):
        """Return a list of received messages which are stored in the
        BlackholeDeliverer."""
        return self._helper.get_received_messages()



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


class CommandParserHelper(object):
    def __init__(self, policy=None, authenticator=None):
        self.deliverer = None
        self.command_parser = MockCommandParser()
        self.deliverer = BlackholeDeliverer()
        self.session = self.new_session(policy=policy, authenticator=authenticator)

    def new_session(self, policy=None, authenticator=None):
        session = SMTPSession(
            command_parser = self.command_parser,
            deliverer      = self.deliverer,
            policy         = policy,
            authenticator  = authenticator,
        )
        session.new_connection('127.0.0.1', 4567)
        return session

    def check_last_code(self, expected_code):
        code, reply_text = self.last_reply()
        assert code == expected_code
        return reply_text

    def check_reply_code(self, code, reply_text, expected_first_digit):
        first_code_digit = int(str(code)[0])
        smtp_reply = "%s %s" % (code, reply_text)
        if expected_first_digit is not None:
            assert first_code_digit == expected_first_digit, smtp_reply

    def ehlo(self):
        self.send_valid('ehlo', 'fnord')

    def helo(self):
        self.send_valid('helo', 'fnord')

    def last_reply(self):
        return self.command_parser.replies[-1]

    def last_server_message(self):
        last_code, last_message = self.last_reply()
        return last_message

    def send(self, command, data=None, expected_first_digit=2):
        number_replies_before = len(self.command_parser.replies)
        self.session.handle_input(command, data)
        assert len(self.command_parser.replies) == number_replies_before + 1
        code, reply_text = self.command_parser.replies[-1]
        self.check_reply_code(code, reply_text, expected_first_digit=int(expected_first_digit))
        return (code, reply_text)

    def send_invalid(self, command, data=None):
        return self.send(command, data=data, expected_first_digit=5)

    def send_valid(self, command, data=None):
        return self.send(command, data=data, expected_first_digit=2)

    def send_auth_login(self, username_b64=None, password_b64=None, expect_username_error=False, reduce_roundtrips=True):
        previous_replies = len(self.command_parser.replies)
        expected_code = 334 if not expect_username_error else 501
        if reduce_roundtrips:
            self.send('AUTH LOGIN', username_b64, expected_first_digit=str(expected_code)[0])
            nr_replies = 1
        else:
            self.send('AUTH LOGIN', expected_first_digit=3)
            code, reply_text = self._handle_auth_credentials(username_b64)
            assert code == 334
            nr_replies = 2
        if expect_username_error:
            assert len(self.command_parser.replies) == previous_replies+nr_replies
            return self.last_reply()
        assert password_b64 is not None

        reply_text = self.check_last_code(expected_code)
        assert reply_text == b64encode('Password:')
        self._handle_auth_credentials(password_b64)
        assert len(self.command_parser.replies) == previous_replies+nr_replies+1
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
        assert code == 221
        assert reply_text == 'localhost closing connection'
        assert not self.command_parser.open
