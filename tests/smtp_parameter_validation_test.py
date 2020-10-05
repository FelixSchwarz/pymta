# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

from pythonic_testcase import *

from pymta.compat import b64encode
from pymta.test_util import CommandParserTestCase, DummyAuthenticator



class SMTPParameterValidationTest(CommandParserTestCase):

    def last_server_message(self):
        last_code, last_message = self.command_parser.replies[-1]
        return last_message

    def send_invalid(self, command, data=None):
        return super(SMTPParameterValidationTest, self).send(command, data=data, expected_first_digit=5)

    def send_valid(self, command, data=None):
        return super(SMTPParameterValidationTest, self).send(command, data=data, expected_first_digit=2)

    # -------------------------------------------------------------------------
    # helo/ehlo

    def test_helo_accepts_exactly_one_parameter(self):
        self.send_invalid('helo')
        self.send_invalid('helo', 'foo bar')
        self.send_invalid('helo', '')

    def test_ehlo_accepts_exactly_one_parameter(self):
        self.send_invalid('ehlo')
        self.send_invalid('ehlo', 'foo bar')

    # -------------------------------------------------------------------------
    # commands without parameters

    def helo(self):
        self.send_valid('helo', 'fnord')

    def test_noop_does_not_accept_any_parameters(self):
        self.helo()

        self.send_invalid('noop', 'foo')

    def test_rset_does_not_accept_any_parameters(self):
        self.helo()

        self.send_invalid('rset', 'foo')

    def test_quit_does_not_accept_any_parameters(self):
        self.helo()

        self.send_invalid('quit', 'invalid')

    def test_data_does_not_accept_any_parameters(self):
        self.helo_and_mail_from()
        self.send_valid('rcpt to', 'foo@example.com')

        self.send_invalid('data', 'invalid')

    # -------------------------------------------------------------------------
    # MAIL FROM

    def test_mail_from_requires_an_email_address(self):
        self.helo()

        self.send_invalid('mail from')
        self.send_invalid('mail from', 'foo@@bar')

    def test_mail_from_must_not_have_extensions_for_plain_smtp(self):
        self.helo()

        self.send_invalid('mail from', '<foo@example.com> SIZE=100')
        assert_equals('No SMTP extensions allowed for plain SMTP.', self.last_server_message())

    def ehlo(self):
        self.send_valid('ehlo', 'fnord')

    def test_mail_from_validates_size_extension(self):
        self.ehlo()

        self.send_invalid('mail from', '<foo@example.com> SIZE=fnord')

    def test_mail_from_rejects_unknown_extension(self):
        self.send_valid('ehlo', 'fnord')

        self.send_invalid('mail from', '<foo@example.com> FNORD=INVALID')
        assert_equals('Invalid extension: "FNORD=INVALID"', self.last_server_message())

    def helo_and_mail_from(self):
        self.helo()
        self.send_valid('mail from', 'foo@example.com')

    # -------------------------------------------------------------------------
    # RCPT TO

    def test_rcpt_to_requires_an_email_address(self):
        self.helo_and_mail_from()

        self.send_invalid('rcpt to')
        self.send_invalid('rcpt to foo@@bar.com')
        self.send_invalid('rcpt to foo@bar.com invalid')

    def test_rcpt_to_accepts_a_valid_email_address(self):
        self.helo_and_mail_from()
        self.send_valid('rcpt to', 'foo@example.com')
        self.send_valid('rcpt to', '<foo@example.com>')

    # -------------------------------------------------------------------------
    # AUTH PLAIN

    def inject_authenticator(self):
        self.session._authenticator = DummyAuthenticator()

    def base64(self, value):
        return b64encode(value).strip()

    def test_auth_plain_accepts_correct_authentication(self):
        self.inject_authenticator()
        self.ehlo()

        self.send_valid('AUTH PLAIN', b64encode('\x00foo\x00foo'))

    def test_auth_plain_requires_exactly_one_parameter(self):
        self.inject_authenticator()
        self.ehlo()

        self.send_invalid('AUTH PLAIN')
        base64_credentials = self.base64('\x00foo\x00foo')
        self.send_invalid('AUTH PLAIN', base64_credentials + ' ' + base64_credentials)

    def test_auth_plain_detects_bad_base64_credentials(self):
        self.inject_authenticator()
        self.ehlo()

        self.send_invalid('AUTH PLAIN')
        self.send_invalid('AUTH PLAIN', 'invalid_base64')

    def test_auth_plain_reject_bad_credentials(self):
        self.inject_authenticator()
        self.ehlo()

        self.send_invalid('AUTH PLAIN', self.base64('\x00foo\x00bar'))


