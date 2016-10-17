#!/usr/bin/env python3.5
# coding=utf-8
# vim: set ts=4 sw=4 expandtab syntax=python:
"""

rwatch
Rainwatch
Automated download manager for seedboxes

Copyright (c) 2016 J. Hipps / Neo-Retro Group
https://ycnrg.org/

@author     Jacob Hipps <jacob@ycnrg.org>
@repo       https://git.ycnrg.org/projects/YRW/repos/rainwatch

"""

from rwatch.util import XConfig, git_info_raw
from rwatch.logthis import *

__version__ = "0.11.18"
__date__ = "15 Oct 2016"

__all__ = ['gitinfo', 'defaults', '__version__', '__date__']

gitinfo = git_info_raw()

defaults = {
            'run': {
                'torid': None,
                'quiet': False,
                'list': False,
                'json': False,
                'full': False,
                'srv': False,
                'fdebug': False,
                'locale': None,
                'move': None
            },
            'core': {
                'loglevel': LL.INFO,
                'logfile': "rainwatch.log",
                'rules': "rainwatch.rules",
                'tclient': "deluge"
            },
            'xfer': {
                'hostname': None,
                'user': None,
                'port': 22,
                'basepath': '',
                'keyfile': None
            },
            'notify': {
                'hostname': None,
                'user': None,
                'icon': ""
            },
            'srv': {
                'pidfile': "rainwatch.pid",
                'url': "http://localhost:4464",
                'iface': "0.0.0.0",
                'port': 4464,
                'nofork': False,
                'debug': False,
                'shared_key': ''
            },
            'redis': {
                'host': "localhost",
                'port': 6379,
                'db': 11,
                'prefix': "rainwatch"
            },
            'xmpp': {
                'user': None,
                'pass': None,
                'server': None,
                'sendto': None
            },
            'deluge': {
                'user': "",
                'pass': "",
                'hostname': "localhost",
                'port': 58846
            },
            'rtorrent': {
                'uri': "http://localhost:5000"
            },
            'web': {
                'bw_graph': None
            }
        }
