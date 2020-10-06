# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

from pythonic_testcase import *

from pymta.api import IMTAPolicy
from pymta.compat import b64encode
from pymta.test_util import CommandParserTestCase, DummyAuthenticator



class BasicMessageSendingTest(CommandParserTestCase):

    def _check_last_code(self, expected_code):
        code, reply_text = self.last_reply()
        assert_equals(expected_code, code)
        return reply_text

    def test_new_connection(self):
        assert_length(1, self.command_parser.replies)
        self._check_last_code(220)
        code, reply_text = self.last_reply()
        assert_equals('localhost Hello 127.0.0.1', reply_text)
        self.close_connection()

    def test_noop_does_nothing(self):
        self.send('noop')
        self.close_connection()

    def test_send_helo(self):
        self.send('helo', 'foo.example.com')
        assert_length(2, self.command_parser.replies)
        self._check_last_code(250)
        code, reply_text = self.last_reply()
        assert_equals('localhost', reply_text)
        self.close_connection()

    def test_reject_duplicated_helo(self):
        self.send('helo', 'foo.example.com')
        code, reply_text = self.send('helo', 'foo.example.com',
                                      expected_first_digit=5)
        assert_equals(503, code)
        expected_message = 'Command "helo" is not allowed here'
        assert_true(reply_text.startswith(expected_message), message=reply_text)
        self.close_connection()

    def test_helo_without_hostname_is_rejected(self):
        self.send('helo', expected_first_digit=5)
        # But we must be able to send the right command here (state machine must
        # not change)
        self.send('helo', 'foo')

    def test_helo_with_invalid_arguments_is_rejected(self):
        expect_invalid = lambda data: assert_equals(501, self.send('helo', data, expected_first_digit=5)[0])
        expect_invalid('')
        expect_invalid('  ')
        expect_invalid(None)
        # Even if we don't enforce that the helo parameter must be a valid host
        # name (as required as per RFC 2821), at least there should be only
        # one parameter.
        expect_invalid('foo bar')

    def test_helo_can_send_ipv4_address_in_brackets(self):
        # smtplib in Python 2.6.2 does this at least...
        self.send('helo', '[127.0.0.1]')

    def test_invalid_commands_are_recognized(self):
        self.session.handle_input('invalid')
        assert_length(2, self.command_parser.replies)
        self._check_last_code(500)
        code, reply_text = self.last_reply()
        assert_equals('unrecognized command "invalid"', reply_text)
        self.close_connection()

    def _send_mail(self, rfc822_msg):
        self.send('MAIL FROM', 'foo@example.com')
        self.send('RCPT TO', 'bar@example.com')
        self.send('DATA', expected_first_digit=3)
        self.send('MSGDATA', rfc822_msg)

    def test_send_simple_mail(self):
        rfc822_msg = 'Subject: Test\n\nJust testing...\n'
        self.send('HELO', 'foo.example.com')
        self._send_mail(rfc822_msg)
        self.close_connection()

        received_messages = self.deliverer.received_messages
        assert_equals(1, received_messages.qsize())
        msg = received_messages.get()
        assert_equals('127.0.0.1', msg.peer.remote_ip)
        assert_equals(4567, msg.peer.remote_port)

        assert_equals('foo.example.com', msg.smtp_helo)
        assert_equals('foo@example.com', msg.smtp_from)
        assert_equals(['bar@example.com'], msg.smtp_to)
        assert_equals(rfc822_msg, msg.msg_data)

    def test_help_is_supported(self):
        code, reply_text = self.send('HELP')
        assert_equals(214, code)
        supported_commands = set(reply_text[1].split(' '))
        expected_commands = set(['AUTH', 'DATA', 'EHLO', 'HELO', 'HELP', 'MAIL',
                                 'NOOP', 'QUIT', 'RCPT', 'RSET'])
        assert_equals(expected_commands, supported_commands)

    def test_support_for_rset(self):
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', 'foo@example.com')
        self.send('RSET')
        self.send('MAIL FROM', 'bar@example.com')

    def test_send_ehlo_without_authenticator(self):
        self.send('EHLO', 'foo.example.com')
        assert_length(2, self.command_parser.replies)
        code, reply_text = self.last_reply()
        assert_equals(250, code)
        assert_equals(set(('localhost', 'HELP')), set(reply_text))

    def test_ehlo_without_hostname_is_rejected(self):
        self.send('EHLO', expected_first_digit=5)

    def test_ehlo_with_invalid_arguments_is_rejected(self):
        expect_invalid = lambda data: assert_equals(501, self.send('ehlo', data, expected_first_digit=5)[0])
        expect_invalid('')
        expect_invalid('  ')
        expect_invalid(None)
        expect_invalid('foo bar')

    def test_auth_plain_without_authenticator_is_rejected(self):
        self.send('EHLO', 'foo.example.com')
        base64_credentials = b64encode('\x00foo\x00foo')
        self.send('AUTH PLAIN', base64_credentials, expected_first_digit=5)
        assert_length(3, self.command_parser.replies)
        self._check_last_code(535)

    def test_authenticator_advertises_auth_plain_support(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        code, reply_texts = self.last_reply()
        assert_contains('AUTH PLAIN', reply_texts)

    def test_auth_plain_with_username_and_password_is_accepted(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        self.send('AUTH PLAIN', b64encode('\x00foo\x00foo'))
        assert_length(3, self.command_parser.replies)
        self._check_last_code(235)
        code, reply_text = self.last_reply()
        assert_equals('Authentication successful', reply_text)

    def test_auth_plain_with_authzid_username_and_password_is_accepted(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        # RFC 4616 defines SASL PLAIN in the form
        # [authzid] \x00 authcid \x00 passwd
        # smtplib in Python 2.3 will send an additional authzid (which is equal
        # to authcid)
        self.send('AUTH PLAIN', b64encode('ignored\x00foo\x00foo'))
        assert_length(3, self.command_parser.replies)
        self._check_last_code(235)
        code, reply_text = self.last_reply()
        assert_equals('Authentication successful', reply_text)

    def test_auth_plain_with_bad_credentials_is_rejected(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        base64_credentials = b64encode('\x00foo\x00bar')
        self.send('AUTH PLAIN', base64_credentials, expected_first_digit=5)
        self._check_last_code(535)

    def test_auth_plain_with_bad_base64_is_rejected(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        self.send('AUTH PLAIN', 'foo', expected_first_digit=5)
        assert_length(3, self.command_parser.replies)
        self._check_last_code(501)

    def test_auth_plain_with_bad_format_is_rejected(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        base64_credentials = b64encode('\x00foo')
        self.send('AUTH PLAIN', base64_credentials, expected_first_digit=5)
        assert_length(3, self.command_parser.replies)
        self._check_last_code(501)

    def test_auth_login_with_username_and_password_is_accepted(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        self.send_auth_login(username='foo', password='foo')
        assert_equals((235, 'Authentication successful'), self.last_reply())

    def test_auth_login_3step(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        self.send_auth_login(username='foo', password='foo', reduce_roundtrips=False)
        assert_equals((235, 'Authentication successful'), self.last_reply())

    def test_auth_login_with_bad_credentials_is_rejected(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        self.send_auth_login(username='foo', password='invalid')
        self._check_last_code(535)

    def test_auth_login_with_bad_base64_username_is_rejected(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        self.send_auth_login(username_b64='foo', password='foo')
        self._check_last_code(501)

    def test_auth_login_with_bad_base64_password_is_rejected(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        self.send_auth_login(username='foo', password_b64='foo')
        self._check_last_code(501)

        # state machine should switch back to normal command mode
        code, reply_text = self._handle_auth_credentials('foo')
        assert_equals(501, code,
            message='need to retart AUTH LOGIN, not just send password again')
        self.send_auth_login(username='foo', password='foo')
        assert_equals((235, 'Authentication successful'), self.last_reply())

    def test_size_restrictions_are_announced_in_ehlo_reply(self):
        class RestrictedSizePolicy(IMTAPolicy):
            def max_message_size(self, peer):
                return 100
        self.session._policy = RestrictedSizePolicy()

        self.send('EHLO', 'foo.example.com')
        code, reply_texts = self.last_reply()
        assert_contains('SIZE 100', reply_texts)

    def test_early_rejection_if_size_verb_indicates_big_message(self):
        class RestrictedSizePolicy(IMTAPolicy):
            def max_message_size(self, peer):
                return 100
        self.session._policy = RestrictedSizePolicy()

        self.send('EHLO', 'foo.example.com')
        self.send('MAIL FROM', '<foo@example.com>   size=106530  ',
                  expected_first_digit=5)
        self._check_last_code(552)

    def test_reject_verbs_for_plain_smtp(self):
        """Test that SMTP extension verbs are rejected when the connection uses
        plain SMTP."""
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', '<foo@example.com>   size=106530  ',
                  expected_first_digit=5)
        code, reply_text = self.last_reply()
        assert_equals(501, code)
        assert_equals('No SMTP extensions allowed for plain SMTP.', reply_text)

    def test_can_still_use_esmtp_after_first_mail(self):
        self.send('EHLO', 'foo.example.com')
        self._send_mail('Subject: First Message\n\nJust testing...\n')
        self.send('MAIL FROM', '<foo@example.com>   size=106530  ')

    def send_auth_login(self, username=None, username_b64=None, password=None, password_b64=None, **kwargs):
        assert (username is not None) ^ (username_b64 is not None)
        if username_b64 is None:
            username_b64 = b64encode(username)
            expect_username_error = False
        else:
            expect_username_error = True
        assert (password is not None) ^ (password_b64 is not None)
        if password_b64 is None:
            password_b64 = b64encode(password)
        return super(BasicMessageSendingTest, self).send_auth_login(
            username_b64 = username_b64,
            password_b64 = password_b64,
            expect_username_error = expect_username_error,
            **kwargs
        )

