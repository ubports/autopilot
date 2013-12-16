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

"""Base module for application launchers."""

import fixtures
import json
import logging
import os
import psutil
import subprocess
import signal
from time import sleep
from testtools.content import content_from_file, text_content

from autopilot.application._environment import (
    _call_upstart_with_args,
    GtkApplicationEnvironment,
    QtApplicationEnvironment,
    UpstartApplicationEnvironment,
)


logger = logging.getLogger(__name__)


class ApplicationLauncher(fixtures.Fixture):
    """A class that knows how to launch an application with a certain type of
    introspection enabled.

    """
    def __init__(self, case_addDetail):
        self.case_addDetail = case_addDetail
        super(ApplicationLauncher, self).__init__()

    def launch(self, *arguments):
        raise NotImplementedError("Sub-classes must implement this method.")


class ClickApplicationLauncher(ApplicationLauncher):
    def __init__(self, case_addDetail, **kwargs):
        super(ClickApplicationLauncher, self).__init__(case_addDetail)

        self.emulator_base = kwargs.pop('emulator_base', None)
        self.dbus_bus = kwargs.pop('dbus_bus', 'session')

        _raise_if_not_empty(kwargs)

    def launch(self, package_id, app_name):
        app_id = _get_click_app_id(package_id, app_name)

        _app_env = self.useFixture(UpstartApplicationEnvironment())
        _app_env._app_env.prepare_environment(
            app_id,
            app_name,
        )

        self._attach_application_logs_at_cleanup(app_id)
        pid = _launch_click_app(app_id)
        self.addCleanup(self._kill_pid, pid)

        logger.info(
            "Click package %s has been launched with PID %d",
            self.app_id,
            pid
        )

        return pid

    def _attach_application_logs_at_cleanup(self, app_id):
        self.addCleanup(
            lambda: self.case_addDetail(
                "Application Log",
                _get_click_application_log_content_object(app_id)
            )
        )


class NormalApplicationLauncher(ApplicationLauncher):
    def __init__(self, case_addDetail, **kwargs):
        super(NormalApplicationLauncher, self).__init__(case_addDetail)
        self.app_hint = kwargs.pop('app_type', None)
        self.cwd = kwargs.pop('launch_dir', None)
        self.capture_output = kwargs.pop('capture_output', True)

        self.dbus_bus = kwargs.pop('dbus_bus', 'session')
        self.emulator_base = kwargs.pop('emulator_base', None)

        _raise_if_not_empty(kwargs)

    def launch(self, application, *arguments):
        app_path = _get_application_path(application)

        app_env = self.useFixture(
            _get_application_environment(self.app_hint, app_path)
        )
        app_path, arguments = app_env.prepare_environment(
            app_path,
            list(arguments),
        )
        process = launch_process(
            app_path,
            arguments,
            self.capture_output,
            cwd=self.cwd,
        )

        self.addCleanup(self._kill_process_and_attach_logs, process)

        return process.pid

    def _kill_process_and_attach_logs(self, process):
        stdout, stderr, return_code = _kill_process(process)
        self.case_addDetail(
            'process-return-code',
            text_content(str(return_code))
        )
        self.case_addDetail('process-stdout', text_content(stdout))
        self.case_addDetail('process-stderr', text_content(stderr))


def launch_process(application, args, capture_output, **kwargs):
    """Launch an autopilot-enabled process and return the process object."""
    commandline = [application]
    commandline.extend(args)
    logger.info("Launching process: %r", commandline)
    cap_mode = None
    if capture_output:
        cap_mode = subprocess.PIPE
    process = subprocess.Popen(
        commandline,
        stdin=subprocess.PIPE,
        stdout=cap_mode,
        stderr=cap_mode,
        close_fds=True,
        preexec_fn=os.setsid,
        universal_newlines=True,
        **kwargs
    )
    return process


def _is_process_running(pid):
    return psutil.pid_exists(pid)


def _launch_click_app(app_id):
    subprocess.check_output([
        "/sbin/start",
        "application",
        "APP_ID={}".format(app_id),
    ])

    return _get_click_app_pid(app_id)


def _get_click_app_status(app_id):
    _call_upstart_with_args(
        "status",
        "application-click",
        "APP_ID={}".format(app_id)
    )


def _get_click_application_log_content_object(app_id):
    log_dir = os.path.expanduser('~/.cache/upstart/')
    log_name = 'application-click-{}.log'.format(app_id)
    log_path = os.path.join(log_dir, log_name)

    return content_from_file(log_path)


def _get_click_app_id(package_id, app_name=None):
    for pkg in _get_click_manifest():
        if pkg['name'] == package_id:
            if app_name is None:
                app_name = pkg['hooks'].keys()[0]
            elif app_name not in pkg['hooks']:
                raise RuntimeError(
                    "Application '{}' is not present within the click "
                    "package '{}'.".format(app_name, package_id))

            return "{0}_{1}_{2}".format(package_id, app_name, pkg['version'])
    raise RuntimeError(
        "Unable to find package '{}' in the click manifest."
        .format(package_id)
    )


def _get_click_manifest():
    """Return the click package manifest as a python list."""
    # get the whole click package manifest every time - it seems fast enough
    # but this is a potential optimisation point for the future:
    click_manifest_str = subprocess.check_output(
        ["click", "list", "--manifest"]
    )
    return json.loads(click_manifest_str)


def _get_click_app_pid(app_id):
    for i in range(10):
        try:
            list_output = _get_click_app_status(app_id)
        except subprocess.CalledProcessError:
            # application not started yet.
            pass
        else:
            for line in list_output.split('\n'):
                if app_id in line and "start/running" in line:
                    return int(line.split()[-1])
        # give the app time to launch - maybe this is not needed?:
        sleep(1)
    else:
        raise RuntimeError(
            "Could not find autopilot interface for click package"
            " '{}' after 10 seconds.".format(app_id)
        )


def _kill_pid(pid):
    """Kill the process with the specified pid."""
    logger.info("waiting for process to exit.")
    try:
        logger.info("Killing process %d", pid)
        os.killpg(pid, signal.SIGTERM)
    except OSError:
        logger.info("Appears process has already exited.")
    for i in range(10):
        if not _is_process_running(pid):
            break
        if i == 9:
            logger.info(
                "Killing process group, since it hasn't exited after "
                "10 seconds."
            )
            os.killpg(pid, signal.SIGKILL)
        sleep(1)


def _get_application_environment(app_hint, app_path):
    if app_hint is not None:
        return _get_app_env_from_string_hint(app_hint)
    elif app_path is not None:
        return get_application_launcher_wrapper(app_path)


def get_application_launcher_wrapper(app_path):
    """Return an instance of :class:`ApplicationLauncher` that knows how to
    launch the application at 'app_path'.
    """
    # TODO: this is a teeny bit hacky - we call ldd to check whether this
    # application links to certain library. We're assuming that linking to
    # libQt* or libGtk* means the application is introspectable. This excludes
    # any non-dynamically linked executables, which we may need to fix further
    # down the line.

    try:
        ldd_output = subprocess.check_output(
            ["ldd", app_path],
            universal_newlines=True
        ).strip().lower()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(e)
    if 'libqtcore' in ldd_output or 'libqt5core' in ldd_output:
        return QtApplicationEnvironment()
    elif 'libgtk' in ldd_output:
        return GtkApplicationEnvironment()
    return None


def _get_application_path(application):
    try:
        return subprocess.check_output(
            ['which', application],
            universal_newlines=True
        ).strip()
    except subprocess.CalledProcessError as e:
        raise ValueError(
            "Unable to find path for application {app}: {reason}"
            .format(app=application, reason=str(e))
        )


def _get_app_env_from_string_hint(hint):
    hint = hint.lower()
    if hint == 'qt':
        return QtApplicationEnvironment()
    elif hint == 'gtk':
        return GtkApplicationEnvironment()
    return None


def _kill_process(process):
    """Kill the process, and return the stdout, stderr and return code."""
    stdout = ""
    stderr = ""
    logger.info("waiting for process to exit.")
    try:
        logger.info("Killing process %d", process.pid)
        os.killpg(process.pid, signal.SIGTERM)
    except OSError:
        logger.info("Appears process has already exited.")
    for i in range(10):
        tmp_out, tmp_err = process.communicate()
        stdout += tmp_out
        stderr += tmp_err
        if not _is_process_running(process.pid):
            break
        if i == 9:
            logger.info(
                "Killing process group, since it hasn't exited after "
                "10 seconds."
            )
            os.killpg(process.pid, signal.SIGKILL)
        sleep(1)
    return stdout, stderr, process.returncode


def _raise_if_not_empty(kwargs):
    if kwargs:
        arglist = [repr(k) for k in kwargs.keys()]
        arglist.sort()
        raise ValueError(
            "Unknown keyword arguments: %s." % (', '.join(arglist))
        )
