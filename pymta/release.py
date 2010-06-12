# -*- coding: UTF-8 -*-
"Release information about pymta."

name = 'pymta'
version = '0.5.2'
description = 'library to build a custom SMTP server'
long_description = '''
pymta is a library to build a custom SMTP server in Python. This is useful if 
you want to...

* test mail-sending code against a real SMTP server even in your unit tests.
* build a custom SMTP server with non-standard behavior without reimplementing 
  the whole SMTP protocol.
* have a low-volume SMTP server which can be easily extended using Python

Changelog
******************************

0.5.2 (12.06.2010)
==================
- Fix bug - detect of command/message also when the terminator is sent in 
  multiple packages (fixes manual message submission with telnet)

0.5.1 (08.06.2010)
==================
- Fix egg file generation: Include all necessary packages in eggs

0.5.0 (07.04.2010)
==================
- Dropped dependency to repoze.workflow because the module added a lot of 
  dependencies recently (six others in total). The new, custom state machine
  also supports flags and conditions which suits SMTP very much.
- Added dependency to pycerberus (>= 0.3.1) to validate all sent parameters
  thoroughly with sensible error messages.
- All inputs from peers is now validated
- relaxed restrictions for the HELO/EHLO parameter (as real world clients don't
  send real host names)
- Fixed bug - ESMTP session switched back to plain SMTP after the first mail 
  was sent
- Fixed bug - Hang after sending data to a broken connection

0.4.0 (08.06.2009)
==================
- Compatibility fixes for Python 2.3-2.6
- Policies can drop connection to the client before or after the response
- CommandParser is more robust against various socket errors
- Better infrastructure and documentation to use pymta in third-party tests

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
'''
author = 'Felix Schwarz'
email = 'felix.schwarz@oss.schwarz.eu'
url = 'http://www.schwarz.eu/opensource/projects/pymta'
download_url = 'http://www.schwarz.eu/opensource/projects/%(name)s/download/%(version)s/%(name)s-%(version)s.tar.gz' % dict(name=name, version=version)
copyright = u'2008-2010 Felix Schwarz'
license='MIT'

