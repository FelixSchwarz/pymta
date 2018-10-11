#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

from setuptools import setup, find_packages


def requires_from_file(filename):
    requirements = []
    with open(filename, 'r') as requirements_fp:
        for line in requirements_fp.readlines():
            match = re.search('^\s*([a-zA-Z][^#]+?)(\s*#.+)?\n$', line)
            if match:
                requirements.append(match.group(1))
    return requirements

setup(
    name='pymta',
    version='0.6.0',
    description='library to build a custom SMTP server',
    long_description="""
pymta is a library to build a custom SMTP server in Python. This is useful if
you want to...

* test mail-sending code against a real SMTP server even in your unit tests.
* build a custom SMTP server with non-standard behavior without reimplementing
  the whole SMTP protocol.
* have a low-volume SMTP server which can be easily extended using Python""",
    packages = find_packages(),
    license='MIT',
    author='Felix Schwarz',
    author_email='felix.schwarz@oss.schwarz.eu',
    url='https://github.com/FelixSchwarz/pymta',
    install_requires=requires_from_file('requirements.txt'),
    tests_require=['nose'],
    test_suite='nose.collector',

    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Communications :: Email',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
