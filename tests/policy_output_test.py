# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT
"Tests the different outputs of a policy class"

from __future__ import print_function, unicode_literals

from pymta.api import IMTAPolicy, PolicyDecision
from pymta.test_util import CommandParserHelper


def test_policy_can_return_true():
    class TruePolicy(IMTAPolicy):
        def accept_new_connection(self, peer):
            return True
    _cp = CommandParserHelper(policy=TruePolicy())
    assert _cp.command_parser.open

def test_policy_can_return_false():
    class FalsePolicy(IMTAPolicy):
        def accept_new_connection(self, peer):
            return False
    _cp = CommandParserHelper(policy=FalsePolicy())
    assert not _cp.command_parser.open

def test_returning_none_is_treated_as_true():
    class NonePolicy(IMTAPolicy):
        def accept_new_connection(self, peer):
            return None
    _cp = CommandParserHelper(policy=NonePolicy())
    assert _cp.command_parser.open

def test_policy_can_return_custom_codes_as_tuple():
    class CustomCodePolicy(IMTAPolicy):
        def accept_new_connection(self, peer):
            return (False, (553, 'Go away'))

    _cp = CommandParserHelper(policy=CustomCodePolicy())
    assert not _cp.command_parser.open
    assert len(_cp.command_parser.replies) == 1
    code, reply_text = _cp.command_parser.replies[-1]
    assert code == 553
    assert reply_text == 'Go away'

def test_policy_can_return_multiple_lines():
    class CustomCodePolicy(IMTAPolicy):
        def accept_new_connection(self, peer):
            return (False, (552, ('Go away', 'Evil IP')))

    _cp = CommandParserHelper(policy=CustomCodePolicy())
    assert len(_cp.command_parser.replies) == 1
    code, reply_text = _cp.command_parser.replies[-1]
    assert code == 552
    assert reply_text == ('Go away', 'Evil IP')
    assert not _cp.command_parser.open

def test_can_return_policydecision_instance():
    class ReturnPolicyDecisionPolicy(IMTAPolicy):
        def accept_helo(self, helo_string, message):
            is_localhost = (helo_string == 'localhost')
            return PolicyDecision(decision=is_localhost)

    _cp = CommandParserHelper(policy=ReturnPolicyDecisionPolicy())
    _cp.send('HELO', 'foo.example.com', expected_first_digit=5)
    _cp.send('HELO', 'bar.example.net', expected_first_digit=5)
    _cp.send('HELO', 'localhost')

def test_can_return_custom_code_and_message_in_policydecision_instance():
    class ReturnCustomCodePolicy(IMTAPolicy):
        def accept_helo(self, helo_string, message):
            return PolicyDecision(False, (553, 'I am tired'))

    _cp = CommandParserHelper(policy=ReturnCustomCodePolicy())
    _cp.send('HELO', 'foo.example.com', expected_first_digit=5)
    code, reply_text = _cp.command_parser.replies[-1]
    assert (code, reply_text) == (553, 'I am tired')

def test_can_close_connection_after_reply():
    class CloseConnectionAfterReplyPolicy(IMTAPolicy):
        def accept_helo(self, helo_string, message):
            decision = PolicyDecision(False, (552, 'Stupid Spammer'))
            decision._close_connection_after_response = True
            return decision

    _cp = CommandParserHelper(policy=CloseConnectionAfterReplyPolicy())
    _cp.send('HELO', 'foo.example.com', expected_first_digit=5)
    code, reply_text = _cp.command_parser.replies[-1]
    assert (code, reply_text) == (552, 'Stupid Spammer')
    assert not _cp.command_parser.open

def test_can_close_connection_before_reply():
    class CloseConnectionAfterReplyPolicy(IMTAPolicy):
        def accept_helo(self, helo_string, message):
            decision = PolicyDecision(False)
            decision._close_connection_before_response = True
            return decision

    _cp = CommandParserHelper(policy=CloseConnectionAfterReplyPolicy())
    number_replies_before = len(_cp.command_parser.replies)
    _cp.session.handle_input('HELO', 'foo.example.com')
    assert len(_cp.command_parser.replies) == number_replies_before
    assert not _cp.command_parser.open

def test_can_close_connection_after_using_default_response():
    class CloseConnectionAfterReplyPolicy(IMTAPolicy):
        def accept_helo(self, helo_string, message):
            decision = PolicyDecision(False)
            decision._close_connection_after_response = True
            return decision

    _cp = CommandParserHelper(policy=CloseConnectionAfterReplyPolicy())
    _cp.send('HELO', 'foo.example.com', expected_first_digit=5)
    code, reply_text = _cp.command_parser.replies[-1]
    assert (code, reply_text) == (550, 'Administrative Prohibition')
    assert not _cp.command_parser.open

def test_can_close_connection_after_positive_response():
    class CloseConnectionAfterPositiveReplyPolicy(IMTAPolicy):
        def accept_helo(self, helo_string, message):
            decision = PolicyDecision(True)
            decision._close_connection_after_response = True
            return decision

    _cp = CommandParserHelper(policy=CloseConnectionAfterPositiveReplyPolicy())
    _cp.send('HELO', 'foo.example.com')
    assert not _cp.command_parser.open
