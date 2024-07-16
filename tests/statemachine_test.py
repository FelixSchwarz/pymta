# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

from unittest import TestCase

import pytest

from pymta.statemachine import StateMachine, StateMachineDefinitionError, \
    StateMachineError


class StateMachineTest(TestCase):

    def setUp(self):
        self.state = StateMachine(initial_state='new')

    def test_can_initialize_statemachine(self):
        StateMachine(initial_state='foo')

    # --- adding states ------------------------------------------------------

    def test_can_add_states(self):
        self.state.add('new', 'processed', 'process')
        self.state.add('new', 'new', 'noop')

    def test_raise_exception_if_duplicate_action_is_defined(self):
        self.state.add('new', 'processed', 'process')
        with pytest.raises(StateMachineDefinitionError):
            self.state.add('new', 'new', 'process')

    # --- introspection ------------------------------------------------------

    def test_can_ask_for_current_state(self):
        state = StateMachine(initial_state='foo')
        state.add('foo', 'foo', 'noop')
        assert state.state() == 'foo'
        assert not state.is_impossible_state()

    def test_no_state_if_initial_state_not_available(self):
        state = StateMachine(initial_state='invalid')
        assert state.state() is None
        assert state.is_impossible_state()

    def test_can_ask_for_all_known_actions(self):
        self.state.add('new', 'new', 'noop')
        self.state.add('new', 'processed', 'process')
        self.state.add('processed', 'new', 'rework')
        assert self.state.known_actions() == set(('noop', 'process', 'rework'))

    def test_can_ask_for_all_currently_allowed_actions(self):
        self.state.add('new', 'new', 'noop')
        self.state.add('new', 'processed', 'process')
        self.state.add('processed', 'new', 'rework')

        assert self.state.allowed_actions() == set(('noop', 'process'))
        self.state.set_state('processed')
        assert self.state.allowed_actions() == set(('rework',))

    def test_can_ask_for_all_known_states(self):
        assert self.state.known_states() == set()
        self.state.add('new', 'processed', 'process')
        self.state.add('processed', 'done', 'finalize')
        assert self.state.known_states() == set(('new', 'processed', 'done'))

    def test_can_ask_for_all_non_final_states(self):
        assert self.state.known_non_final_states() == set()
        self.state.add('new', 'processed', 'process')
        self.state.add('processed', 'done', 'finalize')
        assert self.state.known_non_final_states() == set(('new', 'processed'))

    # --- handling states ----------------------------------------------------

    def test_can_not_set_state_to_invalid_state(self):
        with pytest.raises(StateMachineError):
            self.state.set_state('invalid')

    # --- executing ----------------------------------------------------------

    def test_can_execute_states(self):
        self.state.add('new', 'processed', 'process')
        self.state.execute('process')
        assert self.state.state() == 'processed'

    def test_handler_is_called_for_state_transition(self):
        self._transition = None
        def handler(from_state, to_state, action_name):
            self._transition = (from_state, to_state, action_name)

        self.state.add('new', 'new', 'noop', handler)
        self.state.execute('noop')
        assert self.state.state() == 'new'
        assert self._transition == ('new', 'new', 'noop')

    def test_raise_exception_for_invalid_action(self):
        self.state.add('new', 'processed', 'process')
        with pytest.raises(StateMachineError):
            self.state.execute('invalid')

        self.state.add('processed', 'new', 'rework')
        with pytest.raises(StateMachineError):
            self.state.execute('rework')
        self.state.execute('process')
        with pytest.raises(StateMachineError):
            self.state.execute('process')
        self.state.execute('rework')

    def test_raise_exception_if_in_impossible_state(self):
        state = StateMachine(initial_state='invalid')
        state.add('new', 'processed', 'process')
        with pytest.raises(StateMachineError):
            self.state.execute('process')

    def test_raise_exception_if_no_outgoing_transition_defined_when_executing(self):
        self.state.add('new', 'processed', 'process')
        self.state.set_state('processed')
        with pytest.raises(StateMachineError):
            self.state.execute('rework')

    # --- transition with operations and conditions --------------------------

    def test_can_add_transition_with_additional_operation(self):
        self.state.add('new', 'processed', 'process', operations=('set_foo',))

    def test_can_tell_if_flag_is_set(self):
        assert not self.state.is_set(None)
        assert not self.state.is_set('foo')

    def test_transition_can_also_set_flags(self):
        self.state.add('new', 'processed', 'process', operations=('set_foo',))
        assert not self.state.is_set('foo')

        self.state.execute('process')
        assert self.state.is_set('foo')

    def test_can_add_conditional_transition(self):
        self.state.add('new', 'authenticated', 'authenticate', condition='if_tls')

    def test_allowed_actions_obeys_condition(self):
        self.state.add('new', 'new', 'use_tls', operations=('set_tls',))
        self.state.add('new', 'authenticated', 'authenticate', condition='if_tls')
        assert self.state.allowed_actions() == set(('use_tls',))
        self.state.execute('use_tls')
        assert self.state.allowed_actions() == set(('use_tls', 'authenticate'))

    def test_conditional_transition_is_only_executed_if_flag_is_true(self):
        self.state.add('new', 'new', 'use_tls', operations=('set_tls',))
        self.state.add('new', 'authenticated', 'authenticate', condition='if_tls')
        assert self.state.state() == 'new'
        with pytest.raises(StateMachineError):
            self.state.execute('authenticate')
        self.state.execute('use_tls')
        assert self.state.is_set('tls')
        self.state.execute('authenticate')

    def test_can_also_specify_negative_flag_checks_for_transitions(self):
        self.state.add('new', 'new', 'use_tls', operations=('set_tls',), condition='if_not_tls')
        self.state.add('new', 'authenticated', 'authenticate', condition='if_tls')

        with pytest.raises(StateMachineError):
            self.state.execute('authenticate')

        self.state.execute('use_tls')
        with pytest.raises(StateMachineError):
            self.state.execute('use_tls')
        self.state.execute('authenticate')

