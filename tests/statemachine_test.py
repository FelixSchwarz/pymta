# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

from unittest import TestCase

import pytest

from pymta.statemachine import StateMachine, StateMachineDefinitionError, \
    StateMachineError


def test_can_initialize_statemachine():
    StateMachine(initial_state='foo')

# --- adding states ------------------------------------------------------

def test_can_add_states():
    state = StateMachine(initial_state='new')
    state.add('new', 'processed', 'process')
    state.add('new', 'new', 'noop')

def test_raise_exception_if_duplicate_action_is_defined():
    state = StateMachine(initial_state='new')
    state.add('new', 'processed', 'process')
    with pytest.raises(StateMachineDefinitionError):
        state.add('new', 'new', 'process')

# --- introspection ------------------------------------------------------

def test_can_ask_for_current_state():
    state = StateMachine(initial_state='foo')
    state.add('foo', 'foo', 'noop')
    assert state.state() == 'foo'
    assert not state.is_impossible_state()

def test_no_state_if_initial_state_not_available():
    state = StateMachine(initial_state='invalid')
    assert state.state() is None
    assert state.is_impossible_state()

def test_can_ask_for_all_known_actions():
    state = StateMachine(initial_state='new')
    state.add('new', 'new', 'noop')
    state.add('new', 'processed', 'process')
    state.add('processed', 'new', 'rework')
    assert state.known_actions() == set(('noop', 'process', 'rework'))

def test_can_ask_for_all_currently_allowed_actions():
    state = StateMachine(initial_state='new')
    state.add('new', 'new', 'noop')
    state.add('new', 'processed', 'process')
    state.add('processed', 'new', 'rework')

    assert state.allowed_actions() == set(('noop', 'process'))
    state.set_state('processed')
    assert state.allowed_actions() == set(('rework',))

def test_can_ask_for_all_known_states():
    state = StateMachine(initial_state='new')
    assert state.known_states() == set()
    state.add('new', 'processed', 'process')
    state.add('processed', 'done', 'finalize')
    assert state.known_states() == set(('new', 'processed', 'done'))

def test_can_ask_for_all_non_final_states():
    state = StateMachine(initial_state='new')
    assert state.known_non_final_states() == set()
    state.add('new', 'processed', 'process')
    state.add('processed', 'done', 'finalize')
    assert state.known_non_final_states() == set(('new', 'processed'))

# --- handling states ----------------------------------------------------

def test_can_not_set_state_to_invalid_state():
    state = StateMachine(initial_state='new')
    with pytest.raises(StateMachineError):
        state.set_state('invalid')

# --- executing ----------------------------------------------------------

def test_can_execute_states():
    state = StateMachine(initial_state='new')
    state.add('new', 'processed', 'process')
    state.execute('process')
    assert state.state() == 'processed'

def test_handler_is_called_for_state_transition():
    state = StateMachine(initial_state='new')
    _ctx = {'transition': None}
    def handler(from_state, to_state, action_name):
        _ctx['transition'] = (from_state, to_state, action_name)

    state.add('new', 'new', 'noop', handler)
    state.execute('noop')
    assert state.state() == 'new'
    assert _ctx['transition'] == ('new', 'new', 'noop')

def test_raise_exception_for_invalid_action():
    state = StateMachine(initial_state='new')
    state.add('new', 'processed', 'process')
    with pytest.raises(StateMachineError):
        state.execute('invalid')

    state.add('processed', 'new', 'rework')
    with pytest.raises(StateMachineError):
        state.execute('rework')
    state.execute('process')
    with pytest.raises(StateMachineError):
        state.execute('process')
    state.execute('rework')

def test_raise_exception_if_in_impossible_state():
    state = StateMachine(initial_state='new')
    state = StateMachine(initial_state='invalid')
    state.add('new', 'processed', 'process')
    with pytest.raises(StateMachineError):
        state.execute('process')

def test_raise_exception_if_no_outgoing_transition_defined_when_executing():
    state = StateMachine(initial_state='new')
    state.add('new', 'processed', 'process')
    state.set_state('processed')
    with pytest.raises(StateMachineError):
        state.execute('rework')

# --- transition with operations and conditions --------------------------

def test_can_add_transition_with_additional_operation():
    state = StateMachine(initial_state='new')
    state.add('new', 'processed', 'process', operations=('set_foo',))

def test_can_tell_if_flag_is_set():
    state = StateMachine(initial_state='new')
    assert not state.is_set(None)
    assert not state.is_set('foo')

def test_transition_can_also_set_flags():
    state = StateMachine(initial_state='new')
    state.add('new', 'processed', 'process', operations=('set_foo',))
    assert not state.is_set('foo')

    state.execute('process')
    assert state.is_set('foo')

def test_can_add_conditional_transition():
    state = StateMachine(initial_state='new')
    state.add('new', 'authenticated', 'authenticate', condition='if_tls')

def test_allowed_actions_obeys_condition():
    state = StateMachine(initial_state='new')
    state.add('new', 'new', 'use_tls', operations=('set_tls',))
    state.add('new', 'authenticated', 'authenticate', condition='if_tls')
    assert state.allowed_actions() == set(('use_tls',))
    state.execute('use_tls')
    assert state.allowed_actions() == set(('use_tls', 'authenticate'))

def test_conditional_transition_is_only_executed_if_flag_is_true():
    state = StateMachine(initial_state='new')
    state.add('new', 'new', 'use_tls', operations=('set_tls',))
    state.add('new', 'authenticated', 'authenticate', condition='if_tls')
    assert state.state() == 'new'
    with pytest.raises(StateMachineError):
        state.execute('authenticate')
    state.execute('use_tls')
    assert state.is_set('tls')
    state.execute('authenticate')

def test_can_also_specify_negative_flag_checks_for_transitions():
    state = StateMachine(initial_state='new')
    state.add('new', 'new', 'use_tls', operations=('set_tls',), condition='if_not_tls')
    state.add('new', 'authenticated', 'authenticate', condition='if_tls')

    with pytest.raises(StateMachineError):
        state.execute('authenticate')

    state.execute('use_tls')
    with pytest.raises(StateMachineError):
        state.execute('use_tls')
    state.execute('authenticate')

