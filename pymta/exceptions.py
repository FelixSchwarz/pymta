# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT


from pymta.api import PyMTAException


__all__ = ['InvalidParametersError', 'SMTPViolationError']


class SMTPViolationError(PyMTAException):
    """Raised when the SMTP client violated the protocol."""

    def __init__(self, response_sent=False, code=550,
                 reply_text='Administrative Prohibition', message=None):
        if message is None:
            message = '%s %s' % (code, reply_text)
        PyMTAException.__init__(self, message)
        self.response_sent = response_sent
        self.code = code
        self.reply_text = reply_text


class InvalidParametersError(SMTPViolationError):
    """The SMTP client provided invalid parameters for a SMTP command."""

    def __init__(self, parameter=None, *args, **kwargs):
        # In Python 2.3 Exception is an old-style classes so we can not use super
        SMTPViolationError.__init__(self, *args, **kwargs)
        self.parameter = parameter


