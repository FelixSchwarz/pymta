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


class PyMTAException(Exception):
    pass

class InvalidParametersException(PyMTAException):
    pass

class PolicyDenial(PyMTAException):
    def __init__(self, response_sent, code=550, reply_text='Administrative Prohibition'):
        self.response_sent = response_sent
        self.code = code
        self.reply_text = reply_text


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
    
    def _get_all_real_states(self, including_quit=False):
        states = Set()
        for key in self.state.states:
            command_name = key[1]
            new_state = self.state.states[key]
            state_name = new_state[0]
            if state_name not in ['new']:
                if including_quit or (state_name != 'finished'):
                    states.add((command_name, state_name))
        return states
    
    def _add_rset_transitions(self):
        for command_name, state_name in self._get_all_real_states():
            if state_name == 'new':
                print command_name, 'RSET ', state_name
                self._add_state(state_name, 'RSET',  state_name)
            else:
                self._add_state(state_name, 'RSET',  'identify')
    
    def _add_help_noop_and_quit_transitions(self):
        """HELP, NOOP and QUIT should be possible from everywhere so we 
        need to add these transitions to all states configured so far."""
        states = Set()
        for key in self.state.states:
            new_state = self.state.states[key]
            state_name = new_state[0]
            if state_name not in ['new', 'finished']:
                states.add(state_name)
        for state in states:
            self._add_state(state, 'NOOP',  state)
            self._add_state(state, 'HELP',  state)
            self._add_state(state, 'QUIT',  'finished')
    
    
    def _build_state_machine(self):
        # This will implicitely declare an instance variable '_state' with the
        # initial state
        self.state = StateMachine('_state', initial_state='new')
        self._add_state('new',     'GREET', 'greeted')
        self._add_state('greeted', 'HELO',  'identify')
        self._add_state('identify', 'MAIL FROM',  'sender_known')
        self._add_state('sender_known', 'RCPT TO',  'recipient_known')
        # multiple recipients
        self._add_state('recipient_known', 'RCPT TO',  'recipient_known')
        self._add_state('recipient_known', 'DATA',  'receiving_message')
        self._add_state('receiving_message', 'MSGDATA',  'identify')
        self._add_help_noop_and_quit_transitions()
        self._add_rset_transitions()
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
    
    def _evaluate_decision(self, decision):
        return (decision in [True, None])
    
    def is_allowed(self, acl_name, *args):
        if self._policy != None:
            decider = getattr(self._policy, acl_name)
            result = decider(*args)
            if result in [True, False, None]:
                return self._evaluate_decision(result), False
            elif len(result) == 2:
                decision = self._evaluate_decision(result[0])
                code, custom_response = result[1]
                if not isinstance(custom_response, basestring):
                    self.reply(code, custom_response)
                else:
                    self.multiline_reply(code, custom_response)
                return decision, True
            raise ValueError('Unknown policy response')
        return True, False
    
    # -------------------------------------------------------------------------
    
    def new_connection(self, remote_ip, remote_port):
        """This method is called when a new SMTP session is opened.
        [PUBLIC API]
        """
        self._state = 'new'
        self._message = Message(Peer(remote_ip, remote_port))
        
        decision, response_sent = self.is_allowed('accept_new_connection', 
                                                  self._message.peer)
        if decision:
            if not response_sent:
                self.handle_input('greet')
        else:
            if not response_sent:
                self.reply(554, 'SMTP service not available')
            self.close_connection()
    
    
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
        except PolicyDenial, e:
            if not e.response_sent:
                self.reply(e.code, e.reply_text)
        self._command_arguments = None
    
    
    def reply(self, code, text):
        """This method returns a message to the client (actually the session 
        object is responsible of actually pushing the bits)."""
        print 'code, text', code, text
        self._command_parser.push(code, text)
    
    
    def multiline_reply(self, code, responses):
        """This method returns a message with multiple lines to the client 
        (actually the session object is responsible of actually pushing the 
        bits)."""
        self._command_parser.multiline_push(code, responses)
    
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
        # Policy check was done when accepting the connection so we don't have 
        # to do it here again.
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
    
    def smtp_help(self):
        states = Set()
        for command_name, invalid in self._get_all_real_states(including_quit=True):
            if command_name not in ['GREET', 'MSGDATA']:
                command_name = command_name.split(' ')[0]
                states.add(command_name)
        self.multiline_reply(214, (('Commands supported'), ' '.join(states)))
    
    def smtp_helo(self):
        helo_string = (self._command_arguments or '').strip()
        valid_hostname_syntax = (self.hostname_regex.match(helo_string) != None)
        if not valid_hostname_syntax:
            raise InvalidParametersException(helo_string)
        else:
            decision, response_sent = self.is_allowed('accept_helo', helo_string, self._message)
            if decision:
                self._message.smtp_helo = helo_string
                if not response_sent:
                    primary_hostname = self._command_parser.primary_hostname
                    self.reply(250, primary_hostname)
            elif not decision:
                raise PolicyDenial(response_sent)
    
    def smtp_mail_from(self):
        sender = self._command_arguments
        # TODO: Check for good email address!
        # TODO: Check for single email address!
        decision, response_sent = self.is_allowed('accept_from', sender, self._message)
        if decision:
            self._message.smtp_from = sender
            if not response_sent:
                self.reply(250, 'OK')
        elif not decision:
            raise PolicyDenial(response_sent)
    
    def _extract_email_address(self, parameter):
        match = re.search('^<?(.*?)>?$', parameter)
        if match:
            return match.group(1)
        raise InvalidParametersException(parameter)
    
    def smtp_rcpt_to(self):
        # TODO: Check for good email address!
        
        email_address = self._extract_email_address(self._command_arguments)
        decision, response_sent = self.is_allowed('accept_rcpt_to', email_address, self._message)
        if decision:
            self._message.smtp_to.append(email_address)
            if not response_sent:
                self.reply(250, 'OK')
        elif not decision:
            raise PolicyDenial(response_sent, 550, 'relay not permitted')
    
    def smtp_data(self):
        # TODO: Check no arguments
        decision, response_sent = self.is_allowed('accept_data', self._message)
        if decision and not response_sent:
            self._command_parser.switch_to_data_mode()
            self.reply(354, 'Enter message, ending with "." on a line by itself')
        elif not decision:
            raise PolicyDenial(response_sent)
    
    def smtp_msgdata(self):
        """This method handles not a real smtp command. It is called when the
        whole message was received (multi-line DATA command is completed)."""
        msg_data = self._command_arguments
        self._command_parser.switch_to_command_mode()
        decision, response_sent = self.is_allowed('accept_msgdata', msg_data, self._message)
        if decision:
            self._message.msg_data = msg_data
            self._command_parser.new_message_received(self._message)
            self._message = None
            if not response_sent:
                self.reply(250, 'OK')
                # Now we must not loose the message anymore!
        elif not decision:
            raise PolicyDenial(response_sent, 550, 'Message content is not acceptable')
    
    def smtp_rset(self):
        self._message = Message(peer=self._message.peer, 
                                smtp_helo=self._message.smtp_helo)
        self.reply(250, 'Reset OK')
    

