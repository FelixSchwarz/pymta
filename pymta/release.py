# -*- coding: UTF-8 -*-
"""Release information about pymta."""

name = "pymta"
version = "0.3.1"
description = "library to build a custom SMTP server"
long_description = """
pymta is a library to build a custom SMTP server in Python. This is useful if 
you want to...

* test mail-sending code against a real SMTP server even in your unit tests.
* build a custom SMTP server with non-standard behavior without reimplementing 
  the whole SMTP protocol.
* have a low-volume SMTP server which can be easily extended using Python

Changelog
******************************

0.3.1 (27.02.2009)
==================
 - Fixed bug which caused hang after unexpected connection drop by client

0.3 (15.02.2009)
==================
 - Switch to process-based architecture, got rid of asyncore
 - Support for size-limitations of messages, huge messages will not be stored in
   memory if they will be rejected anyway (denial of service prevention)
 - API documentation is now auto-generated
 - Renamed DefaultMTAPolicy to IMTAPolicy and moved all interfaces to pymta.api
 - Added the debugging_server as an extremely simple example of a pymta-based 
   server
"""
author = "Felix Schwarz"
email = "felix.schwarz@oss.schwarz.eu"
url = "http://www.schwarz.eu/opensource/projects/pymta"
download_url = "http://www.schwarz.eu/opensource/projects/pymta/download/%(version)s/pymta-%(version)s.tar.gz" % dict(version=version)
copyright = "© 2008-2009 Felix Schwarz"
license="MIT"

