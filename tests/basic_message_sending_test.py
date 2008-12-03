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

from sets import Set
from unittest import TestCase

from tests.util import CommandParserTestCase


class BasicMessageSendingTest(CommandParserTestCase):

    def setUp(self):
        super(BasicMessageSendingTest, self).setUp()
    
    def test_new_connection(self):
        self.assertEqual(1, len(self.command_parser.replies))
        code, reply_text = self.command_parser.replies[-1]
        self.assertEqual(220, code)
        self.assertEqual('localhost Hello 127.0.0.1', reply_text)
        self.close_connection()
    
    def test_noop_does_nothing(self):
        self.send('noop')
        self.close_connection()
    
    def test_send_helo(self):
        self.send('helo', 'foo.example.com')
        self.assertEqual(2, len(self.command_parser.replies))
        code, reply_text = self.command_parser.replies[-1]
        self.assertEqual(250, code)
        self.assertEqual('localhost', reply_text)
        self.close_connection()

    def test_reject_duplicated_helo(self):
        self.send('helo', 'foo.example.com')
        code, reply_text = self.send('helo', 'foo.example.com', 
                                      expected_first_digit=5)
        self.assertEqual(503, code)
        expected_message = 'Command "helo" is not allowed here'
        self.assertTrue(reply_text.startswith(expected_message), reply_text)
        self.close_connection()
    
    def test_helo_without_hostname_is_rejected(self):
        self.send('helo', expected_first_digit=5)
        # But we must be able to send the right command here (state machine must
        # not change)
        self.send('helo', 'foo')
    
    def test_helo_with_invalid_arguments_is_rejected(self):
        expect_invalid = lambda data: self.assertEqual(501, self.send('helo', data, expected_first_digit=5)[0])
        expect_invalid('')
        expect_invalid('  ')
        expect_invalid(None)
        expect_invalid('foo bar')
        expect_invalid('foo_bar')
    
    def test_invalid_commands_are_recognized(self):
        self.session.handle_input('invalid')
        self.assertEqual(2, len(self.command_parser.replies))
        code, reply_text = self.command_parser.replies[-1]
        self.assertEqual(500, code)
        self.assertEqual('unrecognized command "invalid"', reply_text)
        self.close_connection()
    
    def test_send_simple_mail(self):
        self.send('HELO', 'foo.example.com')
        self.send('MAIL FROM', 'foo@example.com')
        self.send('RCPT TO', 'bar@example.com')
        rfc822_msg = 'Subject: Test\n\nJust testing...\n'
        self.send('DATA', expected_first_digit=3)
        self.send('MSGDATA', rfc822_msg)
        self.close_connection()
        
        self.assertEqual(1, len(self.command_parser.messages))
        msg = self.command_parser.messages[0]
        self.assertEqual('127.0.0.1', msg.peer.remote_ip)
        self.assertEqual(4567, msg.peer.remote_port)
        
        self.assertEqual('foo.example.com', msg.smtp_helo)
        self.assertEqual('foo@example.com', msg.smtp_from)
        self.assertEqual('bar@example.com', msg.smtp_to)
        self.assertEqual(rfc822_msg, msg.msg_data)
    
    def test_help_is_supported(self):
        code, reply_text = self.send('HELP')
        self.assertEqual(214, code)
        supported_commands = Set(reply_text[1].split(' '))
        expected_commands = Set(['DATA', 'HELO', 'HELP', 'MAIL', 'NOOP', 'QUIT',
                                 'RCPT'])
        self.assertEqual(expected_commands, supported_commands)

