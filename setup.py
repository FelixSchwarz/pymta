#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import os

import setuptools

from pymta.lib.distribution_helpers import information_from_file

if __name__ == '__main__':
    release_filename = os.path.join('pymta', 'release.py')
    externally_defined_parameters= information_from_file(release_filename)
    
    setuptools.setup(
          install_requires=['pycerberus >= 0.5dev'],
          
          # simple_super is not zip_safe
          zip_safe=False,
          packages=setuptools.find_packages(),
          classifiers = [
              'Development Status :: 4 - Beta',
              'Intended Audience :: Developers',
              'License :: OSI Approved :: MIT License',
              'Operating System :: OS Independent',
              'Programming Language :: Python',
              'Topic :: Communications :: Email',
              'Topic :: Software Development :: Libraries :: Python Modules',
            ],
          test_suite = 'nose.collector',
          **externally_defined_parameters
    )


