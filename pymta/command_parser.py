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

from Queue import Empty
import re
import socket

from repoze.workflow.statemachine import StateMachine, StateMachineError

from pymta.exceptions import SMTPViolationError
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


class SMTPCommandParser(object):
    """This class is a tiny abstraction layer above the real communication 
    with the client. It knows about the two basic SMTP modes (sending commands
    vs. sending message data) and can assemble SMTP-like replies (Code-Message)
    in a convenient manner. However all handling of SMTP commands will take 
    place in an upper layer.
    
    The original 'SMTPChannel' class from Python.org handled all communication 
    with asynchat, implemented a extremely simple state machine and processed 
    the data. Implementing hooks in that design (or adding fine-grained 
    policies) was not possible at all with the previous design."""
    
    LINE_TERMINATOR = '\r\n'

    def __init__(self, channel, remote_ip_string, remote_port, deliverer, 
                 policy=None, authenticator=None):
        self._channel = channel
        
        self.data = None
        self.terminator = self.LINE_TERMINATOR
        self._build_state_machine()
        
        self.session = SMTPSession(command_parser=self, deliverer=deliverer,
                                   policy=policy, authenticator=authenticator)
        allowed_commands = self.session.get_all_allowed_internal_commands()
        self._parser = ParserImplementation(allowed_commands)
        self.session.new_connection(remote_ip_string, remote_port)
    
    def _build_state_machine(self):
        def _command_completed(from_state, to_state, smtp_command, instance):
            self.data = None
        
        def _start_receiving_message(from_state, to_state, smtp_command, instance):
            self.terminator = '%s.%s' % (self.LINE_TERMINATOR, self.LINE_TERMINATOR)
            self.data = []
        
        def _finished_receiving_message(from_state, to_state, smtp_command, instance):
            self.terminator = self.LINE_TERMINATOR
            self.data = None
        
        self.state = StateMachine('_state', initial_state='commands')
        self._state = 'commands'
        self.state.add('commands', 'COMMAND', 'commands', _command_completed)
        self.state.add('commands', 'DATA',    'data', _start_receiving_message)
        self.state.add('data',     'COMMAND', 'commands', _finished_receiving_message)
    
    def primary_hostname(self):
        # TODO: This should go into a config object!
        return socket.getfqdn()
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
        self._channel.write(msg)
    
    def collect_incoming_data(self, data):
        if self._state == 'commands':
            self.data = data
        elif data != '.':
            # In DATA mode '.' on a line by itself signals the 'end of message'.
            # So the dot is only needed in protocol itself but we don't add it 
            # to our payload.
            self.data.append(data)
    
    def input_exceeds_limits(self):
        """Called from the underlying transport layer if the client input 
        exceeded the configured maximum message size."""
        self.session.input_exceeds_limits()
        self.switch_to_command_mode()
    
    def set_maximum_message_size(self, max_size):
        """Set the maximum allowed size (in bytes) of a command/message in the
        underlying transport layer so that big messages are not stored in memory
        before they are rejected."""
        self._channel.set_max_input_size(max_size)
    
    def switch_to_command_mode(self):
        """Called from the SMTPSession when a message was received and the 
        client is expected to send single commands again."""
        self.state.execute(self, 'COMMAND')
    
    def switch_to_data_mode(self):
        """Called from the SMTPSession when the client should start transfering
        the actual message data."""
        self.state.execute(self, 'DATA')
    
    def _assemble_msgdata(self, input_data):
        """Uses the input data to recover the original payload (includes 
        transparency support as specified in RFC 821, Section 4.5.2)."""
        lines = []
        for part in input_data:
            for line in part.split(self.LINE_TERMINATOR):
                if line.startswith('.'):
                    line = line[1:]
                lines.append(line)
        return '\n'.join(lines)
    
    def get_terminator(self):
        return self._terminator
    
    def set_terminator(self, terminator):
        self._terminator = terminator
    terminator = property(get_terminator, set_terminator)
    
    def found_terminator(self):
        input_data = self.data
        if self._state == 'commands':
            command, parameter = self._parser.parse(input_data)
            self.session.handle_input(command, parameter)
        else:
            assert isinstance(input_data, list)
            msgdata = self._assemble_msgdata(input_data)
            self.session.handle_input('MSGDATA', msgdata)
    
    def close_when_done(self):
        self._channel.close()


class ClientDisconnectedError(SMTPViolationError):
    """Raised when the SMTP client closed the connection unexpectedly."""
    pass


class WorkerProcess(object):
    """The WorkerProcess handles the real communication. with the client. It 
    does not know anything about the SMTP protocol (besides the fact that it is
    a line-based protocol)."""
    
    def __init__(self, queue, server_socket, deliverer_class, policy_class=None,
                 authenticator_class=None):
        self._queue = queue
        self._server_socket = server_socket
        self._deliverer = self._get_instance_from_class(deliverer_class)
        self._policy = self._get_instance_from_class(policy_class)
        self._authenticator = self._get_instance_from_class(authenticator_class)
        
        self._connection = None
        self._chatter = None
        self._max_size = None
        self._input_too_big = False
    
    def _get_instance_from_class(self, class_reference):
        instance = None
        if class_reference != None:
            instance = class_reference()
        return instance
    
    def _wait_for_connection(self):
        while True:
            # We want to check periodically if we need to abort
            try:
                connection, remote_address = self._server_socket.accept()
                break
            except socket.timeout:
                try:
                    new_token = self._queue.get_nowait()
                    self._queue.put(new_token)
                    if new_token == None:
                        return None
                except Empty:
                    pass
        connection.settimeout(socket.getdefaulttimeout())
        return connection, remote_address
    
    def _get_token_with_timeout(self, seconds):
        # wait at max 1 second for the token so that we can abort the whole
        # process in a reasonable time
        token = None
        while True:
            try:
                token = self._queue.get(timeout=seconds)
                break
            except Empty:
                pass
        return token
    
    def run(self):
        token = None
        def have_token():
            return (token != None)
        
        try:
            while True:
                token = self._get_token_with_timeout(1)
                if not have_token():
                    break
                assert token == True
                
                connection_info = self._wait_for_connection()
                self._queue.put(token)
                token = None
                if connection_info == None:
                    break
                self.chat_with_peer(connection_info)
        finally:
            if have_token():
                # If we possess the token, put it back in the queue so other can
                # continue doing stuff.
                self._queue.put(True)
    
    def set_max_input_size(self, max_size):
        """Set the maximum size of client input (in bytes) before the input is
        discarded. When the client finished transmitting a message which was
        too big, the 'input_exceeds_limits' method is called on the chatter 
        which is responsible for notifying the peer.
        Setting a maximum size of None disables any size-checking."""
        self._max_size = max_size
    
    def chat_with_peer(self, connection_info):
        self._connection, (remote_ip_string, remote_port) = connection_info
        self._chatter = SMTPCommandParser(self, remote_ip_string, remote_port, 
                            self._deliverer, self._policy, self._authenticator)
        while self.is_connected():
            try:
                data = self.readline()
                if not self._input_too_big:
                    self._chatter.collect_incoming_data(data)
                    self._chatter.found_terminator()
                else:
                    self._chatter.input_exceeds_limits()
                    self._input_too_big = False
            except ClientDisconnectedError:
                if self.is_connected():
                    self._connection.close()
                    self._connection = None
    
    def is_connected(self):
        return (self._connection != None)
    
    def readline(self):
        """Read as much data as possible until a line terminator was 
        received."""
        assert self.is_connected()
        data = ''
        self._input_too_big = False
        while True:
            try:
                more_data = self._connection.recv(4096)
            except socket.error:
                raise ClientDisconnectedError()
            if more_data == '':
                raise ClientDisconnectedError()
            elif more_data.endswith(self._chatter.terminator):
                data += more_data[:-len(self._chatter.terminator)]
                break
            elif not self._input_too_big:
                data += more_data
            if (self._max_size is not None) and (len(data) > self._max_size):
                self._input_too_big = True
                data = ''
        return data
    
    def close(self):
        """Closes the connection to the client."""
        assert self.is_connected()
        self._connection.close()
        self._connection = None
    
    def write(self, data):
        """Sends some data to the client."""
        assert self.is_connected()
        self._connection.send(data)

