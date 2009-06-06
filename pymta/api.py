# -*- coding: UTF-8 -*-
"""This package contains classes which from which you can derive your own 
classes easily to customize the behavior of your MTA. Everything in here is 
considered part of the public API which should be as stable as possible."""
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

__all__ = ['IAuthenticator', 'IMessageDeliverer', 'IMTAPolicy', 'PolicyDecision', 
           'PyMTAException']


class IAuthenticator(object):
    """Authenticators check if the user’s credentials are actually correct. This
    may involve some checking against external subsystems (e.g. a database or a
    LDAP directory)."""
    
    def authenticate(self, username, password, peer):
        """This method is called after the client issued an AUTH PLAIN command 
        and must return a boolean value (True/False)."""
        raise NotImplementedError



class IMessageDeliverer(object):
    """Deliverers take care of the message routing/delivery after a message was
    accepted (e.g. put it in a mailbox file, forward it to another server, ...).
    """
    
    def new_message_accepted(self, msg):
        """This method is called when a new message was accepted by the server.
        Now the MTA is then in charge of delivering the message to the 
        specified recipients. Please note that you can not reject the message 
        anymore at this stage (if there are problems you must generate a 
        non-delivery report aka bounce). 
        
        There will be one deliverer instance per client connection so
        this method may does not have to be thread-safe. However this method 
        may get called multiple times when the client transmits more than one
        message for the same connection."""
        raise NotImplementedError


class PolicyDecision(object):
    def __init__(self, decision=True, reply=None):
        self._decision = decision
        self._reply = reply
        self._close_connection_before_response = False
        self._close_connection_after_response = False
    
    def close_connection_before_response(self):
        """Return True if the server should close the client connection without
        any further communication."""
        return self._close_connection_before_response
    
    def close_connection_after_response(self):
        """Return True if the server should close the client connection after it
        sent the given response."""
        return self._close_connection_after_response
    
    def is_command_acceptable(self):
        return self._decision
    
    def use_custom_reply(self):
        return (self._reply is not None)
    
    def get_custom_reply(self):
        if not self.use_custom_reply():
            raise ValueError('No custom reply set.')
        return self._reply


class IMTAPolicy(object):
    """Policies can change with behavior of an MTA dynamically (e.g. don't allow 
    relaying unless the client is located within the trusted company network,
    enable authentication only for some connections). In established MTAs like
    Exim and Postfix it's a very important task for every system administrator 
    to configure the message acceptance policies which are normally part of the
    configuration file.
    
    A policy does not change the SMTP implementation itself (the state machine) 
    but can send out custom replies to the client. A policy doesn't have to care 
    if the commands were given in the correct order (the state machines will 
    take care of that). The only thing is that the message object passed into 
    many policy methods does not contain all data at certain stages (e.g. 
    accept_mail_from can not access the recipients list because that was not 
    submitted yet).
    
    'IMTAPolicy' provides a very permissive policy (all commands are 
    accepted) from which you can derive custom policies. Its methods are usually
    named 'accept_<SMTP command name>'.
    
    Every method in the 'IMTAPolicy' interface can return either a single
    boolean value (True/False) or a tuple. A boolean value specifies if the
    command should be accepted. The caller is responsible for sending the actual
    default replies.
    
    Alternatively a policy can choose to return a tuple to have more control 
    over the reply sent to the client: (decision, (reply code, reply message)). 
    The decision is the boolean known from the last paragraph. The reply code 
    is an integer which should a be a valid SMTP code. reply message is either a 
    basestring with a custom message or an iterable of basestrings (in case a 
    a multi-line reply is sent).
    
    Last but not least a PolicyDecision can be returned which embodies the 
    decision as well as (optionally) a custom reply. The reply has the same 
    format as described in the paragraph before. The PolicyDecision can ask the
    server to close the connection unconditionally after or even before sending
    the response to the client (in the latter case no response will be sent).
    """
    
    def accept_new_connection(self, peer):
        """This method is called directly after a new connection is received. 
        The  policy can decide if the given peer is allowed to connect to the 
        SMTP server. If it declines, the connection will be closed 
        immediately."""
        return True
    
    def max_message_size(self, peer):
        """Return the maximum size (in bytes) for messages from this peer. When
        this method returns an integer, there pymta will check the actual 
        message size after the message was received (before the accept_msgdata
        method is called) and will respond with the appropriate error message if
        necessary.
        If you return None, no size limit will be enforced by pymta (however you
        can always reject a message using accept_msgdata()."""
        return None
    
    def ehlo_lines(self, peer):
        """Return an iterable for SMTP extensions to advertise after EHLO.
        By default support for SMTP SIZE extension will be announced if you set
        a max message size."""
        max_size = self.max_message_size(peer)
        if max_size != None:
            return ('SIZE %d' % max_size,)
        return ()
    
    def accept_helo(self, helo_string, message):
        """Decides if the HELO command with the given helo_name should be 
        accepted."""
        return True
    
    def accept_ehlo(self, ehlo_string, message):
        """Decides if the EHLO command with the given helo_name should be 
        accepted."""
        return True
    
    def accept_auth_plain(self, username, password, message):
        """Decides if AUTH plain should be allowed for this client. Please note 
        that username and password are not verified before, the authenticator 
        will check them after the policy allowed this command.
        
        The method must not return a response by itself in case it accepts the
        AUTH PLAIN command!"""
        return True
    
    def accept_from(self, sender, message):
        "Decides if the sender of this message (MAIL FROM) should be accepted."
        return True
    
    def accept_rcpt_to(self, new_recipient, message):
        """Decides if recipient of this message (RCPT TO) should be accepted. 
        If a message should be delivered to multiple recipients this method is 
        called for every recipient."""
        return True
    
    def accept_data(self, message):
        """Decides if we allow the client to start a message transfer (the 
        actual message contents will be transferred after this method allowed 
        it)."""
        return True
    
    def accept_msgdata(self, msgdata, message):
        """This method actually matches no real SMTP command. It is called 
        after a message was transferred completely and this is the last check 
        before the SMTP server takes the responsibility of transferring it to 
        the recipients."""
        return True


class PyMTAException(Exception):
    """Base class for all exceptions used in pymta."""
    pass




