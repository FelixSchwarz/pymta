# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

import pytest

from pymta.api import IMTAPolicy
from pymta.compat import b64encode
from pymta.test_util import CommandParserTestCase, DummyAuthenticator



class BasicMessageSendingTest(CommandParserTestCase):

    def _check_last_code(self, expected_code):
        code, reply_text = self.last_reply()
        assert code == expected_code
        return reply_text

    def test_new_connection(self):
        assert len(self.command_parser.replies) == 1
        self._check_last_code(220)
        code, reply_text = self.last_reply()
        assert reply_text == 'localhost Hello 127.0.0.1'
        self.close_connection()

    def test_noop_does_nothing(self):
        self.send('noop')
        self.close_connection()

    def test_send_helo(self):
        self.send('helo', 'foo.example.com')
        assert len(self.command_parser.replies) == 2
        self._check_last_code(250)
        code, reply_text = self.last_reply()
        assert reply_text == 'localhost'
        self.close_connection()

    def test_reject_duplicated_helo(self):
        self.send('helo', 'foo.example.com')
        code, reply_text = self.send('helo', 'foo.example.com',
                                      expected_first_digit=5)
        assert code == 503
        expected_message = 'Command "helo" is not allowed here'
        assert reply_text.startswith(expected_message), reply_text
        self.close_connection()

    def test_helo_without_hostname_is_rejected(self):
        self.send('helo', expected_first_digit=5)
        # But we must be able to send the right command here (state machine must
        # not change)
        self.send('helo', 'foo')

    @pytest.mark.parametrize('data', [
        '', '  ', None,
        # Even if we don't enforce that the helo parameter must be a valid host
        # name (as required as per RFC 2821), at least there should be only
        # one parameter.
        'foo bar',
    ])
    @pytest.mark.xfail
    def test_helo_with_invalid_arguments_is_rejected(self, data):
        assert self.send('helo', data, expected_first_digit=5)[0] == 501

    def test_helo_can_send_ipv4_address_in_brackets(self):
        # smtplib in Python 2.6.2 does this at least...
        self.send('helo', '[127.0.0.1]')

    def test_invalid_commands_are_recognized(self):
        self.session.handle_input('invalid')
        assert len(self.command_parser.replies) == 2
        self._check_last_code(500)
        code, reply_text = self.last_reply()
        assert reply_text == 'unrecognized command "invalid"'
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
        assert received_messages.qsize() == 1
        msg = received_messages.get()
        assert msg.peer.remote_ip == '127.0.0.1'
        assert msg.peer.remote_port == 4567

        assert msg.smtp_helo == 'foo.example.com'
        assert msg.smtp_from == 'foo@example.com'
        assert msg.smtp_to == ['bar@example.com']
        assert msg.msg_data == rfc822_msg

    def test_help_is_supported(self):
        code, reply_text = self.send('HELP')
        assert code == 214
        supported_commands = set(reply_text[1].split(' '))
        expected_commands = set(['AUTH', 'DATA', 'EHLO', 'HELO', 'HELP', 'MAIL',
                                 'NOOP', 'QUIT', 'RCPT', 'RSET'])
        assert supported_commands == expected_commands

    def test_support_for_rset(self):
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', 'foo@example.com')
        self.send('RSET')
        self.send('MAIL FROM', 'bar@example.com')

    def test_send_ehlo_without_authenticator(self):
        self.send('EHLO', 'foo.example.com')
        assert len(self.command_parser.replies) == 2
        code, reply_text = self.last_reply()
        assert code == 250
        assert set(reply_text) == set(('localhost', 'HELP'))

    def test_ehlo_without_hostname_is_rejected(self):
        self.send('EHLO', expected_first_digit=5)


    @pytest.mark.parametrize('data', ['', '  ', None, 'foo bar'])
    @pytest.mark.xfail
    def test_ehlo_with_invalid_arguments_is_rejected(self, data):
        assert self.send('ehlo', data, expected_first_digit=5)[0] == 501

    def test_auth_plain_without_authenticator_is_rejected(self):
        self.send('EHLO', 'foo.example.com')
        base64_credentials = b64encode('\x00foo\x00foo')
        self.send('AUTH PLAIN', base64_credentials, expected_first_digit=5)
        assert len(self.command_parser.replies) == 3
        self._check_last_code(535)

    def test_authenticator_advertises_auth_plain_support(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        code, reply_texts = self.last_reply()
        assert 'AUTH PLAIN' in reply_texts

    def test_auth_plain_with_username_and_password_is_accepted(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        self.send('AUTH PLAIN', b64encode('\x00foo\x00foo'))
        assert len(self.command_parser.replies) == 3
        self._check_last_code(235)
        code, reply_text = self.last_reply()
        assert reply_text == 'Authentication successful'

    def test_auth_plain_with_authzid_username_and_password_is_accepted(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        # RFC 4616 defines SASL PLAIN in the form
        # [authzid] \x00 authcid \x00 passwd
        # smtplib in Python 2.3 will send an additional authzid (which is equal
        # to authcid)
        self.send('AUTH PLAIN', b64encode('ignored\x00foo\x00foo'))
        assert len(self.command_parser.replies) == 3
        self._check_last_code(235)
        code, reply_text = self.last_reply()
        assert reply_text == 'Authentication successful'

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
        assert len(self.command_parser.replies) == 3
        self._check_last_code(501)

    def test_auth_plain_with_bad_format_is_rejected(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        base64_credentials = b64encode('\x00foo')
        self.send('AUTH PLAIN', base64_credentials, expected_first_digit=5)
        assert len(self.command_parser.replies) == 3
        self._check_last_code(501)

    def test_auth_login_with_username_and_password_is_accepted(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        self.send_auth_login(username='foo', password='foo')
        assert self.last_reply() == (235, 'Authentication successful')

    def test_auth_login_3step(self):
        self.session._authenticator = DummyAuthenticator()

        self.send('EHLO', 'foo.example.com')
        self.send_auth_login(username='foo', password='foo', reduce_roundtrips=False)
        assert self.last_reply() == (235, 'Authentication successful')

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
        assert code == 501, 'need to retart AUTH LOGIN, not just send password again'
        self.send_auth_login(username='foo', password='foo')
        assert self.last_reply() == (235, 'Authentication successful')

    def test_size_restrictions_are_announced_in_ehlo_reply(self):
        class RestrictedSizePolicy(IMTAPolicy):
            def max_message_size(self, peer):
                return 100
        self.session._policy = RestrictedSizePolicy()

        self.send('EHLO', 'foo.example.com')
        code, reply_texts = self.last_reply()
        assert 'SIZE 100' in reply_texts

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
        assert code == 501
        assert reply_text == 'No SMTP extensions allowed for plain SMTP.'

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

