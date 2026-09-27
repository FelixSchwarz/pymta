# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

import smtplib

from pymta.test_util import SMTPTestHelper


def test_mta_listens_on_free_port():
    helper1 = SMTPTestHelper()
    helper2 = SMTPTestHelper()
    (hostname1, port1) = helper1.start_mta()
    (hostname2, port2) = helper2.start_mta()
    try:
        assert port1 != 0
        assert port1 == helper1.listen_port
        assert port1 != port2
        smtp_connection = smtplib.SMTP(hostname1, port1)
        assert smtp_connection.noop()[0] == 250
        smtp_connection.quit()
    finally:
        helper1.stop_mta()
        helper2.stop_mta()
