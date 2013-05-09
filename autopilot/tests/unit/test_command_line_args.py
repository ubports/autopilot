#!/usr/bin/env python
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


"Unit tests for the command line parser in autopilot."


from mock import patch
from StringIO import StringIO
from testtools import TestCase
from testtools.matchers import Equals
from unittest import expectedFailure

from autopilot import parse_arguments


class CommandLineArgsTests(TestCase):

    def parse_args(self, args):
        if isinstance(args, basestring):
            args = args.split()
        try:
            return parse_arguments(args)
        except SystemExit as e:
            self.fail("Caught exception: %r" % e)

    def test_launch_command_accepts_application(self):
        args = self.parse_args("launch app")
        self.assertThat(args.mode, Equals("launch"))

    def test_launch_command_has_correct_default_interface(self):
        args = self.parse_args("launch app")
        self.assertThat(args.interface, Equals("Auto"))

    def test_launch_command_can_specify_Qt_interface(self):
        args = self.parse_args("launch -i Qt app")
        self.assertThat(args.interface, Equals("Qt"))

    def test_launch_command_can_specify_Gtk_interface(self):
        args = self.parse_args("launch -i Gtk app")
        self.assertThat(args.interface, Equals("Gtk"))

    @patch('sys.stderr', new=StringIO())
    @expectedFailure
    def test_launch_command_fails_on_unknown_interface(self):
        self.parse_args("launch -i unknown app")

    def test_launch_command_has_correct_default_verbosity(self):
        args = self.parse_args("launch app")
        self.assertThat(args.verbose, Equals(False))

    def test_launch_command_can_specify_verbosity(self):
        args = self.parse_args("launch -v app")
        self.assertThat(args.verbose, Equals(1))

    def test_launch_command_can_specify_extra_verbosity(self):
        args = self.parse_args("launch -vv app")
        self.assertThat(args.verbose, Equals(2))
        args = self.parse_args("launch -v -v app")
        self.assertThat(args.verbose, Equals(2))

    def test_launch_command_stores_application(self):
        args = self.parse_args("launch app")
        self.assertThat(args.application, Equals(["app"]))

    def test_launch_command_stores_application_with_args(self):
        args = self.parse_args("launch app arg1 arg2")
        self.assertThat(args.application, Equals(["app", "arg1", "arg2"]))

    def test_launch_command_accepts_different_app_arg_formats(self):
        args = self.parse_args("launch app -s --long --key=val arg1 arg2")
        self.assertThat(args.application,
            Equals(["app", "-s", "--long", "--key=val", "arg1", "arg2"]))

    @patch('autopilot.have_vis', new=lambda: True)
    def test_vis_present_when_vis_module_installed(self):
        args = self.parse_args('vis')
        self.assertThat(args.mode, Equals("vis"))

    @patch('autopilot.have_vis', new=lambda: False)
    @patch('sys.stderr', new=StringIO())
    @expectedFailure
    def test_vis_not_present_when_vis_module_not_installed(self):
        self.parse_args('vis')

    @patch('autopilot.have_vis', new=lambda: True)
    def test_vis_default_verbosity(self):
        args = self.parse_args('vis')
        self.assertThat(args.verbose, Equals(False))

    @patch('autopilot.have_vis', new=lambda: True)
    def test_vis_single_verbosity(self):
        args = self.parse_args('vis -v')
        self.assertThat(args.verbose, Equals(1))

    @patch('autopilot.have_vis', new=lambda: True)
    def test_vis_double_verbosity(self):
        args = self.parse_args('vis -vv')
        self.assertThat(args.verbose, Equals(2))
        args = self.parse_args('vis -v -v')
        self.assertThat(args.verbose, Equals(2))

    def test_list_mode(self):
        args = self.parse_args('list foo')
        self.assertThat(args.mode, Equals("list"))

    def test_list_mode_accepts_suite_name(self):
        args = self.parse_args('list foo')
        self.assertThat(args.suite, Equals(["foo"]))

    def test_list_mode_accepts_many_suite_names(self):
        args = self.parse_args('list foo bar baz')
        self.assertThat(args.suite, Equals(["foo", "bar", "baz"]))

    def test_list_run_order_long_option(self):
        args = self.parse_args('list --run-order foo')
        self.assertThat(args.run_order, Equals(True))

    def test_list_run_order_short_option(self):
        args = self.parse_args('list -ro foo')
        self.assertThat(args.run_order, Equals(True))

    def test_list_no_run_order(self):
        args = self.parse_args('list foo')
        self.assertThat(args.run_order, Equals(False))

    def test_run_mode(self):
        args = self.parse_args('run foo')
        self.assertThat(args.mode, Equals("run"))

    def test_run_mode_accepts_suite_name(self):
        args = self.parse_args('run foo')
        self.assertThat(args.suite, Equals(["foo"]))

    def test_run_mode_accepts_many_suite_names(self):
        args = self.parse_args('run foo bar baz')
        self.assertThat(args.suite, Equals(["foo", "bar", "baz"]))

    def test_run_command_default_output(self):
        args = self.parse_args('run foo')
        self.assertThat(args.output, Equals(None))

    def test_run_command_path_output_short(self):
        args = self.parse_args('run -o /path/to/file foo')
        self.assertThat(args.output, Equals("/path/to/file"))

    def test_run_command_path_output_long(self):
        args = self.parse_args('run --output ../file foo')
        self.assertThat(args.output, Equals("../file"))

    def test_run_command_default_format(self):
        args = self.parse_args('run foo')
        self.assertThat(args.format, Equals("text"))

    def test_run_command_text_format_short_version(self):
        args = self.parse_args('run -f text foo')
        self.assertThat(args.format, Equals("text"))

    def test_run_command_text_format_long_version(self):
        args = self.parse_args('run --format text foo')
        self.assertThat(args.format, Equals("text"))

    def test_run_command_xml_format_short_version(self):
        args = self.parse_args('run -f xml foo')
        self.assertThat(args.format, Equals("xml"))

    def test_run_command_xml_format_long_version(self):
        args = self.parse_args('run --format xml foo')
        self.assertThat(args.format, Equals("xml"))

    @patch('sys.stderr', new=StringIO())
    @expectedFailure
    def test_run_command_unknown_format_short_version(self):
        self.parse_args('run -f unknown foo')

    @patch('sys.stderr', new=StringIO())
    @expectedFailure
    def test_run_command_unknown_format_long_version(self):
        self.parse_args('run --format unknown foo')

    def test_run_command_record_flag_default(self):
        args = self.parse_args("run foo")
        self.assertThat(args.record, Equals(False))

    def test_run_command_record_flag_short(self):
        args = self.parse_args("run -r foo")
        self.assertThat(args.record, Equals(True))

    def test_run_command_record_flag_long(self):
        args = self.parse_args("run --record foo")
        self.assertThat(args.record, Equals(True))

    def test_run_command_record_dir_flag_default(self):
        args = self.parse_args("run foo")
        self.assertThat(args.record_directory, Equals("/tmp/autopilot"))

    def test_run_command_record_dir_flag_short(self):
        args = self.parse_args("run -rd /path/to/dir foo")
        self.assertThat(args.record_directory, Equals("/path/to/dir"))

    def test_run_command_record_dir_flag_long(self):
        args = self.parse_args("run --record-directory /path/to/dir foo")
        self.assertThat(args.record_directory, Equals("/path/to/dir"))

    def test_run_default_verbosity(self):
        args = self.parse_args('run foo')
        self.assertThat(args.verbose, Equals(False))

    def test_run_single_verbosity(self):
        args = self.parse_args('run -v foo')
        self.assertThat(args.verbose, Equals(1))

    def test_run_double_verbosity(self):
        args = self.parse_args('run -vv foo')
        self.assertThat(args.verbose, Equals(2))
        args = self.parse_args('run -v -v foo')
        self.assertThat(args.verbose, Equals(2))