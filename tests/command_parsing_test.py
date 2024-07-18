# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

from unittest import TestCase

from pymta.api import IMTAPolicy
from pymta.command_parser import SMTPCommandParser
from pymta.compat import b64encode, basestring
from pymta.test_util import BlackholeDeliverer, DummyAuthenticator, MockChannel


class CommandParsingTest(TestCase):

    def setUp(self):
        self.deliverer = BlackholeDeliverer()
        self.parser = self.init_command_parser()

    def init_command_parser(self, policy=None, authenticator=None):
        return SMTPCommandParser(
            MockChannel(),
            '127.0.0.1', 12345,
            deliverer     = self.deliverer,
            policy        = policy,
            authenticator = authenticator,
        )

    def parse_command(self, input):
        return self.parser._parser.parse(input)

    def test_parse_command_without_arguments(self):
        assert self.parse_command('QUIT') == ('QUIT', None)
        assert self.parse_command('RSET') == ('RSET', None)
        assert self.parse_command('DATA') == ('DATA', None)

    def test_parse_helo(self):
        assert self.parse_command('HELO foo.example.com') == ('HELO', 'foo.example.com')
        # This command is syntactically invalid but the validity of specific
        # commands should not be checked in the parser.
        assert self.parse_command('helo foo example.com') == ('helo', 'foo example.com')

    def test_strip_parameters(self):
        assert self.parse_command('HELO   foo.example.com   ') == ('HELO', 'foo.example.com')

    def test_parse_commands_with_colons(self):
        mail_from_foo = ('MAIL FROM', 'foo@example.com')
        assert self.parse_command('MAIL FROM: foo@example.com') == mail_from_foo
        assert self.parse_command('MAIL FROM:foo@example.com') == mail_from_foo
        assert self.parse_command('MAIL FROM:  foo@example.com   ') == mail_from_foo
        assert self.parse_command('RCPT TO:foo@example.com, bar@example.com') == \
            ('RCPT TO', 'foo@example.com, bar@example.com')

    def test_parse_auth_plain(self):
        assert self.parse_command('AUTH PLAIN AGZvbwBiYXI=') == ('AUTH PLAIN', 'AGZvbwBiYXI=')

    def test_parse_auth_login_with_username(self):
        self.parser = self.init_command_parser(authenticator=DummyAuthenticator())
        self.send('EHLO foo\r\n')
        self.send('AUTH LOGIN %s\r\n' % b64encode('foo'))
        self.send('%s\r\n' % b64encode('secret'))
        self.send('MAIL FROM: foo@example.com\r\n')

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
        assert self.parser.is_in_data_mode()

    def test_switch_to_command_mode_when_mail_is_sent(self):
        self._send_helo_mail_from_and_rcpt_to()
        self.send('DATA\r\n')
        assert self.parser.is_in_data_mode()
        self.send(['Subject: Foo\r\n\r\n', 'test', '\r\n.\r\n'])
        assert self.parser.is_in_command_mode()
        assert self.deliverer.received_messages.qsize() == 1

    def received_message(self):
        messages = self.deliverer.received_messages
        assert messages.qsize() == 1
        return messages.get()

    def assert_no_messages_received(self):
        assert self.deliverer.received_messages.qsize() == 0

    def replies(self):
        return self.parser._channel.replies

    def last_reply(self):
        return self.replies()[-1]

    def test_recognizes_end_of_data_mode_even_if_terminator_is_sent_in_multiple_packages(self):
        self._send_helo_mail_from_and_rcpt_to()
        self.send(['DATA\r\n', '\r\n', '.', '\r\n'])
        assert self.received_message().msg_data == ''
        assert self.parser.is_in_command_mode()

    def test_recognizes_complete_command_mode_even_if_terminator_is_sent_in_multiple_packages(self):
        self.send(['HELO foo', '\r', '\n'])
        assert len(self.replies()) == 2

    def test_supports_transparency_for_lines_starting_with_a_dot(self):
        """SMTP transparency support - see RFC 821, section 4.5.2"""
        self._send_helo_mail_from_and_rcpt_to()
        self.send(['DATA\r\n', '..foo\r\n', '..bar..baz\r\n', '\r\n.\r\n'])
        assert self.received_message().msg_data == '.foo\n.bar..baz\n'
        assert self.parser.is_in_command_mode()

    def test_big_messages_are_rejected(self):
        """Check that messages which exceed the configured maximum message size
        are rejected. This tests all the code setting the maximum allowed input
        size in the transport layer."""
        class RestrictedSizePolicy(IMTAPolicy):
            def max_message_size(self, peer):
                return 100
        self.parser = self.init_command_parser(RestrictedSizePolicy())

        self._send_helo_mail_from_and_rcpt_to()
        self.send(['DATA\r\n'])
        self.send(('x'*70 + '\n',) * 1500)
        self.send('\r\n.\r\n')
        self.assert_no_messages_received()
        assert self.last_reply().startswith('552 ')
