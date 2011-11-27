#!/usr/bin/env python
from setuptools import setup, find_packages


setup(
        name='pymta',
        version='0.6dev',
        description='library to build a custom SMTP server',
        long_description="""
pymta is a library to build a custom SMTP server in Python. This is useful if 
you want to...

* test mail-sending code against a real SMTP server even in your unit tests.
* build a custom SMTP server with non-standard behavior without reimplementing 
  the whole SMTP protocol.
* have a low-volume SMTP server which can be easily extended using Python""",
        zip_safe=False,
        packages=find_packages(),
        license='MIT',
        author='Felix Schwarz',
        author_email='felix.schwarz@oss.schwarz.eu',
        url='http://www.schwarz.eu/opensource/projects/pymta',
        install_requires=['pycerberus >= 0.5dev'],
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
