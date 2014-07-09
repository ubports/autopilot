# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
#
# Autopilot Functional Test Tool
# Copyright (C) 2014 Canonical
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

from fixtures import Fixture


class FixtureWithDirectAddDetail(Fixture):

    """A test fixture that has a 'caseAddDetail' method that corresponds
    to the addDetail method of the test case in use.

    You must derive from this class in order to add detail objects to tests
    from within cleanup actions.

    """

    def __init__(self, caseAddDetail):
        """Create the fixture.

        :param caseAddDetail: A closure over the testcase's addDetail
            method, or a similar substitution method.
        """
        self.caseAddDetail = caseAddDetail
