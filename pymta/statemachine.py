# -*- coding: UTF-8 -*-
# SPDX-License-Identifier: MIT

from __future__ import print_function, unicode_literals

import re


__all__ = ['StateMachine', 'StateMachineDefinitionError', 'StateMachineError']


class StateMachineError(Exception):
    pass


class StateMachineDefinitionError(StateMachineError):
    pass


class StateMachine(object):
    def __init__(self, initial_state=None):
        self._state = initial_state
        self._transitions = {}
        self._flags = {}

    # --- states ---------------------------

    def state(self):
        if self.is_impossible_state():
            return None
        return self._state

    def is_impossible_state(self):
        return (self._state not in self.known_states())

    def set_state(self, state):
        if state not in self.known_states():
            raise StateMachineError
        self._state = state

    # --- transitions ----------------------

    def add(self, from_state, to_state, action_name, handler=None, operations=(), condition=None):
        self._transitions.setdefault(from_state, {})
        if action_name in self._transitions[from_state]:
            old_to_state = self._transitions[from_state][action_name][0]
            msg = 'Duplicate action "%s" for state "%s" (-> "%s" already known, can not add transition to "%s")' % (action_name, from_state, old_to_state, to_state)
            raise StateMachineDefinitionError(msg)
        self._transitions[from_state][action_name] = (to_state, handler, operations, condition)

    def execute(self, action_name):
        if action_name not in self.allowed_actions():
            msg = 'Invalid action "%s", expected one of %s' % (action_name, self.allowed_actions())
            raise StateMachineError(msg)

        current_state = self.state()
        current_transitions = self._transitions.get(current_state, {})
        final_state, handler, operations, condition = current_transitions[action_name]
        if handler is not None:
            handler(current_state, final_state, action_name)
        for operation in operations:
            self._execute_operation(operation)
        self._state = final_state

    # --- flags ----------------------------

    def is_set(self, flag):
        return self._flags.get(flag, False)

    def _execute_operation(self, operation):
        match = re.search('^set_(\w+)$', operation)
        assert match is not None
        flag_name = match.group(1)
        self._flags[flag_name] = True

    def _is_condition_satisfied(self, condition):
        if condition is None:
            return True
        match = re.search('^if_(not_)?(\w+?)$', condition)
        assert match is not None
        flag = match.group(2)
        if match.group(1):
            return not self.is_set(flag)
        return self.is_set(flag)

    # --- introspection --------------------

    def known_actions(self):
        actions = set()
        for action_name in self._transitions.values():
            actions = actions.union(action_name)
        return actions

    def allowed_actions(self):
        current_transitions = self._transitions.get(self.state(), {})
        _allowed_actions = set()
        for action_name, (to_state, handler, operations, condition) in current_transitions.items():
            if not self._is_condition_satisfied(condition):
                continue
            _allowed_actions.add(action_name)
        return _allowed_actions

    def known_non_final_states(self):
        return set(self._transitions)

    def known_states(self):
        states = self.known_non_final_states()
        for from_state, action_names in self._transitions.items():
            for action_name in action_names:
                (to_state, handler, operations, condition) = self._transitions[from_state][action_name]
                states.update((to_state,))
        return states


