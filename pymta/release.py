# -*- coding: UTF-8 -*-
"""Release information about pymta."""

name = "pymta"
version = "0.5dev"
description = "library to build a custom SMTP server"
long_description = """pymta is a library to build a custom SMTP server in Python. This is useful if 
you want to...
 * test mail-sending code against a real SMTP server even in your unit tests.
 * build a custom SMTP server with non-standard behavior without reimplementing 
   the whole SMTP protocol.
 * have a low-volume SMTP server which can be easily extended using Python
"""
author = "Felix Schwarz"
email = "felix.schwarz@oss.schwarz.eu"
url = "http://www.schwarz.eu/opensource/projects/pymta"
download_url = "http://www.schwarz.eu/opensource/projects/pymta/download/pymta-%s.tar.gz" % version
copyright = "© 2008-2009 Felix Schwarz"
license="MIT"

