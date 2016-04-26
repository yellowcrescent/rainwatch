#!/usr/bin/env python
# coding=utf-8
###############################################################################
#
# deluge - rwatch/deluge.py
# Rainwatch: Deluge RPC interface functions
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
from collections import defaultdict
from deluge_client import DelugeRPCClient

from rwatch.logthis import *

## tinfo remappings

map_tinfo = defaultdict(lambda: None, {
                'hash': "hash",
                'name': "name",
                'save_path': "base_path",
                'time_added': "time_added",
                'comment': "comment",
                'message': "message",
                'tracker_status': "tracker_status",
                'tracker_host': "tracker_host",
                'total_size': "total_size",
                'total_done': "completed_size",
                'progress': "progress",
                'eta': "eta",
                'ratio': "ratio",
                'total_uploaded': "uploaded",
                'all_time_download': "downloaded",
                'upload_payload_rate': "upload_rate",
                'download_payload_rate': "download_rate",
                'num_peers': "connected_peers",
                'num_seeds': "connected_seeds",
                'total_peers': "total_peers",
                'total_seeds': "total_seeds",
                'private': "private",
                'state': "state",
                'active_time': "time_active",
                'num_files': "file_count",
                'num_pieces': "piece_length",
                'next_announce': "next_announce",
                'tracker': "tracker_url"
            })

map_tinfo_files = defaultdict(lambda: None, {
                'path': "path",
                'index': "index",
                'offset': "offset",
                'size': "size"
            })

map_tinfo_trackers = defaultdict(lambda: None, {
                'fails': "fail_count",
                'url': "url"
            })


class delcon:
    """class for handling Deluge RPC comms"""
    xcon = None
    connected = False
    client_version = None
    libtor_version = None

    @classmethod
    def fromXConfig(cls, xconfig):
        """build Deluge client from global XConfig"""
        return cls(duser=xconfig.deluge['user'], dpass=xconfig.deluge['pass'], dhost=xconfig.deluge['hostname'], dport=xconfig.deluge['port'])

    def __init__(self, duser, dpass, dhost='localhost', dport=58846, abortfail=True):
        """connect to deluged and authenticate"""
        logthis("Connecting to deluged on",suffix="%s:%d" % (dhost,dport),loglevel=LL.INFO)
        self.xcon = DelugeRPCClient(dhost, dport, duser, dpass)
        try:
            self.xcon.connect()
            self.client_version = self.xcon.call('daemon.info')
            self.libtor_version = self.xcon.call('core.get_libtorrent_version')
        except Exception as e:
            logthis("Failed to connect to Deluge:",suffix=e,loglevel=LL.ERROR)
            if abortfail: failwith(ER.CONF_BAD, "Connection to Deluge failed. Aborting.")
        logthis("Connected to Deluge OK",ccode=C.GRN,loglevel=LL.INFO)
        logthis("Deluge %s (libtorrent %s)" % (self.client_version, self.libtor_version),loglevel=LL.INFO)
        self.connected = True

    def getTorrent(self, torid):
        """get info on a particular torrent"""
        try:
            interdata = self.xcon.call('core.get_torrent_status',torid,[])
        except Exception as e:
            logexc(e,"Error calling core.get_torrents_status")
            return False

        return self.__remap_tinfo(interdata)

    def getTorrentList(self, filter={}, full=False):
        """get list of torrents; setting full=True will return all fields for all torrents"""
        if full:
            fields = []
        else:
            fields = ['name','progress','tracker_host','eta','total_size','total_done','state','time_added']

        try:
            interdata = self.xcon.call('core.get_torrents_status',filter,fields)
        except Exception as e:
            logexc(e,"Error calling core.get_torrents_status")
            return False

        return self.__remap_tinfo_all(interdata)

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
        if not torids is list: torids = [ torids ]

        rpdir = os.path.realpath(destdir)
        if not os.path.isdir(rpdir):
            logthis("Failed to move torrent storage. Directory does not exist:",suffix=rpdir,loglevel=LL.ERROR)
            return False

        try:
            self.xcon.call('core.move_storage',torids,rpdir)
            return True
        except Exception as e:
            logthis("Failed to move torrent storage:",suffix=e,loglevel=LL.ERROR)
            return False

    def __remap_tinfo_all(self, inlist):
        """remap dict of deluge torrents to rainwatch tinfo schema"""
        listout = {}
        for tkey, tdata in inlist.iteritems():
            listout[tkey] = self.__remap_tinfo(tdata)
        return listout

    def __remap_tinfo(self, indata):
        """remap deluge-specific schema to rainwatch tinfo schema"""
        # remap most values
        newdata = { map_tinfo[ikey]: ival for ikey, ival in indata.items() }
        if newdata.has_key(None): del(newdata[None])

        # set other unmapped or extrapolated values
        if indata.has_key('save_path') and indata.has_key('name'):
            newdata['path'] = "%s/%s" % (indata['save_path'], indata['name'])

        # build file list
        if indata.has_key('files'):
            newfiles = []
            for tnum, tf in enumerate(indata['files']):
                # remap file object
                newfile = { map_tinfo_files[tfk]: tfv for tfk, tfv in tf.items() }
                if newfile.has_key(None): del(newfile[None])
                # set unmapped values
                newfile['progress'] = indata['file_progress'][tnum] * 100.0
                newfile['priority'] = indata['file_priorities'][tnum]
                newfiles.append(newfile)

            newdata['files'] = tuple(newfiles)

        # build tracker list
        if indata.has_key('trackers'):
            newtracks = []
            for tnum, tf in enumerate(indata['trackers']):
                # remap tracker object
                newtrack = { map_tinfo_trackers[tfk]: tfv for tfk, tfv in tf.items() }
                if newtrack.has_key(None): del(newtrack[None])
                # set unmapped values
                newtrack['success_count'] = None
                newtrack['enabled'] = True
                try:
                    newtrack['type'] = re.match('^([a-zA-Z]{3,5})://', tf['url']).group(1)
                except:
                    newtrack['type'] = None
                newtracks.append(newtrack)

            newdata['trackers'] = tuple(newtracks)

        return newdata

    def __del__(self):
        """disconnect from deluged"""
        # nothing special required for disconnection, socket/connection
        # will be cleaned up on shutdown
        pass
