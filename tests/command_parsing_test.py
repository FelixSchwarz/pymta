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

from pymta.command_parser import ParserImplementation
from pymta.lib import PythonicTestCase
from pymta.session import SMTPSession


class CommandParsingTest(PythonicTestCase):

    def setUp(self):
        self.super()
        session = SMTPSession(command_parser=None, deliverer=None)
        allowed_commands = session.get_all_allowed_internal_commands()
        self.parser = ParserImplementation(allowed_commands)
    
    def test_parse_command_without_arguments(self):
        self.assert_equals(('QUIT', None), self.parser.parse('QUIT'))
        self.assert_equals(('RSET', None), self.parser.parse('RSET'))
    
    def test_parse_helo(self):
        self.assert_equals(('HELO', 'foo.example.com'), 
                         self.parser.parse('HELO foo.example.com'))
        # This command is syntactically invalid but the validity of specific
        # commands should not be checked in the parser.
        self.assert_equals(('helo', 'foo example.com'), 
                         self.parser.parse('helo foo example.com'))
    
    def test_strip_parameters(self):
        self.assert_equals(('HELO', 'foo.example.com'), 
                         self.parser.parse('HELO   foo.example.com   '))
    
    def test_parse_commands_with_colons(self):
        self.assert_equals(('MAIL FROM', 'foo@example.com'), 
                        self.parser.parse('MAIL FROM: foo@example.com'))
        self.assert_equals(('MAIL FROM', 'foo@example.com'), 
                        self.parser.parse('MAIL FROM:foo@example.com'))
        self.assert_equals(('MAIL FROM', 'foo@example.com'), 
                        self.parser.parse('MAIL FROM:  foo@example.com   '))
        self.assert_equals(('RCPT TO', 'foo@example.com, bar@example.com'), 
                        self.parser.parse('RCPT TO:foo@example.com, bar@example.com'))
    
    def test_parse_auth_plain(self):
        self.assert_equals(('AUTH PLAIN', 'AGZvbwBiYXI='), 
                         self.parser.parse('AUTH PLAIN AGZvbwBiYXI='))


