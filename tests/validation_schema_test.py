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
from pycerberus.validators import StringValidator

from pymta.lib import PythonicTestCase
from pymta.validation import AuthPlainSchema, MailFromSchema, SMTPCommandArgumentsSchema


class CommandWithoutParametersTest(PythonicTestCase):
    
    def schema(self):
        return SMTPCommandArgumentsSchema()
    
    def test_accept_command_without_parameters(self):
        self.assert_equals({}, self.schema().process(''))
    
    def test_bails_out_if_additional_parameters_are_passed(self):
        e = self.assert_raises(InvalidDataError, lambda: self.schema().process('fnord'))
        self.assert_equals('Syntactically invalid argument(s) \'fnord\'', e.msg())


class CommandWithSingleParameterTest(PythonicTestCase):
    
    def schema(self):
        schema = SMTPCommandArgumentsSchema()
        schema.set_internal_state_freeze(False)
        return schema
    
    def test_accepts_one_parameter(self):
        schema = self.schema()
        schema.add('parameter', StringValidator)
        schema.set_parameter_order(('parameter',))
        self.assert_equals({'parameter': 'fnord'}, schema.process('fnord'))
    
    def test_bails_out_if_no_parameter_is_passed(self):
        schema = self.schema()
        schema.add('parameter', StringValidator)
        self.assert_raises(InvalidDataError, lambda: schema.process(''))
    
    def test_bails_out_if_more_than_one_parameter_is_passed(self):
        schema = self.schema()
        schema.add('parameter', StringValidator)
        self.assert_raises(InvalidDataError, lambda: schema.process('fnord extra'))
    
    def test_can_use_custom_name_for_parameters(self):
        schema = self.schema()
        schema.add('helo', StringValidator)
        schema.set_parameter_order(('helo', ))
        self.assert_equals({'helo': 'localhost'}, schema.process('localhost'))
    
    def test_can_specify_parameter_order_declaratively(self):
        class SchemaWithOrderedParameters(SMTPCommandArgumentsSchema):
            foo = StringValidator()
            bar = StringValidator()
            parameter_order = ('foo', 'bar')
        
        schema = SchemaWithOrderedParameters()
        self.assert_equals({'foo': 'baz', 'bar': 'qux'}, schema.process('baz qux'))


class MailFromSchemaTest(PythonicTestCase):
    
    def schema(self):
        return MailFromSchema()
    
    def process(self, input_string, esmtp=None):
        context = {}
        if esmtp is not None:
            context['esmtp'] = esmtp
        return self.schema().process(input_string, context=context)
    
    # --------------------------------------------------------------------------
    # validating the email address
    
    def test_accept_plain_email_address(self):
        self.assert_dict_contains({'email': 'foo@example.com'}, self.process('foo@example.com'))
    
    # --------------------------------------------------------------------------
    # SMTP extensions
    
    def test_reject_extensions_for_plain_smtp(self):
        input_command = '<foo@example.com> SIZE=1000'
        call = lambda: self.process(input_command, esmtp=False)
        e = self.assert_raises(InvalidDataError, call)
        self.assert_equals('No SMTP extensions allowed for plain SMTP.', e.msg())
    
    def test_can_parse_extensions(self):
        schema = self.schema()
        schema.add('body', StringValidator())
        input_command = '<foo@example.com> BODY=BINARYMIME'
        self.assert_dict_contains({'email': 'foo@example.com', 'body': 'BINARYMIME'}, 
                                  schema.process(input_command, context={'esmtp': True}))
    
    def test_ignores_whitespace_surrounding_extensions(self):
        schema = self.schema()
        schema.add('body', StringValidator())
        input_command = '<foo@example.com>   BODY=BINARYMIME  '
        self.assert_dict_contains({'email': 'foo@example.com', 'body': 'BINARYMIME'}, 
                                  schema.process(input_command, context={'esmtp': True}))
    
    def test_treats_extensions_as_case_insensitive(self):
        schema = self.schema()
        schema.add('body', StringValidator())
        input_command = '<foo@example.com> bOdY=BINARYMIME'
        self.assert_dict_contains({'email': 'foo@example.com', 'body': 'BINARYMIME'}, 
                                  schema.process(input_command, context={'esmtp': True}))
    
    def test_present_meaningful_error_message_for_unknown_arguments(self):
        input_command = 'foo@example.com foo bar'
        call = lambda: self.process(input_command, esmtp=True)
        e = self.assert_raises(InvalidDataError, call)
        self.assert_equals('Invalid arguments: \'foo bar\'', e.msg())
    
    def test_present_meaningful_error_message_for_unknown_extensions(self):
        input_command = 'foo@example.com invalid=fnord'
        call = lambda: self.process(input_command, esmtp=True)
        e = self.assert_raises(InvalidDataError, call)
        self.assert_equals('Invalid extension: \'invalid=fnord\'', e.msg())
    
    
    # ----------------------------------------------------------------------------
    # Tests for validation of specific extensions
    
    # --------------------------------------------------------------------------
    # SMTP SIZE extension
    
    def test_can_extract_size_parameter_if_esmtp_is_enabled(self):
        input_command = 'foo@example.com SIZE=1000'
        self.assert_dict_contains({'size': 1000}, self.process(input_command, esmtp=True))
    
    def test_size_parameter_is_not_mandatory_even_when_using_esmtp(self):
        parameters = self.process('foo@example.com', esmtp=True)
        self.assert_dict_contains({'email': 'foo@example.com'}, parameters)
    
    def test_reject_size_below_zero(self):
        input_command = 'foo@example.com SIZE=-1234'
        call = lambda: self.process(input_command, esmtp=True)
        e = self.assert_raises(InvalidDataError, call)
        self.assert_equals('Invalid size: Must be 1 or greater.', e.msg())
    
    def test_reject_non_numeric_size_parameter(self):
        input_command = 'foo@example.com SIZE=fnord'
        self.assert_raises(InvalidDataError, lambda: self.process(input_command, esmtp=True))


class AuthPlainSchemaTest(PythonicTestCase):
    
    def schema(self):
        return AuthPlainSchema()
    
    def process(self, input_string, esmtp=None):
        context = {}
        if esmtp is not None:
            context['esmtp'] = esmtp
        return self.schema().process(input_string, context=context)
    
    def test_can_extract_base64_decoded_string(self):
        expected_parameters = dict(username='foo', password='foo ', authzid=None)
        parameters = self.schema().process(self.base64(u'\x00foo\x00foo '))
        self.assert_equals(expected_parameters, parameters)
    
    def base64(self, value):
        return unicode(value).encode('base64').strip()
    
    def assert_bad_input(self, input):
        e = self.assert_raises(InvalidDataError, lambda: self.schema().process(input))
        return e
    
    def test_reject_more_than_one_parameter(self):
        input = self.base64(u'\x00foo\x00foo') + ' ' + self.base64(u'\x00foo\x00foo')
        self.assert_bad_input(input)
    
    def test_rejects_bad_base64(self):
        e = self.assert_bad_input('invalid')
        self.assert_equals('Garbled data sent', e.msg())
    
    def test_rejects_invalid_format(self):
        e = self.assert_bad_input(u'foobar'.encode('base64'))
        self.assert_equals('Garbled data sent', e.msg())


