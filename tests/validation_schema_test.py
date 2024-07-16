# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import absolute_import, print_function, unicode_literals

from unittest import TestCase

from pycerberus.errors import InvalidDataError
from pycerberus.validators import StringValidator
import pytest

from pymta.compat import b64encode
from pymta.validation import AuthPlainSchema, MailFromSchema, SMTPCommandArgumentsSchema


class CommandWithoutParametersTest(TestCase):

    def schema(self):
        return SMTPCommandArgumentsSchema()

    def test_accept_command_without_parameters(self):
        assert self.schema().process('') == {}

    def test_bails_out_if_additional_parameters_are_passed(self):
        with pytest.raises(InvalidDataError) as exc_info:
            self.schema().process('fnord')
        assert exc_info.value.msg() == "Syntactically invalid argument(s) 'fnord'"


class CommandWithSingleParameterTest(TestCase):

    def schema(self):
        schema = SMTPCommandArgumentsSchema()
        schema.set_internal_state_freeze(False)
        return schema

    def test_accepts_one_parameter(self):
        schema = self.schema()
        schema.add('parameter', StringValidator)
        schema.set_parameter_order(('parameter',))
        assert schema.process('fnord') == {'parameter': 'fnord'}

    def test_bails_out_if_no_parameter_is_passed(self):
        schema = self.schema()
        schema.add('parameter', StringValidator)
        with pytest.raises(InvalidDataError):
            schema.process('')

    def test_bails_out_if_more_than_one_parameter_is_passed(self):
        schema = self.schema()
        schema.add('parameter', StringValidator)
        with pytest.raises(InvalidDataError):
            schema.process('fnord extra')

    def test_can_use_custom_name_for_parameters(self):
        schema = self.schema()
        schema.add('helo', StringValidator)
        schema.set_parameter_order(('helo', ))
        assert schema.process('localhost') == {'helo': 'localhost'}

    def test_can_specify_parameter_order_declaratively(self):
        class SchemaWithOrderedParameters(SMTPCommandArgumentsSchema):
            foo = StringValidator()
            bar = StringValidator()
            parameter_order = ('foo', 'bar')

        schema = SchemaWithOrderedParameters()
        assert schema.process('baz qux') == {'foo': 'baz', 'bar': 'qux'}


class MailFromSchemaTest(TestCase):

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
        cmd_parameters = self.process('foo@example.com')
        assert _subdict(cmd_parameters, {'email'}) == {'email': 'foo@example.com'}

    # --------------------------------------------------------------------------
    # SMTP extensions

    def test_reject_extensions_for_plain_smtp(self):
        input_command = '<foo@example.com> SIZE=1000'
        with pytest.raises(InvalidDataError) as exc_info:
            self.process(input_command, esmtp=False)
        e = exc_info.value
        assert e.msg() == 'No SMTP extensions allowed for plain SMTP.'

    def test_can_parse_extensions(self):
        schema = self.schema()
        schema.add('body', StringValidator())
        input_command = '<foo@example.com> BODY=BINARYMIME'
        cmd_parameters = schema.process(input_command, context={'esmtp': True})
        expected_parameters = {'email': 'foo@example.com', 'body': 'BINARYMIME'}
        assert _subdict(cmd_parameters, {'email', 'body'}) == expected_parameters

    def test_ignores_whitespace_surrounding_extensions(self):
        schema = self.schema()
        schema.add('body', StringValidator())
        input_command = '<foo@example.com>   BODY=BINARYMIME  '
        cmd_parameters = schema.process(input_command, context={'esmtp': True})
        expected_parameters = {'email': 'foo@example.com', 'body': 'BINARYMIME'}
        assert _subdict(cmd_parameters, {'email', 'body'}) == expected_parameters

    def test_treats_extensions_as_case_insensitive(self):
        schema = self.schema()
        schema.add('body', StringValidator())
        input_command = '<foo@example.com> bOdY=BINARYMIME'
        cmd_parameters = schema.process(input_command, context={'esmtp': True})
        expected_parameters = {'email': 'foo@example.com', 'body': 'BINARYMIME'}
        assert _subdict(cmd_parameters, {'email', 'body'}) == expected_parameters

    def test_present_meaningful_error_message_for_unknown_arguments(self):
        input_command = 'foo@example.com foo bar'
        with pytest.raises(InvalidDataError) as exc_ctx:
            self.process(input_command, esmtp=True)
        e = exc_ctx.value
        assert e.msg() == 'Invalid arguments: "foo bar"'

    def test_present_meaningful_error_message_for_unknown_extensions(self):
        input_command = 'foo@example.com invalid=fnord'
        with pytest.raises(InvalidDataError) as exc_ctx:
            self.process(input_command, esmtp=True)
        e = exc_ctx.value
        assert e.msg() == 'Invalid extension: "invalid=fnord"'


    # ----------------------------------------------------------------------------
    # Tests for validation of specific extensions

    # --------------------------------------------------------------------------
    # SMTP SIZE extension

    def test_can_extract_size_parameter_if_esmtp_is_enabled(self):
        input_command = 'foo@example.com SIZE=1000'
        cmd_parameters = self.process(input_command, esmtp=True)
        assert _subdict(cmd_parameters, {'size'}) == {'size': 1000}

    def test_size_parameter_is_not_mandatory_even_when_using_esmtp(self):
        cmd_parameters = self.process('foo@example.com', esmtp=True)
        assert _subdict(cmd_parameters, {'email'}) == {'email': 'foo@example.com'}

    def test_reject_size_below_zero(self):
        input_command = 'foo@example.com SIZE=-1234'
        with pytest.raises(InvalidDataError) as exc_ctx:
            self.process(input_command, esmtp=True)
        e = exc_ctx.value
        assert e.msg() == 'Invalid size: Must be 1 or greater.'

    def test_reject_non_numeric_size_parameter(self):
        input_command = 'foo@example.com SIZE=fnord'
        with pytest.raises(InvalidDataError):
            self.process(input_command, esmtp=True)


class AuthPlainSchemaTest(TestCase):

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
        assert parameters == expected_parameters

    def base64(self, value):
        return b64encode(value).strip()

    def assert_bad_input(self, input):
        with pytest.raises(InvalidDataError) as exc_ctx:
            self.schema().process(input)
        e = exc_ctx.value
        return e

    def test_reject_more_than_one_parameter(self):
        input = self.base64('\x00foo\x00foo') + ' ' + self.base64('\x00foo\x00foo')
        self.assert_bad_input(input)

    def test_rejects_bad_base64(self):
        e = self.assert_bad_input('invalid')
        assert e.msg() == 'Garbled data sent'

    def test_rejects_invalid_format(self):
        e = self.assert_bad_input(b64encode('foobar'))
        assert e.msg() == 'Garbled data sent'


def _subdict(src_dict, keys):
    subdict = {}
    for key in keys:
        if key in src_dict:
            subdict[key] = src_dict[key]
    return subdict
