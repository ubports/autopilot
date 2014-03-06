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

from codecs import open
import fixtures
import os
import os.path
import sys
import logging
from shutil import rmtree
import subprocess
from tempfile import mkdtemp, mkstemp
from testtools.content import text_content
from textwrap import dedent

from autopilot.testcase import AutopilotTestCase


def remove_if_exists(path):
    if os.path.exists(path):
        if os.path.isdir(path):
            rmtree(path)
        else:
            os.remove(path)


logger = logging.getLogger(__name__)


class AutopilotRunTestBase(AutopilotTestCase):

    """The base class for the autopilot functional tests."""

    def setUp(self):
        super(AutopilotRunTestBase, self).setUp()
        self.base_path = self.create_empty_test_module()

    def create_empty_test_module(self):
        """Create an empty temp directory, with an empty test directory inside
        it.

        This method handles cleaning up the directory once the test completes.

        Returns the full path to the temp directory.

        """

        # create the base directory:
        base_path = mkdtemp()
        self.addDetail('base path', text_content(base_path))
        self.addCleanup(rmtree, base_path)

        # create the tests directory:
        os.mkdir(
            os.path.join(base_path, 'tests')
        )

        # make tests importable:
        open(
            os.path.join(
                base_path,
                'tests',
                '__init__.py'),
            'w').write('# Auto-generated file.')
        return base_path

    def run_autopilot(self, arguments, pythonpath="", use_script=False):
        environment_patch = _get_environment_patch(pythonpath)

        if use_script:
            arg = [sys.executable, self._write_setup_tools_script()]
        else:
            arg = [sys.executable, '-m', 'autopilot.run']

        environ = os.environ.copy()
        environ.update(environment_patch)

        logger.info("Starting autopilot command with:")
        logger.info("Autopilot command = %s", ' '.join(arg))
        logger.info("Arguments = %s", arguments)
        logger.info("CWD = %r", self.base_path)

        arg.extend(arguments)
        process = subprocess.Popen(
            arg,
            cwd=self.base_path,
            env=environ,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
        )

        stdout, stderr = process.communicate()
        retcode = process.poll()

        self.addDetail('retcode', text_content(str(retcode)))
        self.addDetail(
            'stdout',
            text_content(stdout)
        )
        self.addDetail(
            'stderr',
            text_content(stderr)
        )

        return (retcode, stdout, stderr)

    def create_test_file(self, name, contents):
        """Create a test file with the given name and contents.

        'name' must end in '.py' if it is to be importable.
        'contents' must be valid python code.

        """
        open(
            os.path.join(
                self.base_path,
                'tests',
                name),
            'w',
            encoding='utf8').write(contents)

    def _write_setup_tools_script(self):
        """Creates a python script that contains the setup entry point."""
        base_path = mkdtemp()
        self.addCleanup(rmtree, base_path)

        script_file = os.path.join(base_path, 'autopilot')
        open(script_file, 'w').write(load_entry_point_script)

        return script_file


class TempDesktopFile(fixtures.Fixture):
    def setUp(self):
        super(TempDesktopFile, self).setUp()
        path_created = TempDesktopFile._ensure_desktop_dir_exists()
        self._desktop_file_path = self._create_desktop_file()

        self.addCleanup(
            TempDesktopFile._remove_desktop_file_components,
            path_created,
            self._desktop_file_path,
        )

    def get_desktop_file_path(self):
        return self._desktop_file_path

    @staticmethod
    def _ensure_desktop_dir_exists():
        desktop_file_dir = TempDesktopFile._desktop_file_dir()
        if not os.path.exists(desktop_file_dir):
            return TempDesktopFile._create_desktop_file_dir(desktop_file_dir)
        return ''

    @staticmethod
    def _desktop_file_dir():
        return os.path.join(
            os.getenv('HOME'),
            '.local',
            'share',
            'applications'
        )

    @staticmethod
    def _create_desktop_file_dir(desktop_file_dir):
        """Create the directory specified.

        Returns the component of the path that did not exist, or the empty
        string if the entire path already existed.

        """
        # We might be creating more than just the leaf directory, so we need to
        # keep track of what doesn't already exist and remove it when we're
        # done. Defaults to removing the full path
        path_to_delete = ""
        if not os.path.exists(desktop_file_dir):
            path_to_delete = desktop_file_dir
        full_path, leaf = os.path.split(desktop_file_dir)
        while leaf != "":
            if not os.path.exists(full_path):
                path_to_delete = full_path
            full_path, leaf = os.path.split(full_path)

        try:
            os.makedirs(desktop_file_dir)
        except OSError:
            logger.warning("Directory already exists: %s" % desktop_file_dir)
        return path_to_delete

    @staticmethod
    def _remove_desktop_file_components(created_path, created_file):
        if created_path != "":
            rmtree(created_path)
        else:
            os.remove(created_file)

    @staticmethod
    def _create_desktop_file():
        _, tmp_file_path = mkstemp(
            suffix='.desktop',
            dir=TempDesktopFile._desktop_file_dir()
        )
        with open(tmp_file_path, 'w') as desktop_file:
            desktop_file.write(
                dedent("""\
                [Desktop Entry]
                Type=Application
                Exec=Not important
                Path=Not important
                Name=Test app
                Icon=Not important""")
            )
        return tmp_file_path


def _get_environment_patch(pythonpath):
    environment_patch = dict(DISPLAY=':0')

    ap_base_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__),
            '..',
            '..',
            '..'
        )
    )

    pythonpath_additions = []
    if pythonpath is not None:
        pythonpath_additions.append(pythonpath)
    if not os.getcwd().startswith('/usr/'):
        pythonpath_additions.append(ap_base_path)
    environment_patch['PYTHONPATH'] = ":".join(pythonpath_additions)

    return environment_patch


load_entry_point_script = """\
#!/usr/bin/python
__requires__ = 'autopilot==1.4.0'
import sys
from pkg_resources import load_entry_point

if __name__ == '__main__':
    sys.exit(
        load_entry_point('autopilot==1.4.0', 'console_scripts', 'autopilot')()
    )
"""
