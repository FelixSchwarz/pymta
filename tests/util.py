# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from pythonic_testcase import *

from pymta import SMTPSession
from pymta.api import IAuthenticator
from pymta.test_util import BlackholeDeliverer


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
            self.assert_equals(expected_first_digit, first_code_digit, smtp_reply)

    def send(self, command, data=None, expected_first_digit=2):
        number_replies_before = len(self.command_parser.replies)
        self.session.handle_input(command, data)
        self.assert_equals(number_replies_before + 1, len(self.command_parser.replies))
        code, reply_text = self.command_parser.replies[-1]
        self.check_reply_code(code, reply_text, expected_first_digit=expected_first_digit)
        return (code, reply_text)

    def close_connection(self):
        self.send('quit', expected_first_digit=2)
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals(221, code)
        self.assert_equals('localhost closing connection', reply_text)
        self.assert_false(self.command_parser.open)


