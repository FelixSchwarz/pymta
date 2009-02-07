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

from pymta.api import IMTAPolicy

from tests.util import CommandParserTestCase


class PolicyReturnCodesTest(CommandParserTestCase):
    "Tests the different outputs of a policy class"

    def test_policy_can_return_true(self):
        class TruePolicy(IMTAPolicy):
            def accept_new_connection(self, peer):
                return True
        self.init(policy=TruePolicy())
        self.assertEqual(True, self.command_parser.open)
    
    def test_policy_can_return_false(self):
        class FalsePolicy(IMTAPolicy):
            def accept_new_connection(self, peer):
                return False
        self.init(policy=FalsePolicy())
        self.assertEqual(False, self.command_parser.open)
    
    def test_returning_none_is_treated_as_true(self):
        class NonePolicy(IMTAPolicy):
            def accept_new_connection(self, peer):
                return None
        self.init(policy=NonePolicy())
        self.assertEqual(True, self.command_parser.open)
    
    def test_policy_can_return_custom_codes_as_tuple(self):
        class CustomCodePolicy(IMTAPolicy):
            def accept_new_connection(self, peer):
                return (False, (553, 'Go away'))
        self.init(policy=CustomCodePolicy())
        
        self.assertEqual(False, self.command_parser.open)
        self.assertEqual(1, len(self.command_parser.replies))
        code, reply_text = self.command_parser.replies[-1]
        self.assertEqual(553, code)
        self.assertEqual('Go away', reply_text)
    
    def test_policy_can_return_multiple_codes(self):
        class CustomCodePolicy(IMTAPolicy):
            def accept_new_connection(self, peer):
                return (False, (552, ('Go away', 'Evil IP')))
        self.init(policy=CustomCodePolicy())
        
        self.assertEqual(False, self.command_parser.open)
        self.assertEqual(1, len(self.command_parser.replies))
        code, reply_text = self.command_parser.replies[-1]
        self.assertEqual(552, code)
        self.assertEqual(('Go away', 'Evil IP'), reply_text)
        


