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

import base64
import re

from pycerberus.i18n import _
from pycerberus.schema import SchemaValidator
from pycerberus.validators import EmailAddressValidator, IntegerValidator, \
    StringValidator

__all__ = ['HeloSchema', 'MailFromSchema', 'RcptToSchema', 
           'SMTPCommandArgumentsSchema']


# ------------------------------------------------------------------------------
# General infrastructure


class SMTPCommandArgumentsSchema(SchemaValidator):
    
    def __init__(self, *args, **kwargs):
        self.super()
        self.set_internal_state_freeze(False)
        self.set_allow_additional_parameters(False)
        self.set_parameter_order(getattr(self.__class__, 'parameter_order', ()))
        self.set_internal_state_freeze(True)
    
    def messages(self):
        return {'additional_items': _('Syntactically invalid argument(s) %(additional_items)s')}
    
    def _parameter_names(self):
        return list(self._parameter_order)
    
    def _assign_names(self, arguments, context):
        parameter_names = self._parameter_names()
        nr_missing_parameters = max(len(parameter_names) - len(arguments), 0)
        nr_additional_parameters = max(len(arguments), len(parameter_names), 0)
        arguments.extend([None] * nr_missing_parameters)
        parameter_names.extend(['extra%d' % i for i in xrange(nr_additional_parameters)])
        return dict(zip(parameter_names, arguments))
    
    def _parse_parameters(self, value, context):
        arguments = []
        if len(value) > 0:
            arguments = re.split('\s+', value.strip())
        return arguments
    
    def _map_arguments_to_named_fields(self, value, context):
        return self._assign_names(self._parse_parameters(value, context), context)
    
    def set_parameter_order(self, parameter_names):
        self._parameter_order = parameter_names
    
    def process(self, value, context=None):
        fields = self._map_arguments_to_named_fields(value, context or {})
        return self.super(fields, context=context)


class SMTPEmailValidator(EmailAddressValidator):
    
    def messages(self):
        return {'unbalanced_quotes': _(u'Invalid email address format - use balanced angle brackets.')}
    
    def convert(self, value, context):
        string_value = self.super()
        if string_value.startswith('<') or string_value.endswith('>'):
            match = re.search('^<(.+)>$', string_value)
            if match is None:
                self.error('unbalanced_quotes', string_value, context)
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
            self.error('invalid_smtp_arguments', value, context, smtp_arguments=repr(input_string))
    
    def _assert_only_known_extensions(self, key_value_pairs, input_string, context):
        for key, value in key_value_pairs:
            if key.lower() in self.fieldvalidators():
                continue
            value = '='.join((key, value))
            self.error('invalid_extension', value, context, smtp_extension=repr(input_string))
    
    def _validate_extension_arguments(self, key_value_pairs, input_string, context):
        self._assert_all_options_have_a_value_assigned(key_value_pairs, input_string, context)
        self._assert_only_known_extensions(key_value_pairs, input_string, context)
    
    def _assign_names(self, arguments, context):
        if len(arguments) <= 1:
            return self.super()
        
        key_value_pairs = map(lambda option: re.split('=', option, 1), arguments[1:])
        self._validate_extension_arguments(key_value_pairs, ' '.join(arguments[1:]), context)
        lower_case_key_value_pairs = map(lambda item: (item[0].lower(), item[1]), key_value_pairs)
        options = dict(lower_case_key_value_pairs)
        parameters = self.super(arguments[:1], context)
        options.update(parameters)
        return options
    
    def _process_fields(self, fields, context):
        if len(fields) > 1 and not self.uses_esmtp(context):
            self.error('no_extensions', '', context)
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
            return base64.decodestring(value)
        except:
            self.error('invalid_base64', value, context)
    
    def _parse_parameters(self, value, context):
        match = re.search('=\s(.+)$', value.strip())
        if match is not None:
            self.error('additional_items', value, context, additional_items=repr(match.group(1)))
        decoded_parameters = self._decode_base64(value, context)
        match = re.search('^([^\x00]*)\x00([^\x00]*)\x00([^\x00]*)$', decoded_parameters)
        if not match:
            self.error('invalid_format', value, context)
        items = list(match.groups())
        if items[0] == '':
            items[0] = None
        return items

