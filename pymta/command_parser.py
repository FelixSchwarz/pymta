# -*- coding: UTF-8 -*-

import asynchat

from pymta.session import SMTPSession

__all__ = ['SMTPCommandParser']

class SMTPCommandParser(asynchat.async_chat):
    """This class handles only the actual communication with the client. As soon
    as a complete command is received, this class will hand everything over to
    the SMTPProcessor.
    
    In the original 'SMTPChannel' class from Python.org this class handled 
    all communication with asynchat, implemented a extremly simple state machine
    and processed the data. Implementing hooks in that design (or adding 
    fine-grained policies) was not possible at all with the previous design."""
    LINE_TERMINATOR = '\r\n'

    def __init__(self, server, connection, remote_ip_and_port, policy):
        self.COMMAND = 0
        self.DATA = 1
        asynchat.async_chat.__init__(self, connection)
        self.set_terminator(self.LINE_TERMINATOR)
        
        self._server = server
        
        self._connection = connection
        
        self._peer = connection.getpeername()
        
        self.processor = SMTPProcessor(session=self, policy=policy)
        remote_ip_string, remote_port = remote_ip_and_port
        self.processor.new_connection(remote_ip_string, remote_port)
        
        self._line = []
        self._old_state = self.COMMAND
        self._greeting = 0
        self._mailfrom = None
        self._rcpttos = []
        self._data = ''
    
    
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
        
        if not msg.endswith(self.LINE_TERMINATOR):
            msg += self.LINE_TERMINATOR
        asynchat.async_chat.push(self, msg)
    
    def new_message_received(self, msg):
        """Called from the SMTPProcessor when a new message was received 
        successfully."""
        self._server.new_message_received(msg)
        
    
    # Implementation of base class abstract method
    # TODO: Rewrite!
    def collect_incoming_data(self, data):
        print 'collect_incoming_data', data
        self._line.append(data)

    # Implementation of base class abstract method
    # TODO: Rewrite!
    def found_terminator(self):
        line = ''.join(self._line)
        print 'Data:', repr(line)
        self._line = []
        if self._old_state == self.COMMAND:
            if not line:
                self.push('500 Error: bad syntax')
                return
            method = None
            i = line.find(' ')
            if i < 0:
                command = line
                arg = None
            else:
                command = line[:i]
                arg = line[i+1:].strip()
            print 'command is ', command
            
            self.processor.handle_input(command, arg)
            return
        else:
            if self._old_state != self.DATA:
                self.push('451 Internal confusion')
                return
            # Remove extraneous carriage returns and de-transparency according
            # to RFC 821, Section 4.5.2.
            data = []
            for text in line.split('\r\n'):
                if text and text[0] == '.':
                    data.append(text[1:])
                else:
                    data.append(text)
            self._data = '\n'.join(data)
            status = self._server.process_message(self._peer,
                                                   self._mailfrom,
                                                   self._rcpttos,
                                                   self._data)
            self._rcpttos = []
            self._mailfrom = None
            self._old_state = self.COMMAND
            self.set_terminator('\r\n')
            if not status:
                self.push('250 Ok')
            else:
                self.push(status)
    
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

    # -------------------------------------------------------------------------
    # Internal methods for sending data to the client (easy subclassing with
    # different behavior)

    def smtp_helo(self):
        if self.command_arguments in [None, '']:
            self.push('501 Syntax: HELO hostname')
        else:
            self._greeting = self.command_arguments
            self.push('250 %s' % self._fqdn)        

    # -------------------------------------------------------------------------
    # Methods that call policy checks
    

    # SMTP and ESMTP commands
    def smtp_HELO(self, arg):
        print 'helo', repr(self._greeting)
        if not arg:
            self.push('501 Syntax: HELO hostname')
            return
        if self._greeting:
            self.push('503 Duplicate HELO/EHLO')
        else:
            print 'sending ', '250 %s' % self._fqdn
            self._greeting = arg
            self.push('250 %s' % self._fqdn)
    
    def smtp_QUIT(self, arg):
        # args is ignored
        self.push('221 Bye')
        self.close_when_done()

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


