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


__all__ = ['commands_for_babel_support']

def is_babel_available():
    try:
        import babel
    except ImportError:
        return False
    return True

def commands_for_babel_support():
    if not is_babel_available():
        return {}
    from babel.messages import frontend as babel
    
    extra_commands = {
        'extract_messages': babel.extract_messages,
        'init_catalog':     babel.init_catalog,
        'update_catalog':   babel.update_catalog,
        'compile_catalog':  babel.compile_catalog,
    }
    return extra_commands

def information_from_file(filename):
    data = dict()
    execfile(filename, data)
    is_exportable_symbol = lambda key: not key.startswith('_')
    externally_defined_parameters = dict([(key, value) for key, value in data.items() if is_exportable_symbol(key)])
    return externally_defined_parameters


