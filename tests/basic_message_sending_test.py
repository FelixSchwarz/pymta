# -*- coding: UTF-8 -*-

from unittest import TestCase

from pymta import SMTPProcessor

class MockSession(object):
    primary_hostname = 'localhost'
    
    def __init__(self, server):
        self._server = server
        self.replies = []
        self.open = True
    
    def push(self, code, text):
        self.replies.append((code, text))
    
    def close_when_done(self):
        assert self.open
        self.open = False
    
    def new_message_received(self, msg):
        self._server.new_message_received(msg)
    


class MockServer(object):
    def __init__(self):
        self.messages = []

    
    def new_message_received(self, msg):
        self.messages.append(msg)


class BasicMessageSendingTest(TestCase):

    def setUp(self):
        self.server = MockServer()
        self.session = MockSession(self.server)
        self.processor = SMTPProcessor(session=self.session)
        self.processor.new_connection('127.0.0.1', 4567)
    
    def _send(self, command, data=None):
        number_replies_before = len(self.session.replies)
        self.processor.handle_input(command, data)
        self.assertEqual(number_replies_before + 1, len(self.session.replies))
        code, reply_text = self.session.replies[-1]
        self.assertEqual('2', str(code)[0], "%s %s" % (code, reply_text))
    
    def _close_connection(self):
        self._send('quit')
        code, reply_text = self.session.replies[-1]
        self.assertTrue(221, code)
        self.assertEqual('localhost closing connection', reply_text)
        self.assertEqual(False, self.session.open)
    
    def test_new_connection(self):
        self.assertEqual(1, len(self.session.replies))
        code, reply_text = self.session.replies[-1]
        self.assertEqual(220, code)
        self.assertEqual('localhost Hello 127.0.0.1', reply_text)
        self._close_connection()
    
    def test_send_helo(self):
        self._send('helo', 'foo.example.com')
        self.assertEqual(2, len(self.session.replies))
        code, reply_text = self.session.replies[-1]
        self.assertEqual(250, code)
        self.assertEqual('localhost', reply_text)
        self._close_connection()
    
    def test_noop_does_nothing(self):
        self._send('noop')
        self._close_connection()

    def test_reject_duplicated_helo(self):
        self._send('helo', 'foo.example.com')
        self.processor.handle_input('helo', 'foo.example.com')
        self.assertEqual(3, len(self.session.replies))
        code, reply_text = self.session.replies[-1]
        self.assertEqual(503, code)
        expected_message = 'Command "helo" is not allowed here'
        self.assertTrue(reply_text.startswith(expected_message), reply_text)
        self._close_connection()

    def test_invalid_commands_are_recognized(self):
        self.processor.handle_input('invalid')
        self.assertEqual(2, len(self.session.replies))
        code, reply_text = self.session.replies[-1]
        self.assertEqual(500, code)
        self.assertEqual('unrecognized command "invalid"', reply_text)
        self._close_connection()

    def test_send_simple_mail(self):
        self._send('HELO', 'foo.example.com')
        self._send('MAIL FROM', 'foo@example.com')
        self._send('RCPT TO', 'bar@example.com')
        rfc822_msg = 'Subject: Test\r\n\r\nJust testing...\r\n'
        self._send('DATA', rfc822_msg)
        self._close_connection()
        
        self.assertEqual(1, len(self.server.messages))
        msg = self.server.messages[0]
        self.assertEqual('foo@example.com', msg.smtp_from)
        self.assertEqual('bar@example.com', msg.smtp_to)
        self.assertEqual(rfc822_msg, msg.msg_data)

        
        
        
        



