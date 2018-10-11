# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

import re

from pycerberus.i18n import _
from pycerberus.schemas import PositionalArgumentsParsingSchema
from pycerberus.validators import EmailAddressValidator, IntegerValidator, StringValidator

from pymta.compat import dict_keys, dict_values, b, b64decode

__all__ = ['HeloSchema', 'MailFromSchema', 'RcptToSchema', 'SMTPCommandArgumentsSchema']


# ------------------------------------------------------------------------------
# General infrastructure

class SMTPCommandArgumentsSchema(PositionalArgumentsParsingSchema):
    
    def messages(self):
        return {'additional_item': _("Syntactically invalid argument(s) '%(additional_item)s'")}

    def separator_pattern(self):
        return '\s+'


class SMTPEmailValidator(EmailAddressValidator):
    
    def messages(self):
        return {'unbalanced_quotes': _('Invalid email address format - use balanced angle brackets.')}
    
    def convert(self, value, context):
        string_value = self.super()
        if string_value.startswith('<') or string_value.endswith('>'):
            match = re.search('^<(.+)>$', string_value)
            if match is None:
                self.raise_error('unbalanced_quotes', string_value, context)
            string_value = match.group(1)
        return string_value

# ------------------------------------------------------------------------------
# MAIL FROM

class SizeExtensionValidator(IntegerValidator):
    
    def __init__(self, *args, **kwargs):
        kwargs.update({'required': False, 'min': 1})
        self.super()
    
    def messages(self):
        return {'too_low': _('Invalid size: Must be %(min)s or greater.')}


class MailFromSchema(SMTPCommandArgumentsSchema):
    email = SMTPEmailValidator()
    size  = SizeExtensionValidator()
    
    parameter_order = ('email',)
    
    def messages(self):
        return {
            'invalid_extension': _('Invalid extension: %(smtp_extension)s'),
            'invalid_smtp_arguments': _('Invalid arguments: %(smtp_arguments)s'),
            'no_extensions': _('No SMTP extensions allowed for plain SMTP.'),
        }
    
    # --------------------------------------------------------------------------
    # special implementations for SMTP extensions
    
    def uses_esmtp(self, context):
        return context.get('esmtp', False)
    
    def _assert_all_options_have_a_value_assigned(self, key_value_pairs, input_string, context):
        for option in key_value_pairs:
            if len(option) == 2:
                continue
            value = ''.join(option)
            self.raise_error('invalid_smtp_arguments', value, context, smtp_arguments=repr(input_string))
    
    def _assert_only_known_extensions(self, key_value_pairs, input_string, context):
        for key, value in key_value_pairs:
            if key.lower() in self.fieldvalidators():
                continue
            value = '='.join((key, value))
            self.raise_error('invalid_extension', value, context, smtp_extension=repr(input_string))
    
    def _validate_extension_arguments(self, key_value_pairs, input_string, context):
        self._assert_all_options_have_a_value_assigned(key_value_pairs, input_string, context)
        self._assert_only_known_extensions(key_value_pairs, input_string, context)
    
    def aggregate_values(self, parameter_names, arguments, context):
        if len(arguments) <= 1:
            return self.super()
        key_value_pairs = [re.split('=', option, 1) for option in arguments[1:]]

        self._validate_extension_arguments(key_value_pairs, ' '.join(arguments[1:]), context)
        lower_case_key_value_pairs = [(item[0].lower(), item[1]) for item in key_value_pairs]
        options = dict(lower_case_key_value_pairs)
        
        parameter_names = parameter_names + dict_keys(options)
        arguments = [arguments[0]] + dict_values(options)
        return parameter_names, arguments
    
    def _process_fields(self, fields, context):
        if len(fields) > 1 and not self.uses_esmtp(context):
            self.raise_error('no_extensions', '', context)
        return self.super()

# ------------------------------------------------------------------------------

class HeloSchema(SMTPCommandArgumentsSchema):
    helo = StringValidator(strip=True)
    
    parameter_order = ('helo',)


class RcptToSchema(SMTPCommandArgumentsSchema):
    email = SMTPEmailValidator()
    
    parameter_order = ('email',)

# ------------------------------------------------------------------------------
# AUTH PLAIN

class AuthPlainSchema(SMTPCommandArgumentsSchema):
    authzid  = StringValidator(required=False, default=None)
    username = StringValidator()
    password = StringValidator()
    
    parameter_order = ('authzid', 'username', 'password')
    
    def messages(self):
        return {
            'invalid_base64': _('Garbled data sent'),
            'invalid_format': _('Garbled data sent'),
        }
    
    # --------------------------------------------------------------------------
    # special implementations for SMTP extensions
    
    def _decode_base64(self, value, context):
        try:
            return b64decode(value)
        except:
            self.raise_error('invalid_base64', value, context)
    
    def split_parameters(self, value, context):
        match = re.search(('=\s(.+)$'), value.strip())
        if match is not None:
            self.raise_error('additional_item', value, context, additional_item=repr(match.group(1)))
        decoded_parameters = self._decode_base64(value, context)
        match = re.search('^([^\x00]*)\x00([^\x00]*)\x00([^\x00]*)$', decoded_parameters)
        if not match:
            self.raise_error('invalid_format', value, context)
        parameters = list(match.groups())
        if parameters[0] == '':
            parameters[0] = None
        return parameters

