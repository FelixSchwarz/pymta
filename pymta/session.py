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

import re
from sets import Set

from repoze.workflow.statemachine import StateMachine, StateMachineError

from pymta.model import Message, Peer


__all__ = ['SMTPSession']


# regular expression deliberately taken from
# http://stackoverflow.com/questions/106179/regular-expression-to-match-hostname-or-ip-address#106223
regex_string = r'^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z]|[A-Za-z][A-Za-z0-9\-]*[A-Za-z0-9])$'


class InvalidParametersException(Exception):
    pass


class SMTPSession(object):
    """The SMTPSession processes all input data which were extracted from 
    sockets previously. The idea behind is that this class is decoupled from 
    asynchat as much as possible and make it really testable.
    
    The protocol parser will create a new session instance for every new 
    connection so this class does not have to be thread-safe.
    """
    
    def __init__(self, command_parser, policy=None):
        self._command_parser = command_parser
        self._policy = policy
        
        self._command_arguments = None
        self._message = None
        
        self.hostname_regex = re.compile(regex_string, re.IGNORECASE)
        self._build_state_machine()
        
    
    # -------------------------------------------------------------------------
    
    def _add_state(self, from_state, smtp_command, to_state):
        handler_function = self._dispatch_commands
        self.state.add(from_state, smtp_command, to_state, handler_function)
    
    
    def _add_noop_and_quit_transitions(self):
        """NOOP and QUIT should be possible from everywhere so we need to add 
        these transitions to all states configured so far."""
        states = Set()
        for key in self.state.states:
            new_state = self.state.states[key]
            state_name = new_state[0]
            if state_name not in ['new', 'finished']:
                states.add(state_name)
        for state in states:
            self._add_state(state, 'NOOP',  state)
            self._add_state(state, 'QUIT',  'finished')
        
    
    def _build_state_machine(self):
        # This will implicitely declare an instance variable '_state' with the
        # initial state
        self.state = StateMachine('_state', initial_state='new')
        self._add_state('new',     'GREET', 'greeted')
        self._add_state('greeted', 'HELO',  'identify')
        self._add_state('identify', 'MAIL FROM',  'sender_known')
        self._add_state('sender_known', 'RCPT TO',  'recipient_known')
        self._add_state('recipient_known', 'DATA',  'receiving_message')
        self._add_state('receiving_message', 'MSGDATA',  'identify')
        self._add_noop_and_quit_transitions()
        self.valid_commands = [command for from_state, command in self.state.states]
    
    
    def _dispatch_commands(self, from_state, to_state, smtp_command, ob):
        """This method dispatches a SMTP command to the appropriate handler 
        method. It is called after a new command was received and a valid 
        transition was found."""
        print from_state, ' -> ', to_state, ':', smtp_command
        name_handler_method = 'smtp_%s' % smtp_command.lower().replace(' ', '_')
        try:
            handler_method = getattr(self, name_handler_method)
        except AttributeError:
            base_msg = 'No handler for %s though transition is defined (no method %s)'
            print base_msg % (smtp_command, name_handler_method)
            self.reply(451, 'Temporary Local Problem: Please come back later')
        else:
            # Don't catch InvalidParametersException here - else the state would
            # be moved forward. Instead the handle_input will catch it and send
            # out the appropriate reply.
            handler_method()
            
    
    # -------------------------------------------------------------------------
    
    def new_connection(self, remote_ip, remote_port):
        """This method is called when a new SMTP session is opened.
        [PUBLIC API]
        """
        self._state = 'new'
        self._message = Message(Peer(remote_ip, remote_port))
        
        if False and (self._policy != None): # and \
#            (not self._policy.accept_new_connection(self.remote_ip_string, self.remote_port)):
            self.reply(554, 'SMTP service not available')
            self.close_connection()
        else:
            self.handle_input('greet')
    
    
    def handle_input(self, smtp_command, data=None):
        """Processes the given SMTP command with the (optional data).
        [PUBLIC API]
        """
        self._command_arguments = data
        command = smtp_command.upper()
        try:
            # SMTP commands must be treated as case-insensitive
            self.state.execute(self, command)
        except StateMachineError:
            if command not in self.valid_commands:
                self.reply(500, 'unrecognized command "%s"' % smtp_command)
            else:
                msg = 'Command "%s" is not allowed here' % smtp_command
                allowed_transitions = self.state.transitions(self)
                if len(allowed_transitions) > 0:
                      msg += ', expected on of %s' % allowed_transitions
                self.reply(503, msg)
        except InvalidParametersException:
            self.reply(501, 'Syntactically invalid %s argument(s)' % smtp_command)
        self._command_arguments = None
    
    
    def reply(self, code, text):
        """This method returns a message to the client (actually the session 
        object is responsible of actually pushing the bits)."""
        print 'code, text', code, text
        self._command_parser.push(code, text)
    
    
    def close_connection(self):
        "Request a connection close from the SMTP session handling instance."
        self._command_parser.close_when_done()
        self.remote_ip_string = None
        self.remote_port = None
    
    
    # -------------------------------------------------------------------------
    # Protocol handling functions (not public)
    
    def smtp_greet(self):
        """This method handles not a real smtp command. It is called when a new
        connection was accepted by the server."""
        primary_hostname = self._command_parser.primary_hostname
        reply_text = '%s Hello %s' % (primary_hostname, self._message.peer.remote_ip)
        self.reply(220, reply_text)
    
    def smtp_quit(self):
        primary_hostname = self._command_parser.primary_hostname
        reply_text = '%s closing connection' % primary_hostname
        self.reply(221, reply_text)
        self._command_parser.close_when_done()
    
    def smtp_noop(self):
        self.reply(250, 'OK')
    
    def smtp_helo(self):
        helo_string = (self._command_arguments or '').strip()
        valid_hostname_syntax = (self.hostname_regex.match(helo_string) != None)
        if not valid_hostname_syntax:
            raise InvalidParametersException(helo_string)
        else:
            self._message.smtp_helo = helo_string
            primary_hostname = self._command_parser.primary_hostname
            self.reply(250, primary_hostname)
    
    def smtp_mail_from(self):
        # TODO: Check for good email address!
        # TODO: Check for single email address!
        # TODO: Policy
        self._message.smtp_from = self._command_arguments
        self.reply(250, 'OK')
    
    def smtp_rcpt_to(self):
        # TODO: Check for good email address!
        # TODO: Handle multiple arguments
        # TODO: Policy
        self._message.smtp_to = self._command_arguments
        self.reply(250, 'OK')
    
    def smtp_data(self):
        # TODO: Policy check
        # TODO: Check no arguments
        self.reply(354, 'Enter message, ending with "." on a line by itself')
    
    def smtp_msgdata(self):
        """This method handles not a real smtp command. It is called when the
        whole message was received (multi-line DATA command is completed)."""
        msg_data = self._command_arguments
        # TODO: Policy check
        self._message.msg_data = msg_data
        self._command_parser.new_message_received(self._message)
        self._message = None
        self.reply(250, 'OK')
        # Now we must not loose the message anymore!
    

