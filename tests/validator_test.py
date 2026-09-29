# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

import pytest
from pymta.validation import InvalidDataError, RcptToSchema


def _process(input_string):
    return RcptToSchema().process(input_string)['email']

def test_accept_plain_email_address():
    assert _process('foo@example.com') == 'foo@example.com'

def test_accept_email_address_in_angle_brackets():
    assert _process('<foo@example.com>') == 'foo@example.com'

@pytest.mark.parametrize('address', [
    'foo.bar@example.com',
    'foo+tag@example.com',
    "o'brien@example.com",
    'SRS0=HHH=TT=example.org=user@example.com',
    'prvs=1234abcd=user@example.com',
    "!#$%&'*+-/=?^_`{|}~@example.com",
    '"john doe"@example.com',
    '"john\\"doe"@example.com',
    '"john>doe"@example.com',
    'foo@localhost',
    'foo@sub-domain.example.com',
    'foo@[127.0.0.1]',
    'foo@[IPv6:::1]',
])
def test_accept_valid_email_addresses(address):
    assert _process('<%s>' % address) == address

def test_reject_email_address_in_unbalanced_angle_brackets():
    with pytest.raises(InvalidDataError):
        _process('<foo@example.com')
    with pytest.raises(InvalidDataError):
        _process('foo@example.com>')
    with pytest.raises(InvalidDataError):
        _process('<<foo@example.com>>')

def test_reject_email_address_with_unbalanced_quotes():
    with pytest.raises(InvalidDataError):
        _process('<"foo@example.com>')

@pytest.mark.parametrize('address', [
    'foo@@example.com',
    'foo@example..com',
    'foo',
    '@example.com',
    'foo@',
    '.foo@example.com',
    'foo.@example.com',
    'foo..bar@example.com',
    'foo@.example.com',
    'foo@example.com.',
    'foo@-example.com',
    'foo@example-.com',
    'foo bar@example.com',
    'foo@exa mple.com',
    'foo@exa_mple.com',
    'foo@[127.0.0.1',
    'f\xfc\xfc@example.com',
    'foo@b\xe4r.example',
])
def test_reject_invalid_email_addresses(address):
    with pytest.raises(InvalidDataError) as exc_info:
        _process('<%s>' % address)
    assert exc_info.value.msg() == 'Invalid email address "%s".' % address
