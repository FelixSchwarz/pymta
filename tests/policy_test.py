# -*- coding: UTF-8 -*-
#
# The MIT License
# 
# Copyright (c) 2008 Felix Schwarz <felix.schwarz@oss.schwarz.eu>
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

from unittest import TestCase

from pymta import DefaultMTAPolicy

from tests.util import CommandParserTestCase


class BasicPolicyTest(CommandParserTestCase):
    "Tests that all commands can be controlled with policies."

    def setUp(self):
        super(BasicPolicyTest, self).setUp()
    
    def test_connection_can_be_rejected(self):
        class FalsePolicy(DefaultMTAPolicy):
            def accept_new_connection(self, peer):
                return False
        self.init(policy=FalsePolicy())
        self.assertEqual(False, self.command_parser.open)
        self.assertEqual(1, len(self.command_parser.replies))
        code, reply_text = self.command_parser.replies[-1]
        self.assertEqual(554, code)
        self.assertEqual('SMTP service not available', reply_text)
    
    
    def test_helo_can_be_rejected(self):
        class FalsePolicy(DefaultMTAPolicy):
            def accept_helo(self, message):
                return (not message.smtp_helo.endswith('example.com'))
        self.init(policy=FalsePolicy())
        self.send('HELO', 'foo.example.com', expected_first_digit=5)
        self.send('HELO', 'bar.example.com', expected_first_digit=5)
        self.send('HELO', 'localhost')
    
    
    def test_from_can_be_rejected(self):
        class FalsePolicy(DefaultMTAPolicy):
            def accept_from(self, message):
                return False
        self.init(policy=FalsePolicy())
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', 'foo@example.com', expected_first_digit=5)
    
    
    def test_rcptto_can_be_rejected(self):
        class FalsePolicy(DefaultMTAPolicy):
            def accept_rcpt_to(self, new_recipient, message):
                return False
        self.init(policy=FalsePolicy())
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', 'foo@example.com')
        self.send('RCPT TO', 'to@example.com', expected_first_digit=5)
    
    
    def test_data_can_be_rejected(self):
        class FalsePolicy(DefaultMTAPolicy):
            def accept_data(self, message):
                return False
        self.init(policy=FalsePolicy())
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', 'foo@example.com')
        self.send('RCPT TO', 'to@example.com')
        self.send('DATA', expected_first_digit=5)
    
    
    def test_messages_can_be_rejected(self):
        class FalsePolicy(DefaultMTAPolicy):
            def accept_msgdata(self, message):
                return False
        self.init(policy=FalsePolicy())
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', 'foo@example.com')
        self.send('RCPT TO', 'to@example.com')
        self.send('DATA', expected_first_digit=3)
        rfc822_msg = 'Subject: Test\n\nJust testing...\n'
        self.send('MSGDATA', rfc822_msg, expected_first_digit=5)


