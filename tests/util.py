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

from unittest import TestCase

from pymta import SMTPSession
from pymta.api import IAuthenticator
from pymta.test_util import BlackholeDeliverer


class MockCommandParser(object):
    primary_hostname = 'localhost'
    
    def __init__(self):
        self.replies = []
        self.messages = []
        self.open = True
    
    def set_maximum_message_size(self, max_size):
        pass
    
    def push(self, code, text):
        self.replies.append((code, text))
    
    def multiline_push(self, code, lines):
        self.replies.append((code, lines))
    
    def close_when_done(self):
        assert self.open
        self.open = False
    
    def new_message_received(self, msg):
        self.messages.append(msg)
    
    def switch_to_command_mode(self):
        pass
    
    def switch_to_data_mode(self):
        pass


class DummyAuthenticator(IAuthenticator):
    def authenticate(self, username, password, peer):
        return username == password


class CommandParserTestCase(TestCase):

    def setUp(self, policy=None):
        self.init(policy=policy)
    
    def tearDown(self):
        if self.command_parser.open:
            self.close_connection()
    
    def init(self, policy=None, authenticator=None):
        self.command_parser = MockCommandParser()
        self.deliverer = BlackholeDeliverer()
        self.session = SMTPSession(command_parser=self.command_parser,
                                   deliverer=self.deliverer,
                                   policy=policy, authenticator=authenticator)
        self.session.new_connection('127.0.0.1', 4567)
        
    def check_reply_code(self, code, reply_text, expected_first_digit):
        first_code_digit = int(str(code)[0])
        smtp_reply = "%s %s" % (code, reply_text)
        if expected_first_digit != None:
            self.assertEqual(expected_first_digit, first_code_digit, smtp_reply)
    
    def send(self, command, data=None, expected_first_digit=2):
        number_replies_before = len(self.command_parser.replies)
        self.session.handle_input(command, data)
        self.assertEqual(number_replies_before + 1, len(self.command_parser.replies))
        code, reply_text = self.command_parser.replies[-1]
        self.check_reply_code(code, reply_text, expected_first_digit=expected_first_digit)
        return (code, reply_text)
    
    def close_connection(self):
        self.send('quit')
        code, reply_text = self.command_parser.replies[-1]
        self.assertTrue(221, code)
        self.assertEqual('localhost closing connection', reply_text)
        self.assertEqual(False, self.command_parser.open)


