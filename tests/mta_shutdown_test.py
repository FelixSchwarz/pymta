# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

import random
import smtplib
import time

import pytest
from pymta.test_util import BlackholeDeliverer, DebuggingMTA, MTAThread, SMTPTestHelper


def _send_message(hostname, listen_port):
    # After the SMTP session the worker is waiting for new connections again
    # (blocking in "accept()") so the shutdown must wake it up.
    smtp_connection = smtplib.SMTP(hostname, listen_port)
    msg = 'Subject: Test\n\nJust testing...'
    smtp_connection.sendmail('from@example.com', ['to@example.com'], msg)
    smtp_connection.quit()


def _assert_fast_shutdown(stop_mta, mta_thread):
    # The server socket uses a timeout of 1 second so "stop_mta()" would take
    # about one second if the worker is not woken up actively.
    start = time.time()
    stop_mta()
    duration = time.time() - start
    assert not mta_thread.is_alive()
    assert duration < 0.5, 'shutdown took %.2f seconds' % duration


def test_shutdown_after_smtp_session():
    mta_helper = SMTPTestHelper()
    (hostname, listen_port) = mta_helper.start_mta()
    mta_thread = mta_helper.mta_thread
    _send_message(hostname, listen_port)

    _assert_fast_shutdown(mta_helper.stop_mta, mta_thread)
    assert mta_helper.get_received_messages().qsize() == 1


@pytest.mark.parametrize('local_address', ['', '0.0.0.0'])
def test_shutdown_when_listening_on_all_interfaces(local_address):
    listen_port = random.randint(8000, 40000)
    mta = DebuggingMTA(local_address, listen_port, deliverer_class=BlackholeDeliverer)
    mta_thread = MTAThread(mta)
    mta_thread.start()
    SMTPTestHelper()._try_to_connect_to_mta('127.0.0.1', listen_port)
    _send_message('127.0.0.1', listen_port)

    _assert_fast_shutdown(mta_thread.stop, mta_thread)
