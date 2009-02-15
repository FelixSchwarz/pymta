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

import base64
import binascii
import re
try:
    set
except NameError:
    from sets import Set as set

from repoze.workflow.statemachine import StateMachine, StateMachineError

from pymta.model import Message, Peer


__all__ = ['SMTPSession']


# regular expression deliberately taken from
# http://stackoverflow.com/questions/106179/regular-expression-to-match-hostname-or-ip-address#106223
regex_string = r'^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z]|[A-Za-z][A-Za-z0-9\-]*[A-Za-z0-9])$'


class PyMTAException(Exception):
    def __init__(self, response_sent=False, code=550, 
                 reply_text='Administrative Prohibition'):
        self.response_sent = response_sent
        self.code = code
        self.reply_text = reply_text

class DynamicStateSwitchException(PyMTAException):
    """Used to implement more complicated state transitions where the next 
    state depends on other values (e.g. where to go after a message was 
    received - depends on ESMTP and AUTH)."""
    def __init__(self, new_state):
        self.new_state = new_state

class InvalidParametersException(PyMTAException):
    def __init__(self, parameter=None, *args, **kwargs):
        self.parameter = parameter
        super(InvalidParametersException, self).__init__(*args, **kwargs)

class PolicyDenial(PyMTAException):
    pass


class SMTPSession(object):
    """The SMTPSession processes all input data which were extracted from 
    sockets previously. The idea behind this is that this class only knows about
    different SMTP commands and does not have to know things like command mode
    and data mode.
    
    The protocol parser will create a new session instance for every new 
    connection so this class does not have to be thread-safe.
    """
    
    def __init__(self, command_parser, deliverer, policy=None, 
                 authenticator=None):
        self._command_parser = command_parser
        self._deliverer = deliverer
        self._policy = policy
        self._authenticator = authenticator
        
        self._command_arguments = None
        self._message = None
        
        self.hostname_regex = re.compile(regex_string, re.IGNORECASE)
        self._build_state_machine()
    
    # -------------------------------------------------------------------------
    # State machine building
    
    def _add_state(self, from_state, smtp_command, to_state):
        handler_function = self._dispatch_commands
        self.state.add(from_state, smtp_command, to_state, handler_function)
    
    def _get_all_real_states(self, including_quit=False):
        states = set()
        for key in self.state.states:
            command_name = key[1]
            new_state = self.state.states[key]
            state_name = new_state[0]
            if state_name not in ['new']:
                if including_quit or (state_name != 'finished'):
                    states.add((command_name, state_name))
        return states
    
    def get_all_allowed_internal_commands(self):
        """Returns an iterable which includes all allowed commands. This does
        not mean that a specific command from the result is executable right now
        in this session state (or that it can be executed at all in this 
        connection).
        
        Please note that the returned values are /internal/ commands, not SMTP
        commands (use get_all_allowed_smtp_commands for that) so there will be
        'MAIL FROM' instead of 'MAIL'."""
        states = set()
        for command_name, invalid in self._get_all_real_states(including_quit=True):
            if command_name not in ['GREET', 'MSGDATA']:
                states.add(command_name)
        return states
    
    def get_all_allowed_smtp_commands(self):
        states = set()
        for command_name in self.get_all_allowed_internal_commands():
            command_name = command_name.split(' ')[0]
            states.add(command_name)
        return states
    
    def _add_rset_transitions(self):
        for command_name, state_name in self._get_all_real_states():
            if state_name == 'new':
                self._add_state(state_name, 'RSET',  state_name)
            else:
                self._add_state(state_name, 'RSET',  'initialized')
    
    def _add_help_noop_and_quit_transitions(self):
        """HELP, NOOP and QUIT should be possible from everywhere so we 
        need to add these transitions to all states configured so far."""
        states = set()
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
        self.state = StateMachine('_state', initial_state='new')
        self._add_state('new',     'GREET', 'greeted')
        self._add_state('greeted', 'HELO',  'initialized')
        
        self._add_state('greeted', 'EHLO',  'esmtp_initialized')
        
        # ----
        self._add_state('initialized', 'MAIL FROM',  'sender_known')
        self._add_state('esmtp_initialized', 'MAIL FROM',  'sender_known')
        
        self._add_state('esmtp_initialized', 'AUTH PLAIN', 'authenticated')
        self._add_state('authenticated', 'MAIL FROM',  'sender_known')
        # ----
        
        self._add_state('sender_known', 'RCPT TO',  'recipient_known')
        # multiple recipients
        self._add_state('recipient_known', 'RCPT TO',  'recipient_known')
        self._add_state('recipient_known', 'DATA',  'receiving_message')
        self._add_state('receiving_message', 'MSGDATA',  'initialized')
        self._add_help_noop_and_quit_transitions()
        self._add_rset_transitions()
        self.valid_commands = [command for from_state, command in self.state.states]
    
    # -------------------------------------------------------------------------
    
    def get_ehlo_lines(self):
        """Return the capabilities to be advertised after EHLO."""
        lines = []
        if self._authenticator != None:
            # TODO: Make the authentication pluggable but separate mechanism 
            # from user look-up.
            lines.append('AUTH PLAIN')
        if self._policy != None:
            lines.extend(self._policy.ehlo_lines(self._message.peer))
        lines.append('HELP')
        return lines
    
    def _set_size_restrictions(self):
        """Set the maximum allowed message in the underlying layer so that big 
        messages are not hold in memory before they are rejected."""
        max_message_size = self._get_max_message_size_from_policy()
        self._command_parser.set_maximum_message_size(max_message_size)
    
    def _dispatch_commands(self, from_state, to_state, smtp_command, ob):
        """This method dispatches a SMTP command to the appropriate handler 
        method. It is called after a new command was received and a valid 
        transition was found."""
        #print from_state, ' -> ', to_state, ':', smtp_command
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
            self._set_size_restrictions()
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
        except InvalidParametersException, e:
            if not e.response_sent:
                msg = 'Syntactically invalid %s argument(s)' % smtp_command
                self.reply(501, msg)
        except PolicyDenial, e:
            if not e.response_sent:
                self.reply(e.code, e.reply_text)
        self._command_arguments = None
    
    def input_exceeds_limits(self):
        """Called when the client sent a message that exceeded the maximum 
        size."""
        self.reply(552, 'message exceeds fixed maximum message size')
    
    def reply(self, code, text):
        """This method returns a message to the client (actually the session 
        object is responsible of actually pushing the bits)."""
        #print 'code, text', code, text
        self._command_parser.push(code, text)
    
    
    def multiline_reply(self, code, responses):
        """This method returns a message with multiple lines to the client 
        (actually the session object is responsible of actually pushing the 
        bits)."""
        self._command_parser.multiline_push(code, responses)
    
    def close_connection(self):
        "Request a connection close from the SMTP session handling instance."
        self._command_parser.close_when_done()
    
    
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
        states = self.get_all_allowed_smtp_commands()
        self.multiline_reply(214, (('Commands supported'), ' '.join(states)))
    
    def _reply_to_helo(self, helo_string, response_sent):
        self._message.smtp_helo = helo_string
        if not response_sent:
            primary_hostname = self._command_parser.primary_hostname
            self.reply(250, primary_hostname)
    
    def _process_helo_or_ehlo(self, policy_methodname, reply_method):
        helo_string = (self._command_arguments or '').strip()
        valid_hostname_syntax = (self.hostname_regex.match(helo_string) != None)
        if not valid_hostname_syntax:
            raise InvalidParametersException(helo_string)
        else:
            decision, response_sent = self.is_allowed(policy_methodname, helo_string, self._message)
            if decision:
                reply_method(helo_string, response_sent)
            elif not decision:
                raise PolicyDenial(response_sent)
    
    def smtp_helo(self):
        self._process_helo_or_ehlo('accept_helo', self._reply_to_helo)
    
    def _reply_to_ehlo(self, helo_string, response_sent):
        self._message.smtp_helo = helo_string
        if not response_sent:
            primary_hostname = self._command_parser.primary_hostname
            lines = [primary_hostname] + self.get_ehlo_lines()
            self.multiline_reply(250, lines)
    
    def smtp_ehlo(self):
        self._process_helo_or_ehlo('accept_ehlo', self._reply_to_ehlo)
    
    def _check_password(self, username, password):
        decision, response_sent = self.is_allowed('accept_auth_plain', username, password, self._message)
        if not decision:
            raise PolicyDenial(response_sent)
        assert response_sent == False
        if self._authenticator == None:
            self.reply(535, 'AUTH not available')
            raise InvalidParametersException(response_sent=True)
        credentials_correct = \
            self._authenticator.authenticate(username, password, self._message.peer)
        if credentials_correct:
            self._message.username = username
            self.reply(235, 'Authentication successful')
        else:
            self.reply(535, 'Bad username or password')
    
    def smtp_auth_plain(self):
        base64_credentials = self._command_arguments
        try:
            credentials = base64.decodestring(base64_credentials)
        except binascii.Error:
            raise InvalidParametersException(base64_credentials)
        else:
            match = re.search('^\x00([^\x00]*)\x00([^\x00]*)$', credentials)
            if match:
                username, password = match.group(1), match.group(2)
                self._check_password(username, password)
            else:
                raise InvalidParametersException(credentials)
    
    def _split_mail_from_parameter(self, data):
        sender = data
        extensions = {}
        
        # TODO: case insensitivity of extension names
        verb_regex = re.compile('^\s*<(.*)>(?:\s*(\S+)\s*)*\s*$')
        match = verb_regex.search(data)
        if match:
            sender = match.group(1)
            extension_string = match.group(2)
            if extension_string is not None:
                for extension in re.split('\s+', extension_string):
                    if '=' in extension:
                        name, parameter = extension.split('=', 1)
                        extensions[name] = parameter
                    else:
                        extensions[extension] = True
        return (sender, extensions)
    
    def _check_mail_extensions(self, extensions):
        if 'size' in extensions:
            # TODO: protect against non-numeric size!
            announced_size = int(extensions['size'])
            max_message_size = self._get_max_message_size_from_policy()
            if max_message_size != None:
                if announced_size > max_message_size:
                    self.reply(552, 'message exceeds fixed maximum message size')
                    raise InvalidParametersException('MAIL FROM', response_sent=True)
    
    def smtp_mail_from(self):
        data = self._command_arguments
        sender, extensions = self._split_mail_from_parameter(data)
        # TODO: Check for good email address!
        # TODO: Check for single email address!
        uses_esmtp = (self._state in ['esmtp_initialized', 'authenticated'])
        if uses_esmtp:
            self._check_mail_extensions(extensions)
        elif len(extensions) > 0:
            self.reply(501, 'No SMTP extensions allowed for plain SMTP')
            raise InvalidParametersException('MAIL', response_sent=True)
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
    
    def _get_max_message_size_from_policy(self):
        max_message_size = None
        if (self._policy is not None) and (self._message.peer is not None):
            max_message_size = self._policy.max_message_size(self._message.peer)
        return max_message_size
    
    def _check_size_restrictions(self, msg_data):
        max_message_size = self._get_max_message_size_from_policy()
        if (max_message_size is not None):
            msg_too_big = (len(msg_data) > int(max_message_size))
            if msg_too_big:
                msg = 'message exceeds fixed maximum message size'
                raise PolicyDenial(False, 552, msg)
    
    def _copy_basic_settings(self, msg):
        peer = self._message.peer
        new_message = Message(peer=Peer(peer.remote_ip, peer.remote_port), 
                              smtp_helo=self._message.smtp_helo,
                              username=self._message.username)
        return new_message
    
    def smtp_msgdata(self):
        """This method handles not a real smtp command. It is called when the
        whole message was received (multi-line DATA command is completed)."""
        msg_data = self._command_arguments
        self._command_parser.switch_to_command_mode()
        self._check_size_restrictions(msg_data)
        decision, response_sent = self.is_allowed('accept_msgdata', msg_data, self._message)
        if decision:
            self._message.msg_data = msg_data
            new_message = self._copy_basic_settings(self._message)
            self._deliverer.new_message_accepted(self._message)
            if not response_sent:
                self.reply(250, 'OK')
                # Now we must not loose the message anymore!
            self._message = new_message
        elif not decision:
            raise PolicyDenial(response_sent, 550, 'Message content is not acceptable')
    
    def smtp_rset(self):
        self._message = Message(peer=self._message.peer, 
                                smtp_helo=self._message.smtp_helo)
        self.reply(250, 'Reset OK')
    

