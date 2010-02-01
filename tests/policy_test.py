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

from pymta.api import IMTAPolicy, PolicyDecision

from tests.util import CommandParserTestCase, DummyAuthenticator


class BasicPolicyTest(CommandParserTestCase):
    "Tests that all commands can be controlled with policies."
    
    def test_connection_can_be_rejected(self):
        class FalsePolicy(IMTAPolicy):
            def accept_new_connection(self, peer):
                return False
        self.init(policy=FalsePolicy())
        self.assert_false(self.command_parser.open)
        self.assert_equals(1, len(self.command_parser.replies))
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals(554, code)
        self.assert_equals('SMTP service not available', reply_text)
    
    
    def test_helo_can_be_rejected(self):
        class FalsePolicy(IMTAPolicy):
            def accept_helo(self, helo_string, message):
                return (not helo_string.endswith('example.com'))
        self.init(policy=FalsePolicy())
        self.send('HELO', 'foo.example.com', expected_first_digit=5)
        self.send('HELO', 'bar.example.com', expected_first_digit=5)
        self.send('HELO', 'localhost')
    
    
    def test_ehlo_can_be_rejected(self):
        class FalsePolicy(IMTAPolicy):
            def accept_ehlo(self, ehlo_string, message):
                return (not ehlo_string.endswith('example.com'))
        self.init(policy=FalsePolicy())
        self.send('EHLO', 'foo.example.com', expected_first_digit=5)
        self.send('EHLO', 'localhost')
    
    
    def test_auth_plain_can_be_rejected(self):
        class FalsePolicy(IMTAPolicy):
            def accept_auth_plain(self, username, password, message):
                return False
        self.init(policy=FalsePolicy(), authenticator=DummyAuthenticator())
        self.send('EHLO', 'foo.example.com')
        base64_credentials = u'\x00foo\x00foo'.encode('base64')
        self.send('AUTH PLAIN', base64_credentials, expected_first_digit=5)
    
    
    def test_from_can_be_rejected(self):
        class FalsePolicy(IMTAPolicy):
            def accept_from(self, sender, message):
                return False
        self.init(policy=FalsePolicy())
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', 'foo@example.com', expected_first_digit=5)
    
    
    def test_rcptto_can_be_rejected(self):
        class FalsePolicy(IMTAPolicy):
            def accept_rcpt_to(self, new_recipient, message):
                return False
        self.init(policy=FalsePolicy())
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', 'foo@example.com')
        self.send('RCPT TO', 'to@example.com', expected_first_digit=5)
    
    
    def test_data_can_be_rejected(self):
        class FalsePolicy(IMTAPolicy):
            def accept_data(self, message):
                return False
        self.init(policy=FalsePolicy())
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', 'foo@example.com')
        self.send('RCPT TO', 'to@example.com')
        self.send('DATA', expected_first_digit=5)
    
    
    def test_messages_can_be_rejected(self):
        class FalsePolicy(IMTAPolicy):
            def accept_msgdata(self, msg_data, message):
                return False
        self.init(policy=FalsePolicy())
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', 'foo@example.com')
        self.send('RCPT TO', 'to@example.com')
        self.send('DATA', expected_first_digit=3)
        rfc822_msg = 'Subject: Test\n\nJust testing...\n'
        self.send('MSGDATA', rfc822_msg, expected_first_digit=5)
    
    
    def test_size_limit_messages_can_be_rejected(self):
        class MaxSizePolicy(IMTAPolicy):
            def max_message_size(self, peer):
                return 100
        self.init(policy=MaxSizePolicy())
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', 'foo@example.com')
        self.send('RCPT TO', 'to@example.com')
        self.send('DATA', expected_first_digit=3)
        big_data_chunk = ('x'*70 + '\n') * 1500
        rfc822_msg = 'Subject: Test\n\nJust testing...\n' + big_data_chunk
        (code, reply_text) = self.send('MSGDATA', rfc822_msg, 
                                       expected_first_digit=5)
        self.assert_equals(552, code)
        self.assert_equals('message exceeds fixed maximum message size', reply_text)
    
    def test_server_deals_gracefully_with_double_close_because_of_faulty_policy(self):
        class DoubleCloseConnectionPolicy(IMTAPolicy):
            def accept_helo(self, helo_string, message):
                decision = PolicyDecision(True)
                decision._close_connection_before_response = True
                decision._close_connection_after_response = True
                return decision
        self.init(policy=DoubleCloseConnectionPolicy())
        
        number_replies_before = len(self.command_parser.replies)
        self.session.handle_input('HELO', 'foo.example.com')
        self.assert_equals(number_replies_before, len(self.command_parser.replies))
        self.assert_false(self.command_parser.open)

