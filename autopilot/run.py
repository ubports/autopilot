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


from __future__ import absolute_import

#
# NOTE: You MUST NOT import any autopilot modules at global scope, because it
# cases autopilot to be inserted into sys.modules before we've had a chance to
# patch sys.path, which in turn means we cannot use autopilot to run our own
# tests.

from codecs import open
from datetime import datetime
import logging
import os
import os.path
from os import putenv
from os.path import isabs, exists
from platform import node
from random import shuffle
import subprocess
import sys
from unittest.loader import TestLoader
from unittest import TestSuite

from testtools import iterate_tests
from testtools import TextTestResult


_output_stream = None


def list_tests(args):
    """Print a list of tests we find inside autopilot.tests."""
    num_tests = 0
    total_title = "tests"
    test_suite = load_test_suite_from_name(args.suite)

    if args.run_order:
        test_list_fn = lambda: iterate_tests(test_suite)
    else:
        test_list_fn = lambda: sorted(iterate_tests(test_suite), key=id)

    if args.suites:
        from collections import OrderedDict

        suite_names = ["%s.%s" % (t.__module__, t.__class__.__name__)
                       for t in test_list_fn()]
        unique_suite_names = list(OrderedDict.fromkeys(suite_names).keys())
        num_tests = len(unique_suite_names)
        total_title = "suites"
        print("    %s" % ("\n    ".join(unique_suite_names)))
    else:
        for test in test_list_fn():
            has_scenarios = (hasattr(test, "scenarios")
                             and type(test.scenarios) is list)
            if has_scenarios:
                num_tests += len(test.scenarios)
                print(" *%d %s" % (len(test.scenarios), test.id()))
            else:
                num_tests += 1
                print("    " + test.id())
    print("\n\n %d total %s." % (num_tests, total_title))


def run_tests(args):
    """Run tests, using input from `args`."""
    test_suite = load_test_suite_from_name(args.suite)

    if args.random_order:
        shuffle(test_suite._tests)
        print("Running tests in random order")

    import autopilot.globals

    if args.record_directory:
        args.record = True

    if args.record:
        if not args.record_directory:
            args.record_directory = '/tmp/autopilot'
        call_ret_code = subprocess.call(
            ['which', 'recordmydesktop'],
            stdout=subprocess.PIPE
        )
        if call_ret_code != 0:
            print("ERROR: The application 'recordmydesktop' needs to be "
                  "installed to record failing jobs.")
            exit(1)
        autopilot.globals.configure_video_recording(True,
                                                    args.record_directory,
                                                    args.record_options)

    if args.verbose:
        autopilot.globals.set_log_verbose(True)

    setup_logging(args.verbose)
    runner = construct_test_runner(args)
    test_result = runner.run(test_suite, args.failfast)
    if not test_result.wasSuccessful():
        exit(1)


def setup_logging(verbose):
    """Configure the root logger and verbose logging to stderr"""
    from autopilot.utilities import LogFormatter
    from autopilot import get_version_string
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    if verbose == 0:
        root_logger.addHandler(logging.NullHandler())
    if verbose >= 1:
        formatter = LogFormatter()
        stderr_handler = logging.StreamHandler(stream=sys.stderr)
        stderr_handler.setFormatter(formatter)
        root_logger.addHandler(stderr_handler)
    if verbose >= 2:
        from autopilot.utilities import DebugLogFilter
        DebugLogFilter.debug_log_enabled = True
    #log autopilot version
    root_logger.info(get_version_string())


def construct_test_runner(args):
    kwargs = dict(
        stdout=get_output_stream(args),
        output_format=get_output_format(args.format),
    )

    return ConfigurableTestRunner(**kwargs)


def get_output_format(format):
    """Return a Result object for each format we support."""
    from autopilot.testresult import AutopilotVerboseResult

    if format == "text":
        return type('VerboseTextTestResult', (TextTestResult,),
                    dict(AutopilotVerboseResult.__dict__))

    elif format == "xml":
        from junitxml import JUnitXmlResult
        return type('VerboseXmlResult', (JUnitXmlResult,),
                    dict(AutopilotVerboseResult.__dict__))

    raise KeyError("Unknown format name '%s'" % format)


def get_output_stream(args):
    global _output_stream

    if _output_stream is None:
        if args.output:
            path = os.path.dirname(args.output)
            if path != '' and not os.path.exists(path):
                os.makedirs(path)
            log_file = args.output
            if os.path.isdir(log_file):
                default_log = "%s_%s.log" % (
                    node(),
                    datetime.now().strftime("%d.%m.%y-%H%M%S")
                )
                log_file = os.path.join(log_file, default_log)
                print("Using default log filename: %s " % default_log)
            if args.format == 'xml':
                _output_stream = open(log_file, 'w')
            else:
                _output_stream = open(log_file, 'w', encoding='utf-8')
        else:
            _output_stream = sys.stdout
    return _output_stream


class ConfigurableTestRunner(object):
    """A configurable test runner class.

    This class alows us to configure the output format and whether of not we
    collect coverage information for the test run.

    """

    def __init__(self, stdout, output_format):
        self.stdout = stdout
        self.result_class = output_format

    def run(self, test, failfast=False):
        "Run the given test case or test suite."
        result = self.result_class(self.stdout)
        result.startTestRun()
        result.failfast = failfast
        try:
            test_result = test.run(result)
        finally:
            result.stopTestRun()
        return test_result


def load_test_suite_from_name(test_names):
    """Returns a test suite object given a dotted test names."""
    loader = TestLoader()
    if isinstance(test_names, str):
        test_names = list(test_names)
    elif not isinstance(test_names, list):
        raise TypeError("test_names must be either a string or list, not %r"
                        % (type(test_names)))

    tests = []
    test_package_locations = []
    for test_name in test_names:
        top_level_pkg = test_name.split('.')[0]
        package = __import__(top_level_pkg)
        package_parent_path = os.path.abspath(
            os.path.join(
                os.path.dirname(package.__file__),
                '..'
            )
        )
        if package_parent_path not in test_package_locations:
            test_package_locations.append(package_parent_path)
        tests.append(
            loader.discover(top_level_pkg, top_level_dir=package_parent_path)
        )
    all_tests = TestSuite(tests)

    test_dirs = ", ".join(sorted(test_package_locations))
    print("Loading tests from: %s\n" % test_dirs)
    sys.stdout.flush()

    requested_tests = {}
    for test in iterate_tests(all_tests):
        # The test loader returns tests that start with 'unittest.loader' if
        # for whatever reason the test failed to load. We run the tests without
        # the built-in exception catching turned on, so we can get at the
        # raised exception, which we print, so the user knows that something in
        # their tests is broken.
        if test.id().startswith('unittest.loader'):
            test_id = test._testMethodName
            try:
                test.debug()
            except Exception as e:
                print(e)
        else:
            test_id = test.id()
        if any([test_id.startswith(name) for name in test_names]):
            requested_tests[test_id] = test

    return TestSuite(requested_tests.values())


def maybe_patch_python_path():
    """Prepend the current directory to sys.path to ensure that we can load &
    run autopilot tests if the caller is in the parent directory, but only if
    we're not somewhere in /usr/...

    """
    if os.getcwd() not in sys.path and not os.getcwd().startswith('/usr/'):
        sys.path.insert(0, os.getcwd())


def launch_app(args):
    """Launch an application, with introspection support."""
    from autopilot.introspection import (
        launch_application,
        get_application_launcher,
        get_application_launcher_from_string_hint,
    )

    setup_logging(args.verbose)
    app_name = args.application[0]
    if not isabs(app_name) or not exists(app_name):
        try:
            app_name = subprocess.check_output(["which", app_name],
                                               universal_newlines=True).strip()
        except subprocess.CalledProcessError:
            print("Error: cannot find application '%s'" % (app_name))
            exit(1)

    # We now have a full path to the application.
    launcher = None
    if args.interface == 'Auto':
        try:
            launcher = get_application_launcher(app_name)
        except RuntimeError as e:
            print("Error detecting launcher: %s" % str(e))
            print("(Perhaps use the '-i' argument to specify an interface.)")
            exit(1)
    else:
        launcher = get_application_launcher_from_string_hint(args.interface)
    if launcher is None:
        print("Error: Could not determine introspection type to use for "
              "application '%s'." % app_name)
        print("(Perhaps use the '-i' argument to specify an interface.)")
        exit(1)

    try:
        launch_application(launcher, *args.application, capture_output=False)
    except RuntimeError as e:
        print("Error: " + str(e))
        exit(1)


def run_vis(args):
    setup_logging(args.verbose)
    # importing this requires that DISPLAY is set. Since we don't always want
    # that requirement, do the import here:
    from autopilot.vis import vis_main

    # XXX - in quantal, overlay scrollbars make this process consume 100% of
    # the CPU. It's a known bug:
    #
    # https://bugs.launchpad.net/ubuntu/quantal/+source/qt4-x11/+bug/1005677
    #
    # Once that's been fixed we can remove the following line:
    #
    putenv('LIBOVERLAY_SCROLLBAR', '0')
    vis_main()


def main():
    maybe_patch_python_path()

    from autopilot import parse_arguments
    args = parse_arguments()
    if args.mode == 'list':
        list_tests(args)
    elif args.mode == 'run':
        run_tests(args)
    elif args.mode == 'vis':
        run_vis(args)
    elif args.mode == 'launch':
        launch_app(args)


if __name__ == "__main__":
    main()
