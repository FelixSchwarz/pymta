# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import absolute_import, print_function, unicode_literals

import base64
from unittest import TestCase

import pytest
from pymta.compat import b64encode
from pymta.validation import (
    AuthLoginSchema,
    AuthPlainSchema,
    InvalidDataError,
    MailFromSchema,
    RcptToSchema,
    SMTPCommandArgumentsSchema,
)


class CommandWithoutParametersTest(TestCase):

    def schema(self):
        return SMTPCommandArgumentsSchema()

    def test_accept_command_without_parameters(self):
        assert self.schema().process('') == {}

    def test_bails_out_if_additional_parameters_are_passed(self):
        with pytest.raises(InvalidDataError) as exc_info:
            self.schema().process('fnord')
        assert exc_info.value.msg() == "Syntactically invalid argument(s) 'fnord'"


class SingleParameterSchema(SMTPCommandArgumentsSchema):
    parameter_order = ('parameter',)


class CommandWithSingleParameterTest(TestCase):

    def test_accepts_one_parameter(self):
        assert SingleParameterSchema().process('fnord') == {'parameter': 'fnord'}

    def test_bails_out_if_no_parameter_is_passed(self):
        with pytest.raises(InvalidDataError):
            SingleParameterSchema().process('')

    def test_bails_out_if_more_than_one_parameter_is_passed(self):
        with pytest.raises(InvalidDataError) as exc_info:
            SingleParameterSchema().process('fnord extra')
        assert exc_info.value.msg() == "Syntactically invalid argument(s) 'extra'"

    def test_can_specify_parameter_order_declaratively(self):
        class SchemaWithOrderedParameters(SMTPCommandArgumentsSchema):
            parameter_order = ('foo', 'bar')

        schema = SchemaWithOrderedParameters()
        assert schema.process('baz qux') == {'foo': 'baz', 'bar': 'qux'}


class MailFromSchemaWithBody(MailFromSchema):

    def extensions(self):
        extensions = super(MailFromSchemaWithBody, self).extensions()
        extensions['body'] = lambda value: value
        return extensions


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

    def test_accept_null_reverse_path(self):
        # RFC 5321, section 4.5.5: bounces use an empty reverse-path
        assert self.process('<>')['email'] == ''

    def test_ignores_source_route(self):
        cmd_parameters = self.process('<@relay.example:foo@example.com>')
        assert cmd_parameters['email'] == 'foo@example.com'

    def test_rejects_postmaster_without_domain(self):
        with pytest.raises(InvalidDataError):
            self.process('<postmaster>')

    def test_rejects_missing_email_address(self):
        with pytest.raises(InvalidDataError):
            self.process('')

    # --------------------------------------------------------------------------
    # SMTP extensions

    def test_reject_extensions_for_plain_smtp(self):
        input_command = '<foo@example.com> SIZE=1000'
        with pytest.raises(InvalidDataError) as exc_info:
            self.process(input_command, esmtp=False)
        e = exc_info.value
        assert e.msg() == 'No SMTP extensions allowed for plain SMTP.'

    def test_can_parse_extensions(self):
        schema = MailFromSchemaWithBody()
        input_command = '<foo@example.com> BODY=BINARYMIME'
        cmd_parameters = schema.process(input_command, context={'esmtp': True})
        expected_parameters = {'email': 'foo@example.com', 'body': 'BINARYMIME'}
        assert _subdict(cmd_parameters, {'email', 'body'}) == expected_parameters

    def test_ignores_whitespace_surrounding_extensions(self):
        schema = MailFromSchemaWithBody()
        input_command = '<foo@example.com>   BODY=BINARYMIME  '
        cmd_parameters = schema.process(input_command, context={'esmtp': True})
        expected_parameters = {'email': 'foo@example.com', 'body': 'BINARYMIME'}
        assert _subdict(cmd_parameters, {'email', 'body'}) == expected_parameters

    def test_treats_extensions_as_case_insensitive(self):
        schema = MailFromSchemaWithBody()
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
        with pytest.raises(InvalidDataError) as exc_ctx:
            self.process(input_command, esmtp=True)
        assert exc_ctx.value.msg() == 'Invalid size: Must be a number.'

    def test_reject_empty_size_parameter(self):
        with pytest.raises(InvalidDataError):
            self.process('foo@example.com SIZE=', esmtp=True)


class RcptToSchemaTest(TestCase):

    def process(self, input_string):
        return RcptToSchema().process(input_string)

    def test_accept_email_address(self):
        assert self.process('<foo@example.com>') == {'email': 'foo@example.com'}

    def test_accept_postmaster_without_domain(self):
        # RFC 5321, section 4.1.1.3
        assert self.process('<Postmaster>') == {'email': 'Postmaster'}
        assert self.process('<postmaster>') == {'email': 'postmaster'}

    def test_rejects_null_path(self):
        with pytest.raises(InvalidDataError):
            self.process('<>')

    def test_rejects_additional_parameters(self):
        with pytest.raises(InvalidDataError) as exc_ctx:
            self.process('<foo@example.com> invalid')
        assert exc_ctx.value.msg() == "Syntactically invalid argument(s) 'invalid'"


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

    def test_rejects_empty_username(self):
        e = self.assert_bad_input(self.base64('\x00\x00foo'))
        assert e.msg() == 'Garbled data sent'

    def test_decodes_utf8_credentials(self):
        credentials = base64.b64encode(b'\x00foo\x00p\xc3\xa4ss').decode('ascii')
        parameters = self.schema().process(credentials)
        assert parameters['password'] == 'p\xe4ss'


class AuthLoginSchemaTest(TestCase):

    def process(self, input_string):
        return AuthLoginSchema().process(input_string)

    def test_can_extract_base64_decoded_username(self):
        assert self.process(b64encode('foo')) == {'username': 'foo'}

    def test_rejects_bad_base64(self):
        for value in ('invalid!', 'Zm9', 'Zm9v!'):
            with pytest.raises(InvalidDataError) as exc_ctx:
                self.process(value)
            assert exc_ctx.value.msg() == 'Garbled data sent'

    def test_rejects_empty_input(self):
        with pytest.raises(InvalidDataError):
            self.process('')

    def test_rejects_more_than_one_parameter(self):
        with pytest.raises(InvalidDataError):
            self.process(b64encode('foo') + ' ' + b64encode('bar'))


def _subdict(src_dict, keys):
    subdict = {}
    for key in keys:
        if key in src_dict:
            subdict[key] = src_dict[key]
    return subdict
