# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

from pycerberus.errors import InvalidDataError
from pycerberus.validators import StringValidator
from pythonic_testcase import *

from pymta.compat import b64encode
from pymta.validation import AuthPlainSchema, MailFromSchema, SMTPCommandArgumentsSchema


class CommandWithoutParametersTest(PythonicTestCase):

    def schema(self):
        return SMTPCommandArgumentsSchema()

    def test_accept_command_without_parameters(self):
        assert_equals({}, self.schema().process(''))

    def test_bails_out_if_additional_parameters_are_passed(self):
        e = self.assert_raises(InvalidDataError, lambda: self.schema().process('fnord'))
        assert_equals("Syntactically invalid argument(s) 'fnord'", e.msg())


class CommandWithSingleParameterTest(PythonicTestCase):

    def schema(self):
        schema = SMTPCommandArgumentsSchema()
        schema.set_internal_state_freeze(False)
        return schema

    def test_accepts_one_parameter(self):
        schema = self.schema()
        schema.add('parameter', StringValidator)
        schema.set_parameter_order(('parameter',))
        assert_equals({'parameter': 'fnord'}, schema.process('fnord'))

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
        assert_equals({'helo': 'localhost'}, schema.process('localhost'))

    def test_can_specify_parameter_order_declaratively(self):
        class SchemaWithOrderedParameters(SMTPCommandArgumentsSchema):
            foo = StringValidator()
            bar = StringValidator()
            parameter_order = ('foo', 'bar')

        schema = SchemaWithOrderedParameters()
        assert_equals({'foo': 'baz', 'bar': 'qux'}, schema.process('baz qux'))


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
        assert_equals('No SMTP extensions allowed for plain SMTP.', e.msg())

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
        with assert_raises(InvalidDataError) as exc_ctx:
            self.process(input_command, esmtp=True)
        e = exc_ctx.caught_exception
        assert_equals('Invalid arguments: "foo bar"', e.msg())

    def test_present_meaningful_error_message_for_unknown_extensions(self):
        input_command = 'foo@example.com invalid=fnord'
        with assert_raises(InvalidDataError) as exc_ctx:
            self.process(input_command, esmtp=True)
        e = exc_ctx.caught_exception
        assert_equals('Invalid extension: "invalid=fnord"', e.msg())


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
        with assert_raises(InvalidDataError) as exc_ctx:
            self.process(input_command, esmtp=True)
        e = exc_ctx.caught_exception
        assert_equals('Invalid size: Must be 1 or greater.', e.msg())

    def test_reject_non_numeric_size_parameter(self):
        input_command = 'foo@example.com SIZE=fnord'
        with assert_raises(InvalidDataError):
            self.process(input_command, esmtp=True)


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
        parameters = self.schema().process(self.base64('\x00foo\x00foo '))
        assert_equals(expected_parameters, parameters)

    def base64(self, value):
        return b64encode(value).strip()

    def assert_bad_input(self, input):
        with assert_raises(InvalidDataError) as exc_ctx:
            self.schema().process(input)
        e = exc_ctx.caught_exception
        return e

    def test_reject_more_than_one_parameter(self):
        input = self.base64('\x00foo\x00foo') + ' ' + self.base64('\x00foo\x00foo')
        self.assert_bad_input(input)

    def test_rejects_bad_base64(self):
        e = self.assert_bad_input('invalid')
        assert_equals('Garbled data sent', e.msg())

    def test_rejects_invalid_format(self):
        e = self.assert_bad_input(b64encode('foobar'))
        assert_equals('Garbled data sent', e.msg())


