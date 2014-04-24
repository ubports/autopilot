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

"""Private Package containing filters used in finding useful dbus
connections.

"""

from __future__ import absolute_import

import dbus
import logging
import os
import psutil

from autopilot.introspection.backends import DBusAddress
from autopilot.introspection.dbus import get_classname_from_path
from autopilot.introspection.utilities import _get_bus_connections_pid


logger = logging.getLogger(__name__)


class _cached_get_child_pids(object):
    """Get a list of all child process Ids, for the given parent.

    Since we call this often, and it's a very expensive call, we optimise this
    such that the return value will be cached for each scan through the dbus
    bus.

    Calling reset_cache() at the end of each dbus scan will ensure that you get
    fresh values on the next call.
    """

    def __init__(self):
        self._cached_result = None

    def __call__(self, pid):
        if self._cached_result is None:
            self._cached_result = [
                p.pid for p in psutil.Process(pid).get_children(recursive=True)
            ]
        return self._cached_result

    def reset_cache(self):
        self._cached_result = None


_get_child_pids = _cached_get_child_pids()


class MatchesConnectionHasAppName(object):
    @classmethod
    def priority(cls):
        return 0  # LOW

    @classmethod
    def matches(cls, dbus_connection, params):
        """Returns True if dbus_connection has the required application name.

        Can be provided an object_path but defaults to 'AUTOPILOT_PATH' if not
        provided.

        This filter should only activated if the application_name is provided
        in the search criteria.

        :raises KeyError if the 'application_name' parameter isn't passed in
            params

        """
        requested_app_name = params['application_name']
        object_path = params.get(object_path, AUTOPILOT_PATH)
        bus, connection_name = dbus_connection

        dbus_object = cls._get_dbus_address_object(
            connection_name,
            object_path,
            bus
        )
        app_name = cls._get_application_name_from_dbus_address(dbus_object)
        return app_name == requested_app_name

    @classmethod
    def _get_dbus_address_object(cls, connection_name, object_path, bus):
        return DBusAddress(bus, connection_name, object_path)

    @classmethod
    def _get_application_name_from_dbus_address(cls, dbus_address):
        """Return the application name from a dbus_address object."""
        return get_classname_from_path(
            dbus_address.introspection_iface.GetState('/')[0][0]
        )


class MatchesConnectionHasPid(object):

    @classmethod
    def priority(cls):
        return 0

    @classmethod
    def matches(cls, dbus_connection, params):
        """Match a connection based on the connections pid.

        :raises KeyError: if the pid parameter isn't passed in params.

        """
        pid = params['pid']
        bus, connection_name = dbus_connection

        if cls._should_ignore_pid(bus, connection_name, pid):
            return False

        try:
            bus_pid = _get_bus_connections_pid(bus, connection_name)
        except dbus.DBusException as e:
            logger.info(
                "dbus.DBusException while attempting to get PID for %s: %r" %
                (connection_name, e))
            return False

        eligible_pids = [pid] + _get_child_pids(pid)
        return bus_pid in eligible_pids

    @classmethod
    def _should_ignore_pid(cls, bus, connection_name, pid):
        if (
            connection_name == 'org.freedesktop.DBus'
            or cls._bus_pid_is_our_pid(bus, connection_name, pid)
        ):
            return True
        return False

    @classmethod
    def _bus_pid_is_our_pid(cls, bus, connection_name, pid):
        """Returns True if this processes pid is the same as the supplied bus
        connections pid.

        """
        try:
            bus_pid = _get_bus_connections_pid(bus, connection_name)
            return bus_pid == os.getpid()
        except dbus.DBusException:
            return False


class MatchesConnectionHasPathWithAPInterface(object):

    @classmethod
    def priority(cls):
        return 0

    @classmethod
    def matches(cls, dbus_connection, params):
        """Ensure the connection has the path that we expect to be there.

        :raises ValueError: if the path parameter isn't included in params.

        """
        try:
            bus, connection_name = dbus_connection
            path = params['path']
            obj = bus.get_object(connection_name, path)
            dbus.Interface(
                obj,
                'com.canonical.Autopilot.Introspection'
            ).GetVersion()
            return True
        except KeyError:
            raise ValueError("Filter was expecting 'path' parameter")
        except dbus.DBusException:
            return False


_param_to_filter_map = dict(
    application_name=MatchesConnectionHasAppName,
    pid=MatchesConnectionHasPid,
    path=MatchesConnectionHasPathWithAPInterface,
)
