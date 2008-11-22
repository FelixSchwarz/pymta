# -*- coding: UTF-8 -*-

from sets import Set

from repoze.workflow.statemachine import StateMachine, StateMachineError

from pymta.model import Message

__all__ = ['SMTPProcessor']


class SMTPProcessor(object):
    """The SMTPProcessor processes all input data which were extracted from 
    sockets previously. The idea behind is that this class is decoupled from 
    asynchat as much as possible and make it really testable."""
    
    def __init__(self, session, policy=None):
        self._session = session
        self._policy = policy
        
        self._command_arguments = None
        self._message = None
        
        self.remote_ip_string = None
        self.remote_port = None
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
        self._add_state('recipient_known', 'DATA',  'identify')
        # How to add commands?
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
            handler_method()
    
    # -------------------------------------------------------------------------
    
    def new_connection(self, remote_ip, remote_port):
        """This method is called when a new SMTP session is opened.
        [PUBLIC API]
        """
        self.remote_ip_string = remote_ip
        self.remote_port = remote_port
        self._state = 'new'
        
        if (self._policy != None) and \
            (not self._policy.accept_new_connection(self.remote_ip_string, self.remote_port)):
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
        self._command_arguments = None
    
    
    def reply(self, code, text):
        """This method returns a message to the client (actually the session 
        object is responsible of actually pushing the bits)."""
        self._session.push(code, text)
    
    
    def close_connection(self):
        "Request a connection close from the SMTP session handling instance."
        self._session.close_when_done()
        self.remote_ip_string = None
        self.remote_port = None
    
    
    # -------------------------------------------------------------------------
    # Protocol handling functions (not public)
    
    def smtp_greet(self):
        """This method handles not a real smtp command. It is called when a new
        connection was accepted by the server."""
        primary_hostname = self._session.primary_hostname
        reply_text = '%s Hello %s' % (primary_hostname, self.remote_ip_string)
        self.reply(220, reply_text)
        self._message = Message(None)
    
    def smtp_quit(self):
        primary_hostname = self._session.primary_hostname
        reply_text = '%s closing connection' % primary_hostname
        self.reply(221, reply_text)
        self._session.close_when_done()
    
    def smtp_noop(self):
        self.reply(250, 'OK')
    
    def smtp_helo(self):
        helo_string = self._command_arguments
        # We could store the helo string for a later check
        primary_hostname = self._session.primary_hostname
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
        msg_data = self._command_arguments
        # TODO: Policy check
        self._message.msg_data = msg_data
        self._session.new_message_received(self._message)
        self._message = None
        self.reply(250, 'OK')
        # Now we must not loose the message anymore!


