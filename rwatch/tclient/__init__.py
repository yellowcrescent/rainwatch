#!/usr/bin/env python
# coding=utf-8
###############################################################################
#
# tclient - rwatch/tclient/__init__.py
# Rainwatch: Torrent client abstraction functions
#
# @author   J. Hipps <jacob@ycnrg.org>
# @repo     https://bitbucket.org/yellowcrescent/rainwatch
#
# Copyright (c) 2016 J. Hipps / Neo-Retro Group
#
# https://ycnrg.org/
#
###############################################################################

import os
import sys
import re

from rwatch.logthis import *
from rwatch.util import *

import deluge
import rtorrent

tc_lut = { 'deluge': deluge.delcon, 'rtorrent': rtorrent.rtcon }

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
        if not tc_lut.has_key(client):
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
            kwlist = ','.join(map(lambda x: u"%s=%s" % (x,kwargs[x]), kwargs))
            logthis("Unhandled method call:", suffix=u"%s(%s)" % (aname, kwlist), loglevel=LL.WARNING)
        return _undef
