# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
#
# Autopilot Functional Test Tool
# Copyright (C) 2012-2013 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#


"""Autopilot-specific testtools matchers."""

from __future__ import absolute_import

from functools import partial
from testtools.matchers import Matcher, Mismatch
from time import sleep


class Eventually(Matcher):
    """Asserts that a value will eventually equal a given Matcher object.

    This matcher wraps another testtools matcher object. It makes that other
    matcher work with a timeout. This is necessary for several reasons:

    1. Since most actions in a GUI applicaton take some time to complete, the
       test may need to wait for the application to enter the expected state.

    2. Since the test is running in a separate process to the application under
       test, test authors cannot make any assumptions about when the
       application under test will recieve CPU time to update to the expected
       state.

    There are two main ways of using the Eventually matcher:

    **Attributes from the application**::

        self.assertThat(window.maximized, Eventually(Equals(True)))

    Here, ``window`` is an object generated by autopilot from the applications
    state. This pattern of usage will cover 90% (or more) of the assertions in
    an autopilot test. Note that any matcher can be used - either from
    testtools or any custom matcher that implements the matcher API::

        self.assertThat(window.height, Eventually(GreaterThan(200)))

    **Callable Objects**::

        self.assertThat(
            autopilot.platform.model, Eventually(Equals("Galaxy Nexus")))

    In this example we're using the :func:`autopilot.platform.model` function
    as a callable. In this form, Eventually matches against the return value
    of the callable.

    This can also be used to use a regular python property inside an Eventually
    matcher::

        self.assertThat(lambda: self.mouse.x, Eventually(LessThan(10)))

    .. note:: Using this form generally makes your tests less readabvle, and
        should be used with great care. It also relies the test author to have
        knowledge about the implementation of the object being matched against.
        In this example, if ``self.mouse.x`` were ever to change to be a
        regular python attribute, this test would likely break.

    **Timeout**

    By default timeout period is ten seconds. This can be altered by passing
    the timeout keyword::

        self.assertThat(foo.bar, Eventually(Equals(123), timeout=30))

    """

    def __init__(self, matcher, **kwargs):
        super(Eventually, self).__init__()
        self.timeout = kwargs.pop('timeout', 10)
        if kwargs:
            raise ValueError(
                "Unknown keyword arguments: %s" % ', '.join(kwargs.keys()))
        match_fun = getattr(matcher, 'match', None)
        if match_fun is None or not callable(match_fun):
            raise TypeError(
                "Eventually must be called with a testtools matcher argument.")
        self.matcher = matcher

    def match(self, value):
        if callable(value):
            wait_fun = partial(_callable_wait_for, value)
        else:
            wait_fun = getattr(value, 'wait_for', None)
            if wait_fun is None or not callable(wait_fun):
                raise TypeError(
                    "Eventually is only usable with attributes that have a "
                    "wait_for function or callable objects.")

        try:
            wait_fun(self.matcher, self.timeout)
        except AssertionError as e:
            return Mismatch(str(e))
        return None

    def __str__(self):
        return "Eventually " + str(self.matcher)


def _callable_wait_for(refresh_fn, matcher, timeout):
    """Like the patched :meth:`wait_for method`, but for callable objects
    instead of patched variables.

    """
    time_left = timeout
    while True:
        new_value = refresh_fn()
        mismatch = matcher.match(new_value)
        if mismatch:
            failure_msg = mismatch.describe()
        else:
            return

        if time_left >= 1:
            sleep(1)
            time_left -= 1
        else:
            sleep(time_left)
            break

    # can't give a very descriptive message here, especially as refresh_fn
    # is likely to be a lambda.
    raise AssertionError(
        "After %.1f seconds test failed: %s" % (timeout, failure_msg))
