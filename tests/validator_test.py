# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

from pycerberus.errors import InvalidDataError
import pytest

from pymta.validation import SMTPEmailValidator


def _process(input_string):
    return SMTPEmailValidator().process(input_string)

def test_accept_plain_email_address():
    assert _process('foo@example.com') == 'foo@example.com'

def test_accept_email_address_in_angle_brackets():
    assert _process('<foo@example.com>') == 'foo@example.com'

def test_reject_email_address_in_unbalanced_angle_brackets():
    with pytest.raises(InvalidDataError):
        _process('<foo@example.com')
    with pytest.raises(InvalidDataError):
        _process('foo@example.com>')

def test_reject_invalid_email_addresses():
    with pytest.raises(InvalidDataError):
        _process('foo@@example.com')
    with pytest.raises(InvalidDataError):
        _process('foo@example..com')

