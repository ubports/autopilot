# -*- Mode: Python; coding: utf-8; indent-tabs-mode: nil; tab-width: 4 -*-
# Copyright 2012 Canonical
# Author: Chris Lee
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#

from __future__ import absolute_import

import dbus
import pydot
from autopilot.introspection.unity import get_state_by_path

NEXT_NODE_ID=1
NODE_BLACKLIST=["Result"]


def string_rep(dbus_type):
    """Get a string representation of various dbus types."""
    if type(dbus_type) == dbus.Boolean:
        return repr(bool(dbus_type))
    if type(dbus_type) == dbus.String:
        return dbus_type.encode('ascii', errors='ignore')
    if type(dbus_type) in (dbus.Int16, dbus.UInt16, dbus.Int32, dbus.UInt32,
                           dbus.Int64, dbus.UInt64):
        return repr(int(dbus_type))
    if type(dbus_type) == dbus.Double:
        return repr(float(dbus_type))
    if type(dbus_type) == dbus.Array:
        return ', '.join([string_rep(i) for i in dbus_type])
    else:
        return repr(dbus_type)


def escape(s):
    """Escape a string so it can be use in a dot label."""
    return pydot.quote_if_necessary(s).replace('<','\\<').replace('>', '\\>').\
           replace("'", "\\'")


def traverse_tree(state, parent, graph):
    """Recursively traverse state tree, building dot graph as we go."""
    global NEXT_NODE_ID
    lbl = parent.get_comment() + "|"
    # first, set labels for this node:
    bits = ["%s=%s" % (k, string_rep(state[k])) for k in sorted(state.keys())
            if k != 'Children']
    lbl += "\l".join(bits)
    parent.set_label(escape('"{' + lbl + '}"'))
    if 'Children' in state:
        # Add all array nodes as children of this node.
        for child_name, child_state in state['Children']:
            if child_name in NODE_BLACKLIST:
                continue
            child = pydot.Node(str(NEXT_NODE_ID))
            NEXT_NODE_ID+=1
            child.set_comment(child_name)
            graph.add_node(child)
            graph.add_edge(pydot.Edge(parent, child))

            traverse_tree(child_state, child, graph)


def get_vis_graph():
    introspection_tree = get_state_by_path('/')
    graph = pydot.Dot()
    graph.set_simplify(False)
    graph.set_node_defaults(shape='Mrecord')
    graph.set_fontname('Ubuntu')
    graph.set_fontsize('10')

    gnode_unity = pydot.Node("Unity")
    gnode_unity.set_comment("Unity")
    traverse_tree(introspection_tree[0], gnode_unity, graph)

    return graph