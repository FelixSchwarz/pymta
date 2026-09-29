# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT
"""Validation of SMTP command arguments.

Email addresses are checked against the syntax of RFC 5321 (section 4.1.2)
with some simplifications:
 - address literals ("user@[127.0.0.1]") are only checked superficially
 - international addresses (SMTPUTF8) are not supported
 - addresses without angle brackets are accepted
"""

from __future__ import print_function, unicode_literals

import base64
import re


__all__ = [
    'AuthLoginSchema',
    'AuthPlainSchema',
    'HeloSchema',
    'InvalidDataError',
    'MailFromSchema',
    'RcptToSchema',
    'SMTPCommandArgumentsSchema',
    'parse_forward_path',
    'parse_reverse_path',
]


class InvalidDataError(Exception):
    """The client sent invalid command arguments. The message (``.msg()``)
    can be sent back to the client."""

    def __init__(self, msg, value=None):
        super(InvalidDataError, self).__init__(msg)
        self._msg = msg
        self.value = value

    def msg(self):
        return self._msg

# ------------------------------------------------------------------------------
# email addresses (RFC 5321, section 4.1.2)

_ATOM = r"[A-Za-z0-9!#$%&'*+\-/=?^_`{|}~]+"
_DOT_STRING = r'%s(?:\.%s)*' % (_ATOM, _ATOM)
_QUOTED_STRING = r'"(?:[\x20\x21\x23-\x5b\x5d-\x7e]|\\[\x20-\x7e])*"'
_SUB_DOMAIN = r'[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?'
_DOMAIN = r'%s(?:\.%s)*' % (_SUB_DOMAIN, _SUB_DOMAIN)
# IPv4 ("[127.0.0.1]") or tagged ("[IPv6:::1]")
_IPV4_LITERAL = r'[0-9]{1,3}(?:\.[0-9]{1,3}){3}'
_TAGGED_LITERAL = r'[A-Za-z0-9\-]*[A-Za-z0-9]:[\x21-\x5a\x5e-\x7e]+'
_ADDRESS_LITERAL = r'\[(?:%s|%s)\]' % (_IPV4_LITERAL, _TAGGED_LITERAL)
_MAILBOX = r'(?:%s|%s)@(?:%s|%s)' % (_DOT_STRING, _QUOTED_STRING, _DOMAIN, _ADDRESS_LITERAL)
# source routes ("<@relay.example:user@example.com>") are obsolete and must
# be ignored by the server (RFC 5321, section 4.1.1.3 and appendix C)
_SOURCE_ROUTE = r'@%s(?:,@%s)*:' % (_DOMAIN, _DOMAIN)

_MAILBOX_RE = re.compile(r'^(?:%s)?(%s)\Z' % (_SOURCE_ROUTE, _MAILBOX))
# "<" ... ">" (quoted strings might contain ">") followed by optional parameters
_ANGLE_PATH_RE = re.compile(r'^<((?:"(?:[^"\\]|\\.)*"|[^"<>])*)>(?:\s+(.*))?\Z')
_UNBALANCED_BRACKETS = 'Invalid email address format - use balanced angle brackets.'


def _split_path(value):
    """Split the arguments of "MAIL FROM"/"RCPT TO" into the path (without
    angle brackets) and the (possibly empty) string with additional
    parameters."""
    value = (value or '').strip()
    if not value:
        raise InvalidDataError('Missing email address.', value)
    if value.startswith('<'):
        match = _ANGLE_PATH_RE.search(value)
        if match is None:
            raise InvalidDataError(_UNBALANCED_BRACKETS, value)
        return match.group(1), (match.group(2) or '').strip()
    path, parameters = (re.split(r'\s+', value, maxsplit=1) + [''])[:2]
    if path.endswith('>'):
        raise InvalidDataError(_UNBALANCED_BRACKETS, value)
    return path, parameters


def _parse_mailbox(path):
    match = _MAILBOX_RE.search(path)
    if match is None:
        raise InvalidDataError('Invalid email address "%s".' % path, path)
    return match.group(1)


def parse_reverse_path(path):
    """Return the sender address (without angle brackets) or an empty string
    for the null reverse-path ("<>", used for bounces)."""
    if path == '':
        return ''
    return _parse_mailbox(path)


def parse_forward_path(path):
    """Return the recipient address (without angle brackets). "Postmaster"
    (without domain) is also accepted (RFC 5321, section 4.1.1.3)."""
    if path.lower() == 'postmaster':
        return path
    return _parse_mailbox(path)

# ------------------------------------------------------------------------------
# General infrastructure

class SMTPCommandArgumentsSchema(object):
    """Parses whitespace-separated positional arguments. The subclasses list
    the names of the (mandatory) arguments in ``parameter_order``."""
    parameter_order = ()

    def process(self, value, context=None):
        arguments = self._split_arguments(value)
        if len(arguments) < len(self.parameter_order):
            raise InvalidDataError('Value must not be empty.', value)
        result = {}
        for name, argument in zip(self.parameter_order, arguments):
            result[name] = self.validate_argument(name, argument, context or {})
        return result

    def validate_argument(self, name, value, context):
        return value

    def _split_arguments(self, value):
        arguments = (value or '').split()
        nr_parameters = len(self.parameter_order)
        if len(arguments) > nr_parameters:
            additional_items = ' '.join(arguments[nr_parameters:])
            raise InvalidDataError(
                "Syntactically invalid argument(s) '%s'" % additional_items, value)
        return arguments

# ------------------------------------------------------------------------------
# HELO/EHLO

class HeloSchema(SMTPCommandArgumentsSchema):
    parameter_order = ('helo',)

# ------------------------------------------------------------------------------
# MAIL FROM

def _parse_size(value):
    if re.search(r'^-?[0-9]+\Z', value) is None:
        raise InvalidDataError('Invalid size: Must be a number.', value)
    size = int(value)
    if size < 1:
        raise InvalidDataError('Invalid size: Must be 1 or greater.', value)
    return size


class MailFromSchema(SMTPCommandArgumentsSchema):

    def extensions(self):
        """Return the supported parameters (lower case) and a callable which
        validates/converts the value of each parameter."""
        return {'size': _parse_size}

    def process(self, value, context=None):
        path, parameters = _split_path(value)
        result = dict.fromkeys(self.extensions())
        result['email'] = parse_reverse_path(path)
        if parameters:
            if not (context or {}).get('esmtp', False):
                raise InvalidDataError('No SMTP extensions allowed for plain SMTP.', value)
            result.update(self._parse_parameters(parameters))
        return result

    def _parse_parameters(self, parameters):
        key_value_pairs = [item.split('=', 1) for item in parameters.split()]
        if any((len(pair) != 2) for pair in key_value_pairs):
            raise InvalidDataError('Invalid arguments: "%s"' % parameters, parameters)
        extensions = self.extensions()
        result = {}
        for key, value in key_value_pairs:
            parse_value = extensions.get(key.lower())
            if parse_value is None:
                raise InvalidDataError('Invalid extension: "%s"' % parameters, parameters)
            result[key.lower()] = parse_value(value)
        return result

# ------------------------------------------------------------------------------
# RCPT TO

class RcptToSchema(SMTPCommandArgumentsSchema):

    def process(self, value, context=None):
        path, parameters = _split_path(value)
        if parameters:
            raise InvalidDataError(
                "Syntactically invalid argument(s) '%s'" % parameters, value)
        return {'email': parse_forward_path(path)}

# ------------------------------------------------------------------------------
# AUTH PLAIN/AUTH LOGIN

def _decode_base64(value):
    # "base64.b64decode()" silently ignores invalid characters
    is_base64 = re.search(r'^[A-Za-z0-9+/]*={0,2}\Z', value) and (len(value) % 4 == 0)
    if not is_base64:
        raise InvalidDataError('Garbled data sent', value)
    try:
        # RFC 4616/RFC 4954: user names and passwords are UTF-8 encoded
        return base64.b64decode(value.encode('ascii')).decode('utf-8')
    except (TypeError, ValueError):
        # binascii.Error and UnicodeDecodeError are subclasses of ValueError
        raise InvalidDataError('Garbled data sent', value)


class AuthPlainSchema(SMTPCommandArgumentsSchema):
    parameter_order = ('credentials',)

    def process(self, value, context=None):
        credentials = super(AuthPlainSchema, self).process(value, context)['credentials']
        # RFC 4616: [authzid] NUL authcid NUL passwd
        match = re.search(r'^([^\x00]*)\x00([^\x00]+)\x00([^\x00]+)\Z', credentials)
        if match is None:
            raise InvalidDataError('Garbled data sent', value)
        authzid, username, password = match.groups()
        return {'authzid': authzid or None, 'username': username, 'password': password}

    def validate_argument(self, name, value, context):
        return _decode_base64(value)


class AuthLoginSchema(SMTPCommandArgumentsSchema):
    parameter_order = ('username',)

    def validate_argument(self, name, value, context):
        return _decode_base64(value)
