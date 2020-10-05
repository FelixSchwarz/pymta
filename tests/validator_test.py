# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

from pycerberus.errors import InvalidDataError
from pythonic_testcase import *

from pymta.validation import SMTPEmailValidator


class SMTPEmailValidatorTest(PythonicTestCase):

    def process(self, input_string):
        return SMTPEmailValidator().process(input_string)

    def test_accept_plain_email_address(self):
        assert_equals('foo@example.com', self.process('foo@example.com'))

    def test_accept_email_address_in_angle_brackets(self):
        assert_equals('foo@example.com', self.process('<foo@example.com>'))

    def test_reject_email_address_in_unbalanced_angle_brackets(self):
        with assert_raises(InvalidDataError):
            self.process('<foo@example.com')
        with assert_raises(InvalidDataError):
            self.process('foo@example.com>')

    def test_reject_invalid_email_addresses(self):
        with assert_raises(InvalidDataError):
            self.process('foo@@example.com')
        with assert_raises(InvalidDataError):
            self.process('foo@example..com')

