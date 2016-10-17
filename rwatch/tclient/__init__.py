#!/usr/bin/env python3.5
# coding=utf-8
# vim: set ts=4 sw=4 expandtab syntax=python:
"""

rwatch.tclient
Rainwatch > Torrent client abstraction functions

Copyright (c) 2016 J. Hipps / Neo-Retro Group
https://ycnrg.org/

@author     Jacob Hipps <jacob@ycnrg.org>
@repo       https://git.ycnrg.org/projects/YRW/repos/rainwatch

"""

import os
import sys
import re

from rwatch.logthis import *
from rwatch.util import *

from rwatch.tclient import deluge, rtorrent

tc_lut = { 'deluge': deluge.delcon, 'rtorrent': rtorrent.rtcon }

attr_tinfo = [
                'hash', 'name', 'path', 'base_path', 'time_added', 'comment', 'message', 'tracker_status',
                'tracker_host', 'total_size', 'completed_size', 'progress', 'eta', 'ratio', 'uploaded', 'downloaded',
                'upload_rate', 'download_rate', 'connected_peers', 'connected_seeds', 'total_peers', 'total_seeds',
                'private', 'state', 'time_active', 'file_count', 'piece_length', 'next_announce', 'tracker_url',
                'files', 'trackers'
             ]
attr_tinfo_files = [ 'path', 'index', 'offset', 'size', 'progress', 'priority' ]
attr_tinfo_trackers = [ 'fail_count', 'success_count', 'url', 'type', 'enabled' ]


class TorrentClient(object):
    """
    abstract class for interfacing with torrent clients
    """
    tor = None
    client_type = None
    connected = False

    def __init__(self, xconfig, client=None):
        """do constructive things"""
        if not client:
            client = xconfig.core['tclient'].lower()
        else:
            client = client.lower()

        # check if client is supported
        if client not in tc_lut:
            failwith(ER.OPT_BAD, "Invalid torrent client specification '%s'" % (client))

        # spawn torrent client
        self.client_type = client
        self.tor = tc_lut[client].fromXConfig(xconfig)
        self.connected = self.tor.connected

    def __getattr__(self, aname):
        """return reference to client object"""
        if hasattr(self.tor, aname):
            return getattr(self.tor, aname)
        else:
            return self._undefined(aname)

    def _undefined(self, aname):
        """capture unhandled method calls"""
        def _undef(**kwargs):
            kwlist = ', '.join(["%s=%s" % (x, kwargs[x]) for x in kwargs])
            logthis("Unhandled method call:", suffix="%s(%s)" % (aname, kwlist), loglevel=LL.WARNING)
        return _undef
