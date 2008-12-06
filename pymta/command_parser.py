# -*- coding: UTF-8 -*-

import asynchat

from repoze.workflow.statemachine import StateMachine, StateMachineError

from pymta.session import SMTPSession

__all__ = ['SMTPCommandParser']


class ParserImplementation(object):
    """The SMTPCommandParser needs a connected socket to operate. This is very
    inconvenient for testing therefore all 'interesting' functionality is moved
    in this class which is easily testable."""
    
    def parse(self, command):
        assert isinstance(command, basestring)
        parameter = None
        if ':' in command:
            command, parameter = command.split(':', 1)
            parameter = parameter.strip()
        elif ' ' in command:
            command, parameter = command.split(' ', 1)
            parameter = parameter.strip()
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

    def __init__(self, server, connection, remote_ip_and_port, policy):
        self.COMMAND = 0
        self.DATA = 1
        asynchat.async_chat.__init__(self, connection)
        self.set_terminator(self.LINE_TERMINATOR)
        
        self._server = server
        self.data = None
        self._build_state_machine()
        
        self._connection = connection
        self._peer = connection.getpeername()
        self._parser = ParserImplementation()

        self.processor = SMTPSession(command_parser=self, policy=policy)
        remote_ip_string, remote_port = remote_ip_and_port
        self.processor.new_connection(remote_ip_string, remote_port)
        
        self._line = []
        self._old_state = self.COMMAND
        self._greeting = 0
        self._mailfrom = None
        self._rcpttos = []
        self._data = ''
    
    def _build_state_machine(self):
        def _command_completed(from_state, to_state, smtp_command, instance):
            self.data = None
        
        def _start_receiving_message(from_state, to_state, smtp_command, instance):
            self.set_terminator('\r\n.\r\n')
            self.data = []
        
        def _finished_receiving_message(from_state, to_state, smtp_command, instance):
            self.set_terminator('\r\n')
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
    
    def push(self, code, msg=None):
        """Send a message to the peer (using the correct SMTP line terminators
        (usually only called from the SMTPProcessor)."""
        if msg == None:
            msg = code
        else:
            msg = "%s %s" % (str(code), msg)
        
        if not msg.endswith('\r\n'):
            msg += '\r\n'
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
    
    def found_terminator(self):
        input_data = self.data
        if self._state == 'commands':
            command, parameter = self._parser.parse(input_data)
            self.processor.handle_input(command, parameter)
            if command.upper() == 'DATA':
                # TODO: check good output of handle_input
                self.state.execute(self, 'DATA')
        else:
            assert isinstance(input_data, list)
            # TODO: Remove extraneous carriage returns and de-transparency according
            # to RFC 821, Section 4.5.2.
            lines = []
            for part in input_data:
                lines.extend(part.split('\r\n'))
            parameter = '\n'.join(lines)
            self.processor.handle_input('MSGDATA', parameter)
            self.state.execute(self, 'COMMAND')
    
    
    # TODO: Rewrite!
    # factored
    def __getaddr(self, keyword, arg):
        address = None
        keylen = len(keyword)
        if arg[:keylen].upper() == keyword:
            address = arg[keylen:].strip()
            if not address:
                pass
            elif address[0] == '<' and address[-1] == '>' and address != '<>':
                # Addresses can be in the form <person@dom.com> but watch out
                # for null address, e.g. <>
                address = address[1:-1]
        return address
    
    
    def handle_close(self):
        print 'CLOSE!'
        asynchat.async_chat.handle_close(self)
    
    def close_when_done(self):
        print 'CLOSE WHEN DONE!'
        asynchat.async_chat.close_when_done(self)

    # -------------------------------------------------------------------------
    # Internal methods for sending data to the client (easy subclassing with
    # different behavior)

    # -------------------------------------------------------------------------
    # Methods that call policy checks

    def smtp_MAIL(self, arg):
        print '===> MAIL', arg
        address = self.__getaddr('FROM:', arg)
        if not address:
            self.push('501 Syntax: MAIL FROM:<address>')
            return
        if self._mailfrom:
            self.push('503 Error: nested MAIL command')
            return
        self._mailfrom = address
        print 'sender:', self._mailfrom
        self.push('250 Ok')

    def smtp_RCPT(self, arg):
        print '===> RCPT', arg
        if not self._mailfrom:
            self.push('503 Error: need MAIL command')
            return
        address = self.__getaddr('TO:', arg)
        if not address:
            self.push('501 Syntax: RCPT TO: <address>')
            return
        self._rcpttos.append(address)
        print 'recips:', self._rcpttos
        self.push('250 Ok')

    def smtp_RSET(self, arg):
        if arg:
            self.push('501 Syntax: RSET')
            return
        # Resets the sender, recipients, and data, but not the greeting
        self._mailfrom = None
        self._rcpttos = []
        self._data = ''
        self._old_state = self.COMMAND
        self.push('250 Ok')

    def smtp_DATA(self, arg):
        if not self._rcpttos:
            self.push('503 Error: need RCPT command')
            return
        if arg:
            self.push('501 Syntax: DATA')
            return
        self._old_state = self.DATA
        self.set_terminator('\r\n.\r\n')
        self.push('354 End data with <CR><LF>.<CR><LF>')


