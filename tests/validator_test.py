# -*- coding: UTF-8 -*-
#
# The MIT License
# 
# Copyright (c) 2010 Felix Schwarz <felix.schwarz@oss.schwarz.eu>
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


from pycerberus.errors import InvalidDataError

from pymta.lib import PythonicTestCase
from pymta.validation import SMTPEmailValidator


class SMTPEmailValidatorTest(PythonicTestCase):
    
    def process(self, input_string):
        return SMTPEmailValidator().process(input_string)
    
    def test_accept_plain_email_address(self):
        self.assert_equals('foo@example.com', self.process('foo@example.com'))
    
    def test_accept_email_address_in_angle_brackets(self):
        self.assert_equals('foo@example.com', self.process('<foo@example.com>'))
    
    def test_reject_email_address_in_unbalanced_angle_brackets(self):
        self.assert_raises(InvalidDataError, lambda: self.process('<foo@example.com'))
        self.assert_raises(InvalidDataError, lambda: self.process('foo@example.com>'))
    
    def test_reject_invalid_email_addresses(self):
        self.assert_raises(InvalidDataError, lambda: self.process('foo@@example.com'))
        self.assert_raises(InvalidDataError, lambda: self.process('foo@example..com'))


