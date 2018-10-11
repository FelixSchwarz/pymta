# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from pythonic_testcase import *

from pymta.api import IMTAPolicy
from pymta.command_parser import SMTPCommandParser
from pymta.test_util import BlackholeDeliverer
from pymta.compat import basestring

from tests.util import MockChannel


class CommandParsingTest(PythonicTestCase):

    def setUp(self):
        super(CommandParsingTest, self).setUp()
        self.deliverer = BlackholeDeliverer()
        self.init_command_parser()

    def init_command_parser(self, policy=None):
        self.parser = SMTPCommandParser(MockChannel(), '127.0.0.1', 12345,
                                        self.deliverer, policy=policy)

    def parse_command(self, input):
        return self.parser._parser.parse(input)

    def test_parse_command_without_arguments(self):
        self.assert_equals(('QUIT', None), self.parse_command('QUIT'))
        self.assert_equals(('RSET', None), self.parse_command('RSET'))
        self.assert_equals(('DATA', None), self.parse_command('DATA'))

    def test_parse_helo(self):
        self.assert_equals(('HELO', 'foo.example.com'),
                         self.parse_command('HELO foo.example.com'))
        # This command is syntactically invalid but the validity of specific
        # commands should not be checked in the parser.
        self.assert_equals(('helo', 'foo example.com'),
                         self.parse_command('helo foo example.com'))

    def test_strip_parameters(self):
        self.assert_equals(('HELO', 'foo.example.com'),
                         self.parse_command('HELO   foo.example.com   '))

    def test_parse_commands_with_colons(self):
        self.assert_equals(('MAIL FROM', 'foo@example.com'),
                        self.parse_command('MAIL FROM: foo@example.com'))
        self.assert_equals(('MAIL FROM', 'foo@example.com'),
                        self.parse_command('MAIL FROM:foo@example.com'))
        self.assert_equals(('MAIL FROM', 'foo@example.com'),
                        self.parse_command('MAIL FROM:  foo@example.com   '))
        self.assert_equals(('RCPT TO', 'foo@example.com, bar@example.com'),
                        self.parse_command('RCPT TO:foo@example.com, bar@example.com'))

    def test_parse_auth_plain(self):
        self.assert_equals(('AUTH PLAIN', 'AGZvbwBiYXI='),
                         self.parse_command('AUTH PLAIN AGZvbwBiYXI='))

    def send(self, value):
        if isinstance(value, basestring):
            self.parser.process_new_data(value)
        else:
            for item in value:
                self.parser.process_new_data(item)

    def _send_helo_mail_from_and_rcpt_to(self):
        self.send('HELO foo\r\n')
        self.send('MAIL FROM: foo@example.com\r\n')
        self.send('RCPT TO: bar@example.com\r\n')

    def test_can_switch_to_data_mode(self):
        self._send_helo_mail_from_and_rcpt_to()
        self.send('DATA\r\n')
        self.assert_true(self.parser.is_in_data_mode())

    def test_switch_to_command_mode_when_mail_is_sent(self):
        self._send_helo_mail_from_and_rcpt_to()
        self.send('DATA\r\n')
        self.assert_true(self.parser.is_in_data_mode())
        self.send(['Subject: Foo\r\n\r\n', 'test', '\r\n.\r\n'])
        self.assert_true(self.parser.is_in_command_mode())
        self.assert_equals(1, self.deliverer.received_messages.qsize())

    def received_message(self):
        messages = self.deliverer.received_messages
        self.assert_equals(1, messages.qsize())
        return messages.get()

    def assert_no_messages_received(self):
        self.assert_equals(0, self.deliverer.received_messages.qsize())

    def replies(self):
        return self.parser._channel.replies

    def last_reply(self):
        return self.replies()[-1]

    def test_recognizes_end_of_data_mode_even_if_terminator_is_sent_in_multiple_packages(self):
        self._send_helo_mail_from_and_rcpt_to()
        self.send(['DATA\r\n', '\r\n', '.', '\r\n'])
        self.assert_equals('', self.received_message().msg_data)
        self.assert_true(self.parser.is_in_command_mode())

    def test_recognizes_complete_command_mode_even_if_terminator_is_sent_in_multiple_packages(self):
        self.send(['HELO foo', '\r', '\n'])
        self.assert_equals(2, len(self.replies()))

    def test_supports_transparency_for_lines_starting_with_a_dot(self):
        """SMTP transparency support - see RFC 821, section 4.5.2"""
        self._send_helo_mail_from_and_rcpt_to()
        self.send(['DATA\r\n', '..foo\r\n', '..bar..baz\r\n', '\r\n.\r\n'])
        self.assert_equals('.foo\n.bar..baz\n', self.received_message().msg_data)
        self.assert_true(self.parser.is_in_command_mode())

    def test_big_messages_are_rejected(self):
        """Check that messages which exceed the configured maximum message size
        are rejected. This tests all the code setting the maximum allowed input
        size in the transport layer."""
        class RestrictedSizePolicy(IMTAPolicy):
            def max_message_size(self, peer):
                return 100
        self.init_command_parser(RestrictedSizePolicy())

        self._send_helo_mail_from_and_rcpt_to()
        self.send(['DATA\r\n'])
        self.send(('x'*70 + '\n',) * 1500)
        self.send('\r\n.\r\n')
        self.assert_no_messages_received()
        self.assert_true(self.last_reply().startswith('552 '))
