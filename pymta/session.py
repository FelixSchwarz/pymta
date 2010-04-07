# -*- coding: UTF-8 -*-
#
# The MIT License
# 
# Copyright (c) 2008-2010 Felix Schwarz <felix.schwarz@oss.schwarz.eu>
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

from pycerberus import InvalidDataError

from pymta.compat import set
from pymta.exceptions import InvalidParametersError, SMTPViolationError
from pymta.model import Message, Peer
from pymta.statemachine import StateMachine, StateMachineError
from pymta.validation import AuthPlainSchema, HeloSchema, MailFromSchema, \
    RcptToSchema, SMTPCommandArgumentsSchema


__all__ = ['SMTPSession']



class PolicyDenial(SMTPViolationError):
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
        self._close_connection_after_response = False
        self._is_connected = True
        self._message = None
        
        self._build_state_machine()
    
    # -------------------------------------------------------------------------
    # State machine building
    
    def _add_state(self, from_state, to_state, smtp_command, **kwargs):
        handler_function = self._dispatch_commands
        self.state.add(from_state, smtp_command, to_state, handler_function, **kwargs)
    
    def _get_all_commands(self, including_quit=False):
        commands = set()
        for actions in self.state._transitions.values():
            for command_name, transition in actions.items():
                target_state = transition[0]
                if target_state in ['new']:
                    continue
                if including_quit or (target_state != 'finished'):
                    commands.add(command_name)
        return commands
    
    def get_all_allowed_internal_commands(self):
        """Returns an iterable which includes all allowed commands. This does
        not mean that a specific command from the result is executable right now
        in this session state (or that it can be executed at all in this 
        connection).
        
        Please note that the returned values are /internal/ commands, not SMTP
        commands (use get_all_allowed_smtp_commands for that) so there will be
        'MAIL FROM' instead of 'MAIL'."""
        states = set()
        for command_name in self._get_all_commands(including_quit=True):
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
        for state_name in self.state.known_non_final_states():
            if state_name == 'new':
                self._add_state(state_name, 'RSET',  state_name)
            else:
                self._add_state(state_name, 'RSET',  'initialized')
    
    def _add_help_noop_and_quit_transitions(self):
        """HELP, NOOP and QUIT should be possible from everywhere so we 
        need to add these transitions to all states configured so far."""
        states = set()
        for state_name in self.state.known_states():
            if state_name not in ['new', 'finished']:
                states.add(state_name)
        for state in states:
            self._add_state(state, 'NOOP',  state)
            self._add_state(state, 'HELP',  state)
            self._add_state(state, 'QUIT',  'finished')
    
    def _build_state_machine(self):
        self.state = StateMachine(initial_state='new')
        self._add_state('new',     'GREET', 'greeted')
        self._add_state('greeted', 'HELO',  'initialized')
        
        self._add_state('greeted', 'EHLO',  'initialized', operations=('set_esmtp',))
        
        # ----
        self._add_state('initialized', 'MAIL FROM',  'sender_known')
        
        self._add_state('initialized', 'AUTH PLAIN', 'authenticated', condition='if_esmtp')
        self._add_state('authenticated', 'MAIL FROM',  'sender_known')
        # ----
        
        self._add_state('sender_known', 'RCPT TO',  'recipient_known')
        # multiple recipients
        self._add_state('recipient_known', 'RCPT TO',  'recipient_known')
        self._add_state('recipient_known', 'DATA',  'receiving_message')
        self._add_state('receiving_message', 'MSGDATA',  'initialized')
        self._add_help_noop_and_quit_transitions()
        self._add_rset_transitions()
        self.valid_commands = self.state.known_actions()
    
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
        self._command_parser.set_maximum_message_size(self._max_message_size())
    
    def _dispatch_commands(self, from_state, to_state, smtp_command):
        """This method dispatches a SMTP command to the appropriate handler 
        method. It is called after a new command was received and a valid 
        transition was found."""
        #print from_state, ' -> ', to_state, ':', smtp_command
        name_handler_method = 'smtp_%s' % smtp_command.lower().replace(' ', '_')
        try:
            handler_method = getattr(self, name_handler_method)
        except AttributeError:
            # base_msg = 'No handler for %s though transition is defined (no method %s)'
            # print base_msg % (smtp_command, name_handler_method)
            self.reply(451, 'Temporary Local Problem: Please come back later')
        else:
            # Don't catch InvalidDataError here - else the state would be moved 
            # forward. Instead the handle_input will catch it and send out the 
            # appropriate reply.
            handler_method()
    
    def _evaluate_decision(self, decision):
        return (decision in [True, None])
    
    def _is_multiline_reply(self, reply_message):
        return (not isinstance(reply_message, basestring))
    
    def _send_custom_response(self, reply):
        code, custom_response = reply
        if self._is_multiline_reply(custom_response):
            self.multiline_reply(code, custom_response)
        else:
            self.reply(code, custom_response)
    
    def _evaluate_policydecision_result(self, result):
        decision = self._evaluate_decision(result.is_command_acceptable())
        response_sent = result.use_custom_reply()
        if result.close_connection_before_response():
            self.close_connection()
            response_sent = True
        if result.use_custom_reply():
            self._send_custom_response(result.get_custom_reply())
        if result.close_connection_after_response():
            self.please_close_connection_after_response()
        return decision, response_sent
    
    def is_allowed(self, acl_name, *args):
        if self._policy is not None:
            decider = getattr(self._policy, acl_name)
            result = decider(*args)
            if result in [True, False, None]:
                return self._evaluate_decision(result), False
            elif hasattr(result, 'is_command_acceptable'):
                return self._evaluate_policydecision_result(result)
            elif len(result) == 2:
                decision = self._evaluate_decision(result[0])
                self._send_custom_response(result[1])
                return decision, True
            raise ValueError('Unknown policy response')
        return True, False
    
    # -------------------------------------------------------------------------
    
    def new_connection(self, remote_ip, remote_port):
        """This method is called when a new SMTP session is opened.
        [PUBLIC API]
        """
        self.state.set_state('new')
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
        self.please_close_connection_after_response(False)
        # SMTP commands must be treated as case-insensitive
        command = smtp_command.upper()
        try:
            try:
                self.state.execute(command)
            except StateMachineError:
                if command not in self.valid_commands:
                    self.reply(500, 'unrecognized command "%s"' % smtp_command)
                else:
                    msg = 'Command "%s" is not allowed here' % smtp_command
                    allowed_transitions = self.state.allowed_actions()
                    if len(allowed_transitions) > 0:
                        msg += ', expected on of %s' % allowed_transitions
                        self.reply(503, msg)
            except InvalidDataError, e:
                self.reply(501, e.msg())
            except InvalidParametersError, e:
                # TODO: Get rid of InvalidParametersError, shouldn't be 
                # necessary anymore
                if not e.response_sent:
                    msg = 'Syntactically invalid %s argument(s)' % smtp_command
                    self.reply(501, msg)
            except PolicyDenial, e:
                if not e.response_sent:
                    self.reply(e.code, e.reply_text)
        finally:
            if self.should_close_connection_after_response():
                self.close_connection()
            self._command_arguments = None
    
    def input_exceeds_limits(self):
        """Called when the client sent a message that exceeded the maximum 
        size."""
        self.reply(552, 'message exceeds fixed maximum message size')
    
    def reply(self, code, text):
        """This method returns a message to the client (actually the session 
        object is responsible of actually pushing the bits)."""
        self._command_parser.push(code, text)
    
    def multiline_reply(self, code, responses):
        """This method returns a message with multiple lines to the client 
        (actually the session object is responsible of actually pushing the 
        bits)."""
        self._command_parser.multiline_push(code, responses)
    
    def please_close_connection_after_response(self, value=None):
        if value is None:
            value = True
        self._close_connection_after_response = value
    
    def should_close_connection_after_response(self):
        return self._close_connection_after_response
    
    def close_connection(self):
        "Request a connection close from the SMTP session handling instance."
        if self._is_connected:
            self._is_connected = False
            self._command_parser.close_when_done()
    
    
    # -------------------------------------------------------------------------
    # Protocol handling functions (not public)
    
    def arguments(self):
        """Return the given parameters for the command as a string or an empty 
        string"""
        return self._command_arguments or ''
    
    def smtp_greet(self):
        """This method handles not a real smtp command. It is called when a new
        connection was accepted by the server."""
        # Policy check was done when accepting the connection so we don't have 
        # to do it here again.
        primary_hostname = self._command_parser.primary_hostname
        reply_text = '%s Hello %s' % (primary_hostname, self._message.peer.remote_ip)
        self.reply(220, reply_text)
    
    def validate(self, schema_class):
        context = dict(esmtp=self.uses_esmtp())
        return schema_class().process(self.arguments(), context=context)
    
    def smtp_quit(self):
        self.validate(SMTPCommandArgumentsSchema)
        primary_hostname = self._command_parser.primary_hostname
        reply_text = '%s closing connection' % primary_hostname
        self.reply(221, reply_text)
        self._command_parser.close_when_done()
    
    def smtp_noop(self):
        self.validate(SMTPCommandArgumentsSchema)
        self.reply(250, 'OK')
    
    def smtp_help(self):
        # deliberately no checking for additional parameters because RFC 821 
        # says:
        # "The command may take an argument (e.g., any command name) and 
        #  return more specific information as a response."
        states = self.get_all_allowed_smtp_commands()
        self.multiline_reply(214, ('Commands supported', ' '.join(states)))
    
    def _reply_to_helo(self, helo_string, response_sent):
        self._message.smtp_helo = helo_string
        if not response_sent:
            primary_hostname = self._command_parser.primary_hostname
            self.reply(250, primary_hostname)
    
    def _process_helo_or_ehlo(self, policy_methodname, reply_method):
        validated_data = self.validate(HeloSchema)
        helo_string = validated_data['helo']
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
        credentials_correct = \
            self._authenticator.authenticate(username, password, self._message.peer)
        if credentials_correct:
            self._message.username = username
            self.reply(235, 'Authentication successful')
        else:
            self.reply(535, 'Bad username or password')
    
    def smtp_auth_plain(self):
        if self._authenticator is None:
            self.reply(535, 'AUTH not available')
            raise InvalidParametersError(response_sent=True)
        validated_data = self.validate(AuthPlainSchema)
        self._check_password(validated_data['username'], validated_data['password'])
    
    def _check_size_restriction(self, extensions):
        announced_size = extensions.get('size')
        if announced_size is None:
            return
        max_message_size = self._max_message_size()
        if max_message_size is None:
            return
        if announced_size > max_message_size:
            self.reply(552, 'message exceeds fixed maximum message size')
            raise InvalidParametersError('MAIL FROM', response_sent=True)
    
    def uses_esmtp(self):
        return self.state.is_set('esmtp')
    
    def smtp_mail_from(self):
        validated_data = self.validate(MailFromSchema)
        sender = validated_data['email']
        self._check_size_restriction(validated_data)
        decision, response_sent = self.is_allowed('accept_from', sender, self._message)
        if not decision:
            raise PolicyDenial(response_sent)
        self._message.smtp_from = sender
        if not response_sent:
            self.reply(250, 'OK')
    
    def smtp_rcpt_to(self):
        validated_data = self.validate(RcptToSchema)
        email_address = validated_data['email']
        decision, response_sent = self.is_allowed('accept_rcpt_to', email_address, self._message)
        if decision:
            self._message.smtp_to.append(email_address)
            if not response_sent:
                self.reply(250, 'OK')
        elif not decision:
            raise PolicyDenial(response_sent, 550, 'relay not permitted')
    
    def smtp_data(self):
        self.validate(SMTPCommandArgumentsSchema)
        decision, response_sent = self.is_allowed('accept_data', self._message)
        if decision and not response_sent:
            self._command_parser.switch_to_data_mode()
            self.reply(354, 'Enter message, ending with "." on a line by itself')
        elif not decision:
            raise PolicyDenial(response_sent)
    
    def _max_message_size(self):
        max_message_size = None
        if (self._policy is not None) and (self._message.peer is not None):
            max_message_size = self._policy.max_message_size(self._message.peer)
        return max_message_size
    
    def _check_size_restrictions(self, msg_data):
        max_message_size = self._max_message_size()
        if max_message_size is None:
            return
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
        msg_data = self.arguments()
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
        self.validate(SMTPCommandArgumentsSchema)
        self._message = Message(peer=self._message.peer, 
                                smtp_helo=self._message.smtp_helo)
        self.reply(250, 'Reset OK')
    

