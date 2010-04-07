# -*- coding: UTF-8 -*-
#
# The MIT License
# 
# Copyright (c) 2010 Felix Schwarz <felix.schwarz@oss.schwarz.eu>
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

from tests.util import CommandParserTestCase, DummyAuthenticator


class SMTPParameterValidationTest(CommandParserTestCase):
    
    def last_server_message(self):
        last_code, last_message = self.command_parser.replies[-1]
        return last_message
    
    def send_invalid(self, command, data=None):
        return self.super.send(command, data=data, expected_first_digit=5)
    
    def send_valid(self, command, data=None):
        return self.super.send(command, data=data, expected_first_digit=2)
    
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
        self.assert_equals('No SMTP extensions allowed for plain SMTP.', self.last_server_message())
    
    def ehlo(self):
        self.send_valid('ehlo', 'fnord')
    
    def test_mail_from_validates_size_extension(self):
        self.ehlo()
        
        self.send_invalid('mail from', '<foo@example.com> SIZE=fnord')
    
    def test_mail_from_rejects_unknown_extension(self):
        self.send_valid('ehlo', 'fnord')
        
        self.send_invalid('mail from', '<foo@example.com> FNORD=INVALID')
        self.assert_equals("Invalid extension: 'FNORD=INVALID'", self.last_server_message())
    
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
        return unicode(value).encode('base64').strip()
    
    def test_auth_plain_accepts_correct_authentication(self):
        self.inject_authenticator()
        self.ehlo()
        
        self.send_valid('AUTH PLAIN', u'\x00foo\x00foo'.encode('base64'))
    
    def test_auth_plain_requires_exactly_one_parameter(self):
        self.inject_authenticator()
        self.ehlo()
        
        self.send_invalid('AUTH PLAIN')
        base64_credentials = self.base64(u'\x00foo\x00foo')
        self.send_invalid('AUTH PLAIN', base64_credentials + ' ' + base64_credentials)
    
    def test_auth_plain_detects_bad_base64_credentials(self):
        self.inject_authenticator()
        self.ehlo()
        
        self.send_invalid('AUTH PLAIN')
        self.send_invalid('AUTH PLAIN', 'invalid_base64')
    
    def test_auth_plain_reject_bad_credentials(self):
        self.inject_authenticator()
        self.ehlo()
        
        self.send_invalid('AUTH PLAIN', self.base64(u'\x00foo\x00bar'))


