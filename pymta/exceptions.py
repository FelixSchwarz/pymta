# -*- coding: UTF-8 -*-
#
# The MIT License
# 
# Copyright (c) 2008-2009 Felix Schwarz <felix.schwarz@oss.schwarz.eu>
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


