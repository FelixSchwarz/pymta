# -*- encoding: utf-8 -*-
"""The idea is to improve Python's unittest.TestCase class with a more pythonic
API and some convenience functionality."""

# Authors: 
#  - Felix Schwarz <felix.schwarz@agile42.com>
#  - Martin Häcker <martin.haecker@agile42.com>

from unittest import TestCase

from pymta.lib.simple_super import SuperProxy


__all__ = ['PythonicTestCase']


class PythonicTestCase(TestCase):
    
    super = SuperProxy()
    
    def assert_raises(self, exception_type, callable, *args, **kwargs):
        try:
            callable(*args, **kwargs)
        except exception_type, e:
            return e
        # We want the same error message as assertRaises but we must not 
        # assume that callable is idempotent
        self.assertRaises(exception_type, lambda: None)
    
    def assert_false(self, actual, msg=None):
        self.assertEquals(False, actual, msg=msg)
    
    def assert_true(self, actual, msg=None):
        self.assertEquals(True, actual, msg=msg)
    
    def assert_trueish(self, actual, msg=None):
        self.assertTrue(actual, msg=msg)
    
    def assert_none(self, actual, msg=None):
        self.assertEquals(None, actual, msg=msg)
    
    def assert_not_none(self, actual, msg=None):
        self.assertNotEquals(None, actual, msg=msg)
    
    def assert_equals(self, expected, actual, msg=None):
        self.assertEquals(expected, actual, msg=msg)
    
    def assert_not_equals(self, expected, actual, msg=None):
        self.assertNotEquals(expected, actual, msg=msg)
    
    def assert_almost_equals(self, expected, actual, places=None, msg=None):
        self.assertAlmostEqual(expected, actual, places=places, msg=msg)


