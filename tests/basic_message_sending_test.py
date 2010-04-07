# -*- coding: UTF-8 -*-
#
# The MIT License
# 
# Copyright (c) 2008-2009 Felix Schwarz <felix.schwarz@oss.schwarz.eu>
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

from pymta.api import IMTAPolicy
from pymta.compat import set

from tests.util import CommandParserTestCase, DummyAuthenticator


class BasicMessageSendingTest(CommandParserTestCase):
    
    def _check_last_code(self, expected_code):
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals(expected_code, code)
    
    def test_new_connection(self):
        self.assert_equals(1, len(self.command_parser.replies))
        self._check_last_code(220)
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals('localhost Hello 127.0.0.1', reply_text)
        self.close_connection()
    
    def test_noop_does_nothing(self):
        self.send('noop')
        self.close_connection()
    
    def test_send_helo(self):
        self.send('helo', 'foo.example.com')
        self.assert_equals(2, len(self.command_parser.replies))
        self._check_last_code(250)
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals('localhost', reply_text)
        self.close_connection()

    def test_reject_duplicated_helo(self):
        self.send('helo', 'foo.example.com')
        code, reply_text = self.send('helo', 'foo.example.com', 
                                      expected_first_digit=5)
        self.assert_equals(503, code)
        expected_message = 'Command "helo" is not allowed here'
        self.assert_true(reply_text.startswith(expected_message), reply_text)
        self.close_connection()
    
    def test_helo_without_hostname_is_rejected(self):
        self.send('helo', expected_first_digit=5)
        # But we must be able to send the right command here (state machine must
        # not change)
        self.send('helo', 'foo')
    
    def test_helo_with_invalid_arguments_is_rejected(self):
        expect_invalid = lambda data: self.assert_equals(501, self.send('helo', data, expected_first_digit=5)[0])
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
        self.assert_equals(2, len(self.command_parser.replies))
        self._check_last_code(500)
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals('unrecognized command "invalid"', reply_text)
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
        self.assert_equals(1, received_messages.qsize())
        msg = received_messages.get()
        self.assert_equals('127.0.0.1', msg.peer.remote_ip)
        self.assert_equals(4567, msg.peer.remote_port)
        
        self.assert_equals('foo.example.com', msg.smtp_helo)
        self.assert_equals('foo@example.com', msg.smtp_from)
        self.assert_equals(['bar@example.com'], msg.smtp_to)
        self.assert_equals(rfc822_msg, msg.msg_data)
    
    def test_help_is_supported(self):
        code, reply_text = self.send('HELP')
        self.assert_equals(214, code)
        supported_commands = set(reply_text[1].split(' '))
        expected_commands = set(['AUTH', 'DATA', 'EHLO', 'HELO', 'HELP', 'MAIL',
                                 'NOOP', 'QUIT', 'RCPT', 'RSET'])
        self.assert_equals(expected_commands, supported_commands)
    
    def test_support_for_rset(self):
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', 'foo@example.com')
        self.send('RSET')
        self.send('MAIL FROM', 'bar@example.com')
    
    def test_send_ehlo_without_authenticator(self):
        self.send('EHLO', 'foo.example.com')
        self.assert_equals(2, len(self.command_parser.replies))
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals(250, code)
        self.assert_equals(set(('localhost', 'HELP')), set(reply_text))
    
    def test_ehlo_without_hostname_is_rejected(self):
        self.send('EHLO', expected_first_digit=5)
    
    def test_ehlo_with_invalid_arguments_is_rejected(self):
        expect_invalid = lambda data: self.assert_equals(501, self.send('ehlo', data, expected_first_digit=5)[0])
        expect_invalid('')
        expect_invalid('  ')
        expect_invalid(None)
        expect_invalid('foo bar')
    
    def test_auth_plain_without_authenticator_is_rejected(self):
        self.send('EHLO', 'foo.example.com')
        base64_credentials = u'\x00foo\x00foo'.encode('base64')
        self.send('AUTH PLAIN', base64_credentials, expected_first_digit=5)
        self.assert_equals(3, len(self.command_parser.replies))
        self._check_last_code(535)
    
    def test_authenticator_advertises_auth_plain_support(self):
        self.session._authenticator = DummyAuthenticator()
        
        self.send('EHLO', 'foo.example.com')
        code, reply_texts = self.command_parser.replies[-1]
        self.assert_true('AUTH PLAIN' in reply_texts)
    
    def test_auth_plain_with_username_and_password_is_accepted(self):
        self.session._authenticator = DummyAuthenticator()
        
        self.send('EHLO', 'foo.example.com')
        self.send('AUTH PLAIN', u'\x00foo\x00foo'.encode('base64'))
        self.assert_equals(3, len(self.command_parser.replies))
        self._check_last_code(235)
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals('Authentication successful', reply_text)
    
    def test_auth_plain_with_authzid_username_and_password_is_accepted(self):
        self.session._authenticator = DummyAuthenticator()
        
        self.send('EHLO', 'foo.example.com')
        # RFC 4616 defines SASL PLAIN in the form
        # [authzid] \x00 authcid \x00 passwd
        # smtplib in Python 2.3 will send an additional authzid (which is equal 
        # to authcid)
        self.send('AUTH PLAIN', u'ignored\x00foo\x00foo'.encode('base64'))
        self.assert_equals(3, len(self.command_parser.replies))
        self._check_last_code(235)
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals('Authentication successful', reply_text)
    
    def test_auth_plain_with_bad_credentials_is_accepted(self):
        self.session._authenticator = DummyAuthenticator()
        
        self.send('EHLO', 'foo.example.com')
        base64_credentials = u'\x00foo\x00bar'.encode('base64')
        self.send('AUTH PLAIN', base64_credentials, expected_first_digit=5)
        self._check_last_code(535)
    
    def test_auth_plain_with_bad_base64_is_rejected(self):
        self.session._authenticator = DummyAuthenticator()
        
        self.send('EHLO', 'foo.example.com')
        self.send('AUTH PLAIN', 'foo', expected_first_digit=5)
        self.assert_equals(3, len(self.command_parser.replies))
        self._check_last_code(501)
    
    def test_auth_plain_with_bad_format_is_rejected(self):
        self.session._authenticator = DummyAuthenticator()
        
        self.send('EHLO', 'foo.example.com')
        base64_credentials = u'\x00foo'.encode('base64')
        self.send('AUTH PLAIN', base64_credentials, expected_first_digit=5)
        self.assert_equals(3, len(self.command_parser.replies))
        self._check_last_code(501)
    
    def test_size_restrictions_are_announced_in_ehlo_reply(self):
        class RestrictedSizePolicy(IMTAPolicy):
            def max_message_size(self, peer):
                return 100
        self.session._policy = RestrictedSizePolicy()
        
        self.send('EHLO', 'foo.example.com')
        code, reply_texts = self.command_parser.replies[-1]
        self.assert_true('SIZE 100' in reply_texts)
    
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
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals(501, code)
        self.assert_equals('No SMTP extensions allowed for plain SMTP.', reply_text)
    
    def test_can_still_use_esmtp_after_first_mail(self):
        self.send('EHLO', 'foo.example.com')
        self._send_mail('Subject: First Message\n\nJust testing...\n')
        self.send('MAIL FROM', '<foo@example.com>   size=106530  ')

