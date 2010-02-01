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

from pymta.api import IMTAPolicy, PolicyDecision

from tests.util import CommandParserTestCase


class PolicyReturnCodesTest(CommandParserTestCase):
    "Tests the different outputs of a policy class"

    def test_policy_can_return_true(self):
        class TruePolicy(IMTAPolicy):
            def accept_new_connection(self, peer):
                return True
        self.init(policy=TruePolicy())
        self.assert_true(self.command_parser.open)
    
    def test_policy_can_return_false(self):
        class FalsePolicy(IMTAPolicy):
            def accept_new_connection(self, peer):
                return False
        self.init(policy=FalsePolicy())
        self.assert_false(self.command_parser.open)
    
    def test_returning_none_is_treated_as_true(self):
        class NonePolicy(IMTAPolicy):
            def accept_new_connection(self, peer):
                return None
        self.init(policy=NonePolicy())
        self.assert_true(self.command_parser.open)
    
    def test_policy_can_return_custom_codes_as_tuple(self):
        class CustomCodePolicy(IMTAPolicy):
            def accept_new_connection(self, peer):
                return (False, (553, 'Go away'))
        self.init(policy=CustomCodePolicy())
        
        self.assert_false(self.command_parser.open)
        self.assert_equals(1, len(self.command_parser.replies))
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals(553, code)
        self.assert_equals('Go away', reply_text)
    
    def test_policy_can_return_multiple_lines(self):
        class CustomCodePolicy(IMTAPolicy):
            def accept_new_connection(self, peer):
                return (False, (552, ('Go away', 'Evil IP')))
        self.init(policy=CustomCodePolicy())
        
        self.assert_equals(1, len(self.command_parser.replies))
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals(552, code)
        self.assert_equals(('Go away', 'Evil IP'), reply_text)
        self.assert_false(self.command_parser.open)
    
    def test_can_return_policydecision_instance(self):
        class ReturnPolicyDecisionPolicy(IMTAPolicy):
            def accept_helo(self, helo_string, message):
                is_localhost = (helo_string == 'localhost')
                return PolicyDecision(decision=is_localhost)
        self.init(policy=ReturnPolicyDecisionPolicy())
        
        self.send('HELO', 'foo.example.com', expected_first_digit=5)
        self.send('HELO', 'bar.example.net', expected_first_digit=5)
        self.send('HELO', 'localhost')
    
    def test_can_return_custom_code_and_message_in_policydecision_instance(self):
        class ReturnCustomCodePolicy(IMTAPolicy):
            def accept_helo(self, helo_string, message):
                return PolicyDecision(False, (553, 'I am tired'))
        self.init(policy=ReturnCustomCodePolicy())
        
        self.send('HELO', 'foo.example.com', expected_first_digit=5)
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals((553, 'I am tired'), (code, reply_text))
    
    def test_can_close_connection_after_reply(self):
        class CloseConnectionAfterReplyPolicy(IMTAPolicy):
            def accept_helo(self, helo_string, message):
                decision = PolicyDecision(False, (552, 'Stupid Spammer'))
                decision._close_connection_after_response = True
                return decision
        self.init(policy=CloseConnectionAfterReplyPolicy())
        
        self.send('HELO', 'foo.example.com', expected_first_digit=5)
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals((552, 'Stupid Spammer'), (code, reply_text))
        self.assert_false(self.command_parser.open)
    
    def test_can_close_connection_before_reply(self):
        class CloseConnectionAfterReplyPolicy(IMTAPolicy):
            def accept_helo(self, helo_string, message):
                decision = PolicyDecision(False)
                decision._close_connection_before_response = True
                return decision
        self.init(policy=CloseConnectionAfterReplyPolicy())
        
        number_replies_before = len(self.command_parser.replies)
        self.session.handle_input('HELO', 'foo.example.com')
        self.assert_equals(number_replies_before, len(self.command_parser.replies))
        self.assert_false(self.command_parser.open)
    
    def test_can_close_connection_after_using_default_response(self):
        class CloseConnectionAfterReplyPolicy(IMTAPolicy):
            def accept_helo(self, helo_string, message):
                decision = PolicyDecision(False)
                decision._close_connection_after_response = True
                return decision
        self.init(policy=CloseConnectionAfterReplyPolicy())
        
        self.send('HELO', 'foo.example.com', expected_first_digit=5)
        code, reply_text = self.command_parser.replies[-1]
        self.assert_equals((550, 'Administrative Prohibition'), (code, reply_text))
        self.assert_false(self.command_parser.open)
    
    def test_can_close_connection_after_positive_response(self):
        class CloseConnectionAfterPositiveReplyPolicy(IMTAPolicy):
            def accept_helo(self, helo_string, message):
                decision = PolicyDecision(True)
                decision._close_connection_after_response = True
                return decision
        self.init(policy=CloseConnectionAfterPositiveReplyPolicy())
        
        self.send('HELO', 'foo.example.com')
        self.assert_false(self.command_parser.open)


