# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

from pymta.compat import b64encode
from pymta.test_util import CommandParserHelper, DummyAuthenticator


# -------------------------------------------------------------------------
# helo/ehlo

def test_helo_accepts_exactly_one_parameter():
    _cp = CommandParserHelper()
    _cp.send_invalid('helo')
    _cp.send_invalid('helo', 'foo bar')
    _cp.send_invalid('helo', '')

def test_ehlo_accepts_exactly_one_parameter():
    _cp = CommandParserHelper()
    _cp.send_invalid('ehlo')
    _cp.send_invalid('ehlo', 'foo bar')

# -------------------------------------------------------------------------
# commands without parameters

def test_noop_does_not_accept_any_parameters():
    _cp = CommandParserHelper()
    _cp.helo()
    _cp.send_invalid('noop', 'foo')

def test_rset_does_not_accept_any_parameters():
    _cp = CommandParserHelper()
    _cp.helo()
    _cp.send_invalid('rset', 'foo')

def test_quit_does_not_accept_any_parameters():
    _cp = CommandParserHelper()
    _cp.helo()
    _cp.send_invalid('quit', 'invalid')

def test_data_does_not_accept_any_parameters():
    _cp = CommandParserHelper()
    helo_and_mail_from(_cp)
    _cp.send_valid('rcpt to', 'foo@example.com')

    _cp.send_invalid('data', 'invalid')

# -------------------------------------------------------------------------
# MAIL FROM

def test_mail_from_requires_an_email_address():
    _cp = CommandParserHelper()
    _cp.helo()
    _cp.send_invalid('mail from')
    _cp.send_invalid('mail from', 'foo@@bar')

def test_mail_from_must_not_have_extensions_for_plain_smtp():
    _cp = CommandParserHelper()
    _cp.helo()
    _cp.send_invalid('mail from', '<foo@example.com> SIZE=100')
    assert _cp.last_server_message() == 'No SMTP extensions allowed for plain SMTP.'

def test_mail_from_validates_size_extension():
    _cp = CommandParserHelper()
    _cp.ehlo()
    _cp.send_invalid('mail from', '<foo@example.com> SIZE=fnord')

def test_mail_from_rejects_unknown_extension():
    _cp = CommandParserHelper()
    _cp.send_valid('ehlo', 'fnord')

    _cp.send_invalid('mail from', '<foo@example.com> FNORD=INVALID')
    assert _cp.last_server_message() == 'Invalid extension: "FNORD=INVALID"'

def helo_and_mail_from(_cp):
    _cp.helo()
    _cp.send_valid('mail from', 'foo@example.com')

# -------------------------------------------------------------------------
# RCPT TO

def test_rcpt_to_requires_an_email_address():
    _cp = CommandParserHelper()
    helo_and_mail_from(_cp)

    _cp.send_invalid('rcpt to')
    _cp.send_invalid('rcpt to foo@@bar.com')
    _cp.send_invalid('rcpt to foo@bar.com invalid')

def test_rcpt_to_accepts_a_valid_email_address():
    _cp = CommandParserHelper()
    helo_and_mail_from(_cp)
    _cp.send_valid('rcpt to', 'foo@example.com')
    _cp.send_valid('rcpt to', '<foo@example.com>')

# -------------------------------------------------------------------------
# AUTH PLAIN

def _base64(value):
    return b64encode(value).strip()

def test_auth_plain_accepts_correct_authentication():
    _cp = CommandParserHelper(authenticator=DummyAuthenticator())
    _cp.ehlo()
    _cp.send_valid('AUTH PLAIN', b64encode('\x00foo\x00foo'))

def test_auth_plain_requires_exactly_one_parameter():
    _cp = CommandParserHelper(authenticator=DummyAuthenticator())
    _cp.ehlo()

    _cp.send_invalid('AUTH PLAIN')
    base64_credentials = _base64('\x00foo\x00foo')
    _cp.send_invalid('AUTH PLAIN', base64_credentials + ' ' + base64_credentials)

def test_auth_plain_detects_bad_base64_credentials():
    _cp = CommandParserHelper(authenticator=DummyAuthenticator())
    _cp.ehlo()

    _cp.send_invalid('AUTH PLAIN')
    _cp.send_invalid('AUTH PLAIN', 'invalid_base64')

def test_auth_plain_reject_bad_credentials():
    _cp = CommandParserHelper(authenticator=DummyAuthenticator())
    _cp.ehlo()
    _cp.send_invalid('AUTH PLAIN', _base64('\x00foo\x00bar'))
