#!/usr/bin/env python
# coding=utf-8
###############################################################################
#
# rtorrent - rwatch/tclient/rtorrent.py
# Rainwatch: rTorrent RPC interface functions
#
# @author   J. Hipps <jacob@ycnrg.org>
# @repo     https://bitbucket.org/yellowcrescent/rainwatch
#
# Copyright (c) 2016 J. Hipps / Neo-Retro Group
#
# https://ycnrg.org/
#
###############################################################################

import sys
import os
import re
import json
import signal
import optparse
import operator
import time
import collections
import xmlrpclib
from urlparse import urlparse

from rwatch.logthis import C,LL,logthis,ER,failwith,loglevel,print_r,exceptionHandler

class multicall(collections.deque):
    """RPC system.multicall wrapper"""
    xrpc = None

    def __init__(self, rpc):
        super(self.__class__, self).__init__()
        self.xrpc = rpc

    def __getattr__(self, aname):
        return multicallsc(self, aname)

    def queue(self, methodName, params=None):
        """enqueue a function call"""
        # ensure param semi-sanity
        if params is None:
            params = []
        elif not (isinstance(params, list) or isinstance(params, tuple)):
            params = [params]
        self.append({ 'methodName': methodName, 'params': params })
        # return stack index
        return self.__len__() - 1

    def q(self, methodName, params=None):
        """enqueue a function call; like queue(), but chainable"""
        if params is None:
            params = []
        elif not (isinstance(params, list) or isinstance(params, tuple)):
            params = [params]
        self.append({ 'methodName': methodName, 'params': params })
        # return self to allow chaining
        return self

    def run(self):
        """send queued commands to the server for execution"""
        rez = self.xrpc.system.multicall(list(self))
        self.clear()
        ov = {}
        for ri,rr in enumerate(rez):
            ov[ri] = rr[0]
        return tuple(ov.values())

class multicallsc(object):
    """multicall helper metaclass"""
    def __init__(self, mcp, fname):
        self.__mcp = mcp
        self.__fname = fname

    def __call__(self, *pargs):
        return self.__mcp.queue(self.__fname, pargs)

    def __getattr__(self, aname):
        return multicallsc(self.__mcp, self.__fname + "." + aname)


class rtcon:
    """class for handling rTorrent RPC comms"""
    xcon = None
    connected = False
    client_version = None
    libtor_version = None
    api_version = None

    @classmethod
    def fromXConfig(cls, xconfig):
        """build rTorrent client from global XConfig"""
        return cls(uri=xconfig.rtorrent['uri'])

    def __init__(self, uri, abortfail=True):
        """connect to deluged and authenticate"""
        logthis("Connecting to rTorrent RPC via",suffix=uri,loglevel=LL.INFO)
        self.xcon = xmlrpclib.ServerProxy(uri)
        mcx = multicall(self.xcon)
        try:
            self.client_version,self.api_version,self.libtor_version = mcx.q('system.client_version').q('system.api_version').q('system.library_version').run()
        except Exception as e:
            logthis("Failed to connect to rTorrent:",suffix=e,loglevel=LL.ERROR)
            if abortfail:
                failwith(ER.CONF_BAD, "Connection to rTorrent failed. Aborting.")
            else:
                return
        logthis("Connected to rTorrent OK",ccode=C.GRN,loglevel=LL.INFO)
        logthis("rTorrent %s (libtorrent %s)" % (self.client_version, self.libtor_version), loglevel=LL.INFO)
        self.connected = True

    def getTorrent(self, torid):
        """get info on a particular torrent"""
        try:
            return self.xcon.call('core.get_torrent_status',torid,[])
        except Exception as e:
            logthis("Error calling core.get_torrent_status:",suffix=e,loglevel=LL.ERROR)
            return False

    def getTorrentList(self, filter=None):
        """get list of torrents"""
        try:
            tlist = self.xcon.d.multicall(("main",'d.name=','d.hash=','d.completed_bytes=','d.size_bytes=','d.creation_date=','d.complete=','d.is_active=','d.is_hash_checking=','d.state='))
        except Exception as e:
            logthis("Error calling d.multicall:",suffix=e,loglevel=LL.ERROR)
            return False

        ttv = {}
        for tt in tlist:
            try:
                ttracker = re.sub(':[0-9]+$','',urlparse(self.xcon.t.get_url(tt[1],0)).netloc)
            except:
                ttracker = None
            ttv[tt[1]] = { 'name': tt[0], 'tracker_host': ttracker, 'time_added': tt[4], 'progress': float(tt[2] / tt[3]) * 100.0, 'eta': None, 'state': self.__statusLookup(self,*tt[5:8]), 'total_size': tt[3], 'total_done': tt[2] }

        return ttv

    def renameFolder(self, torid, newname):
        """rename torrent directory name"""
        # first, get info on this torrent
        torinfo = self.xcon.call('core.get_torrent_status',torid,[])

        # Check if the dir is the same as torrent name
        if os.path.isdir(torinfo['save_path'] + '/' + torinfo['name']):
            fdir = torinfo['save_path'] + '/' + torinfo['name']
        elif os.path.isdir(os.path.dirname(torinfo['save_path'] + '/' + torinfo['files'][0]['path'])):
            fdir = os.path.dirname(torinfo['save_path'] + '/' + torinfo['files'][0]['path'])
        else:
            logthis("Unable to determine existing directory name for",suffix=torid,loglevel=LL.ERROR)
            return False

        # get base dir from full path
        sdir = os.path.basename(fdir)

        try:
            self.xcon.call('core.rename_folder',torid,sdir,newname)
            return True
        except Exception as e:
            logthis("Failed to rename torrent dir:",prefix=torid,suffix=e,loglevel=LL.ERROR)
            return False

    def moveTorrent(self, torids, destdir):
        """move torrent data (directory or file) to new location"""
        if torids is list: torids = torids[0]
        mcx = multicall(self.xcon)

        rpdir = os.path.realpath(destdir)
        if not os.path.isdir(rpdir):
            logthis("Failed to move torrent storage. Directory does not exist:",suffix=rpdir,loglevel=LL.ERROR)
            return False

        # get current dir of the torrent and torrent name
        tdir,tname = mcx.q('d.get_directory',[torids]).q('d.name',[torids]).run()
        if os.path.is_dir(tdir):
            mbase = tdir
            basedir = os.path.dirname(tdir)
            tdest = destdir + '/' + os.path.basename(tdir)
        else:
            mbase = tdir + '/' + tname
            basedir = tdir
            tdest = destdir + '/' + tname

        try:
            # move file/dir (rtorrent does not do this itself like deluge does)
            os.rename(mbase, tdest)
            self.xcon.d.set_directory(torids, tdest)
            return True
        except Exception as e:
            logthis("Failed to move torrent storage:",suffix=e,loglevel=LL.ERROR)
            return False

    def __statusLookup(self,complete,active,hashing,state):
        """produce status text based upon status bits"""
        if not state: tstatus = "Not Started/Queued"
        elif hashin: tstatus = "Checking"
        elif not complete and not active: tstatus = "Paused"
        elif not complete and active: tstatus = "Downloading"
        elif complete and not active: tstatus = "Complete"
        elif complete and active: tstatus = "Seeding"
        else: tstatus = "Unknown (%d%d%d%d)" % (complete,active,hashing,state)
        return tstatus

    def __del__(self):
        """disconnect from rtorrent"""
        # nothing special required for disconnection, socket/connection
        # will be cleaned up on shutdown
        pass
