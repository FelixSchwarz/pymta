# -*- coding: UTF-8 -*-

from unittest import TestCase

from pymta import SMTPProcessor

class MockSession(object):
    primary_hostname = 'localhost'
    
    def __init__(self):
        self.replies = []
        self.open = True
    
    def push(self, code, text):
        self.replies.append((code, text))
    
    def close_when_done(self):
        assert self.open
        self.open = False
    


class BasicMessageSendingTest(TestCase):

    def setUp(self):
        self.session = MockSession()
        self.processor = SMTPProcessor(session=self.session)
        self.processor.new_connection('127.0.0.1', 4567)
    
    def _close_connection(self):
        self.processor.handle_input('quit')
        self.assertTrue(len(self.session.replies) >= 1)
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
        self.processor.handle_input('helo', 'foo.example.com')
        self.assertEqual(2, len(self.session.replies))
        code, reply_text = self.session.replies[-1]
        self.assertEqual(250, code)
        self.assertEqual('localhost', reply_text)
        self._close_connection()

    def test_reject_duplicated_helo(self):
        self.processor.handle_input('helo', 'foo.example.com')
        self.processor.handle_input('helo', 'foo.example.com')
        self.assertEqual(3, len(self.session.replies))
        code, reply_text = self.session.replies[-1]
        self.assertEqual(502, code)
        expected_message = 'Command "helo" is not allowed here'
        self.assertTrue(reply_text.startswith(expected_message), reply_text)
        self._close_connection()

    def test_invalid_commands_are_recognized(self):
        self.processor.handle_input('invalid')
        self.assertEqual(2, len(self.session.replies))
        code, reply_text = self.session.replies[-1]
        self.assertEqual(500, code)
        self.assertEqual('unrecognized command', reply_text)
        self._close_connection()

    def test_send_simple_mail(self):
        self.processor.handle_input('MAIL FROM', 'foo@example.com')
        self.processor.handle_input('RCPT TO', 'bar@example.com')
        msg = 'Subject: Test\r\n\r\nJust testing...\r\n'
        self.processor.handle_input('DATA', msg)
        self._close_connection()



