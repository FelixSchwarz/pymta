# -*- coding: UTF-8 -*-
#
# The MIT License
# 
# Copyright (c) 2008 Felix Schwarz <felix.schwarz@oss.schwarz.eu>
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

import asynchat
import re

from repoze.workflow.statemachine import StateMachine, StateMachineError

from pymta.session import SMTPSession

__all__ = ['SMTPCommandParser']


class ParserImplementation(object):
    """The SMTPCommandParser needs a connected socket to operate. This is very
    inconvenient for testing therefore all 'interesting' functionality is moved
    in this class which is easily testable."""
    
    def __init__(self, allowed_commands):
        self._allowed_commands = allowed_commands
        regex_string = '^(%s)(?: |:)\s*(.*)$' % '|'.join(allowed_commands)
        self.parse_regex = re.compile(regex_string, re.IGNORECASE)
    
    def parse(self, command):
        assert isinstance(command, basestring)
        parameter = None
        
        match = self.parse_regex.search(command)
        if match != None:
            command = match.group(1)
            parameter = match.group(2).strip()
        return command, parameter
    

class SMTPCommandParser(asynchat.async_chat):
    """This class handles only the actual communication with the client. As soon
    as a complete command is received, this class will hand everything over to
    the SMTPSession.
    
    The original 'SMTPChannel' class from Python.org handled all communication 
    with asynchat, implemented a extremly simple state machine and processed 
    the data. Implementing hooks in that design (or adding fine-grained 
    policies) was not possible at all with the previous design."""
    
    LINE_TERMINATOR = '\r\n'

    def __init__(self, server, connection, remote_ip_string, port, policy, 
                 authenticator=None):
        asynchat.async_chat.__init__(self, connection)
        self.set_terminator(self.LINE_TERMINATOR)
        
        self._server = server
        self.data = None
        self._build_state_machine()
        
        self._connection = connection

        self.session = SMTPSession(command_parser=self, policy=policy, 
                                   authenticator=authenticator)
        allowed_commands = self.session.get_all_allowed_internal_commands()
        self._parser = ParserImplementation(allowed_commands)
        self.session.new_connection(remote_ip_string, remote_port)
    
    def _build_state_machine(self):
        def _command_completed(from_state, to_state, smtp_command, instance):
            self.data = None
        
        def _start_receiving_message(from_state, to_state, smtp_command, instance):
            self.set_terminator('%s.%s' % (self.LINE_TERMINATOR, self.LINE_TERMINATOR))
            self.data = []
        
        def _finished_receiving_message(from_state, to_state, smtp_command, instance):
            self.set_terminator(self.LINE_TERMINATOR)
            self.data = None
        
        self.state = StateMachine('_state', initial_state='commands')
        self._state = 'commands'
        self.state.add('commands', 'COMMAND', 'commands', _command_completed)
        self.state.add('commands', 'DATA',    'data', _start_receiving_message)
        self.state.add('data',     'COMMAND', 'commands', _finished_receiving_message)
    
    def primary_hostname(self):
        return self._server.primary_hostname
    primary_hostname = property(primary_hostname)
    
    
    # -------------------------------------------------------------------------
    # Communication helper methods
    
    def multiline_push(self, code, lines):
        """Send a multi-message to the peer (using the correct SMTP line 
        terminators (usually only called from the SMTPSession)."""
        for i, line in enumerate(lines[:-1]):
            answer = '%s-%s' % (str(code), str(line))
            self.push(answer)
        self.push(code, lines[-1])
    
    def push(self, code, msg=None):
        """Send a message to the peer (using the correct SMTP line terminators
        (usually only called from the SMTPSession)."""
        if msg == None:
            msg = code
        else:
            msg = '%s %s' % (str(code), msg)
        
        if not msg.endswith(self.LINE_TERMINATOR):
            msg += self.LINE_TERMINATOR
        asynchat.async_chat.push(self, msg)
    
    def new_message_received(self, msg):
        """Called from the SMTPProcessor when a new message was received 
        successfully."""
        self._server.new_message_received(msg)
    
    def collect_incoming_data(self, data):
        if self._state == 'commands':
            self.data = data
        elif data != '.':
            # In DATA mode '.' on a line by itself signals the 'end of message'.
            # So the dot is only needed in protocol itself but we don't add it 
            # to our payload.
            self.data.append(data)
    
    def switch_to_command_mode(self):
        """Called from the SMTPSession when a message was received and the 
        client is expected to send single commands again."""
        self.state.execute(self, 'COMMAND')
    
    def switch_to_data_mode(self):
        """Called from the SMTPSession when the client should start transfering
        the actual message data."""
        self.state.execute(self, 'DATA')
    
    def found_terminator(self):
        input_data = self.data
        if self._state == 'commands':
            command, parameter = self._parser.parse(input_data)
            self.session.handle_input(command, parameter)
        else:
            assert isinstance(input_data, list)
            # TODO: Remove extraneous carriage returns and de-transparency according
            # to RFC 821, Section 4.5.2.
            lines = []
            for part in input_data:
                lines.extend(part.split(self.LINE_TERMINATOR))
            parameter = '\n'.join(lines)
            self.session.handle_input('MSGDATA', parameter)
    
    def handle_close(self):
        print 'CLOSE!'
        asynchat.async_chat.handle_close(self)
    
    def close_when_done(self):
        print 'CLOSE WHEN DONE!'
        asynchat.async_chat.close_when_done(self)


