# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
#
# Autopilot Functional Test Tool
# Copyright (C) 2013 Canonical
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
from mock import call, Mock, patch
from testtools import TestCase
from testtools.matchers import Contains, raises

from autopilot.testcase import (
    _compare_system_with_process_snapshot,
    AutopilotTestCase
)
from autopilot.utilities import sleep


class ProcessSnapshotTests(TestCase):

    def test_snapshot_returns_when_no_apps_running(self):
        with sleep.mocked() as mock_sleep:
            _compare_system_with_process_snapshot(lambda: [], [])

            self.assertEqual(0.0, mock_sleep.total_time_slept())

    def test_snapshot_raises_AssertionError_with_new_apps_opened(self):
        with sleep.mocked():
            fn = lambda: _compare_system_with_process_snapshot(
                lambda: ['foo'],
                []
            )
            self.assertThat(fn, raises(AssertionError(
                "The following apps were started during the test and "
                "not closed: ['foo']"
            )))

    def test_bad_snapshot_waits_10_seconds(self):
        with sleep.mocked() as mock_sleep:
            try:
                _compare_system_with_process_snapshot(
                    lambda: ['foo'],
                    []
                )
            except:
                pass
            finally:
                self.assertEqual(10.0, mock_sleep.total_time_slept())

    def test_snapshot_does_not_raise_on_closed_old_app(self):
        _compare_system_with_process_snapshot(lambda: [], ['foo'])

    def test_snapshot_exits_after_first_success(self):
        get_snapshot = Mock()
        get_snapshot.side_effect = [['foo'], []]

        with sleep.mocked() as mock_sleep:
            _compare_system_with_process_snapshot(
                get_snapshot,
                []
            )
            self.assertEqual(1.0, mock_sleep.total_time_slept())

    def test_using_pick_app_launcher_produces_deprecation_message(self):
        class InnerTest(AutopilotTestCase):
            def test_foo(self):
                self.pick_app_launcher()

        with patch('autopilot.testcase.get_application_launcher_wrapper'):
            with patch('autopilot.utilities.logger') as patched_log:
                InnerTest('test_foo').run()

                self.assertThat(
                    patched_log.warning.call_args[0][0],
                    Contains(
                        "This function is deprecated. Please use "
                        "'the 'app_type' argument to the "
                        "launch_test_application method' instead."
                    )
                )


class AutopilotTestCaseClassTests(TestCase):

    """Test functions of the AutopilotTestCase class."""

    @patch('autopilot.testcase.EnvironmentPatch')
    def test_patch_environment(self, ep):
        class EnvironmentPatchingTestCase(AutopilotTestCase):

            """Patch the enrivonment."""

            def test_patch_environment(self):
                self.patch_environment('foo', 'bar')

        EnvironmentPatchingTestCase('test_patch_environment').run()
        ep.assert_called_once_with('foo', 'bar')
        self.assertIn(call().setUp(), ep.mock_calls)
        self.assertIn(call().cleanUp(), ep.mock_calls)
