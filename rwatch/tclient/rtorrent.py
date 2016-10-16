#!/usr/bin/env python
# coding=utf-8
# vim: set ts=4 sw=4 expandtab syntax=python:
"""

rwatch.tclient.rtorrent
Rainwatch > rTorrent RPC client

Copyright (c) 2016 J. Hipps / Neo-Retro Group
https://ycnrg.org/

@author     Jacob Hipps <jacob@ycnrg.org>
@repo       https://git.ycnrg.org/projects/YRW/repos/rainwatch

"""

import os
import re
import xmlrpclib
from collections import defaultdict, deque

from urlparse import urlparse

from rwatch.logthis import *

## tinfo remappings

map_tinfo = defaultdict(lambda: None, {
                'd.hash': "hash",
                'd.name': "name",
                'd.base_path': "path",
                'd.directory_base': "base_path",
                'd.creation_date': "time_added",
                'd.message': "message",
                'd.size_bytes': "total_size",
                'd.completed_bytes': "completed_size",
                'd.ratio': "ratio",
                'd.up.total': "uploaded",
                'd.down.total': "downloaded",
                'd.up.rate': "upload_rate",
                'd.down.rate': "download_rate",
                'd.peers_connected': "connected_peers",
                'd.peers_complete': "connected_seeds",
                'd.is_private': "private",
                'd.size_files': "file_count",
                'd.size_chunks': "piece_count"
            })

map_tinfo_files = defaultdict(lambda: None, {
                'f.path': "path",
                'f.offset': "offset",
                'f.size_bytes': "size",
                'f.priority': "priority"
            })

map_tinfo_trackers = defaultdict(lambda: None, {
                't.failed_counter': "fail_count",
                't.success_counter': "success_count",
                't.url': "url",
                't.is_enabled': "enabled"
            })

## rtorrent enum types
rtorrent_tracker_types = (None, 'http', 'udp', 'dht')


class multicall(deque):
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
        for ri, rr in enumerate(rez):
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
        logthis("Connecting to rTorrent RPC via", suffix=uri, loglevel=LL.INFO)
        self.xcon = xmlrpclib.ServerProxy(uri)
        mcx = multicall(self.xcon)
        try:
            self.client_version, self.api_version, self.libtor_version = mcx.q('system.client_version').q('system.api_version').q('system.library_version').run()
        except Exception as e:
            logthis("Failed to connect to rTorrent:", suffix=e, loglevel=LL.ERROR)
            if abortfail:
                failwith(ER.CONF_BAD, "Connection to rTorrent failed. Aborting.")
            else:
                return
        logthis("Connected to rTorrent OK", ccode=C.GRN, loglevel=LL.INFO)
        logthis("rTorrent %s (libtorrent %s)" % (self.client_version, self.libtor_version), loglevel=LL.INFO)
        self.connected = True

    def getTorrent(self, torid):
        """get info on a particular torrent"""
        try:
            traw = self.__d_multicall_single(torid, ("d.hash", "d.name", "d.base_path", "d.directory_base",
                                                     "d.creation_date", "d.message", "d.size_bytes",
                                                     "d.completed_bytes", "d.ratio", "d.up.total", "d.down.total",
                                                     "d.up.rate", "d.down.rate", "d.peers_connected",
                                                     "d.peers_complete", "d.is_private", "d.complete", "d.is_active",
                                                     "d.is_hash_checking", "d.state", "d.size_files", "d.size_chunks"))
            logthis("traw:", suffix=traw, loglevel=LL.DEBUG2)
        except Exception as e:
            logthis("Error calling d.multicall:", suffix=e, loglevel=LL.ERROR)
            return False

        # remap values
        otor = { map_tinfo[tk]: tv for tk, tv in traw.items() }
        if otor.has_key(None): del(otor[None])
        logthis("remap:", suffix=otor, loglevel=LL.DEBUG2)

        # get files
        flist = []
        fraw = self.__f_multicall(torid, ("f.path", "f.offset", "f.size_bytes",
                                          "f.completed_chunks", "f.size_chunks", "f.priority"))
        for tk, td in enumerate(fraw):
            # remap
            tfile = { map_tinfo_files[ik]: iv for ik, iv in td.items() }
            if tfile.has_key(None): del(tfile[None])
            # extrapolate
            tfile['index'] = tk
            tfile['progress'] = (float(td['f.completed_chunks']) / float(td['f.size_chunks'])) * 100.0
            flist.append(tfile)

        otor['files'] = tuple(flist)

        # get trackers
        tlist = []
        rraw = self.__t_multicall(torid, ("t.failed_counter", "t.success_counter", "t.url", "t.type", "t.is_enabled"))
        for tk, td in enumerate(rraw):
            # remap
            track = { map_tinfo_trackers[ik]: iv for ik, iv in td.items() }
            if track.has_key(None): del(track[None])
            # extrapolate
            track['type'] = rtorrent_tracker_types[int(td['t.type'])]
            tlist.append(track)

        otor['trackers'] = tuple(tlist)

        # set extrapolated values
        otor['progress'] = float(traw['d.completed_bytes']) / float(traw['d.size_bytes']) * 100.0
        otor['state'] = self.__statusLookup(traw['d.complete'], traw['d.is_active'],
                                            traw['d.is_hash_checking'], traw['d.state'])
        otor['ratio'] = float(otor['ratio']) / 1000.0
        otor['hash'] = otor['hash'].lower()
        otor['private'] = bool(otor['private'])

        # terrible ETA calculation
        if not traw['d.complete'] and traw['d.down.rate'] > 0:
            otor['eta'] = int(float(traw['d.size_bytes'] - traw['d.completed_bytes']) / float(traw['d.down.rate']))
        else:
            otor['eta'] = 0

        try:
            otor['tracker_host'] = re.sub(':[0-9]+$', '', urlparse(tlist[0]['url']).netloc)
        except:
            otor['tracker_host'] = None

        return otor

    def getTorrentList(self, filter=None, full=False):
        """get list of torrents; setting full=True will return all fields for all torrents"""
        if full:
            fields = ("d.hash", "d.name", "d.base_path", "d.directory_base", "d.creation_date", "d.message",
                      "d.size_bytes", "d.completed_bytes", "d.ratio", "d.up.total", "d.down.total",
                      "d.up.rate", "d.down.rate", "d.peers_connected", "d.peers_complete", "d.is_private",
                      "d.complete", "d.is_active", "d.is_hash_checking", "d.state", "d.size_files", "d.size_chunks")
        else:
            fields = ("d.name", "d.hash", "d.completed_bytes", "d.size_bytes", "d.creation_date",
                      "d.complete", "d.is_active", "d.is_hash_checking", "d.state", "d.down.rate")

        try:
            traw = self.__d_multicall("main", fields)
        except Exception as e:
            logthis("Error calling d.multicall:", suffix=e, loglevel=LL.ERROR)
            return False

        tlist = {}
        for ttor in traw:
            # remap values
            otor = { map_tinfo[tk]: tv for tk, tv in ttor.items() }
            if otor.has_key(None): del(otor[None])
            logthis("remapped:", suffix=otor, loglevel=LL.DEBUG2)

            if full:
                torid = ttor['d.hash']

                # get files
                flist = []
                fraw = self.__f_multicall(torid, ("f.path", "f.offset", "f.size_bytes", "f.completed_chunks",
                                                  "f.size_chunks", "f.priority"))
                for tk, td in enumerate(fraw):
                    # remap
                    tfile = { map_tinfo_files[ik]: iv for ik, iv in td.items() }
                    if tfile.has_key(None): del(tfile[None])
                    # extrapolate
                    tfile['index'] = tk
                    tfile['progress'] = (float(td['f.completed_chunks']) / float(td['f.size_chunks'])) * 100.0
                    flist.append(tfile)

                otor['files'] = tuple(flist)

                # get trackers
                rlist = []
                rraw = self.__t_multicall(torid, ("t.failed_counter", "t.success_counter",
                                                  "t.url", "t.type", "t.is_enabled"))
                for tk, td in enumerate(rraw):
                    # remap
                    track = { map_tinfo_trackers[ik]: iv for ik, iv in td.items() }
                    if track.has_key(None): del(track[None])
                    # extrapolate
                    track['type'] = rtorrent_tracker_types[int(td['t.type'])]
                    rlist.append(track)

                otor['trackers'] = tuple(rlist)

            # set extrapolated values
            otor['progress'] = float(ttor['d.completed_bytes']) / float(ttor['d.size_bytes']) * 100.0
            otor['state'] = self.__statusLookup(ttor['d.complete'], ttor['d.is_active'],
                                                ttor['d.is_hash_checking'], ttor['d.state'])
            otor['hash'] = otor['hash'].lower()

            if full:
                otor['ratio'] = float(otor['ratio']) / 1000.0
                otor['private'] = bool(otor['private'])

            # terrible ETA calculation
            if not ttor['d.complete'] and ttor['d.down.rate'] > 0:
                otor['eta'] = int(float(ttor['d.size_bytes'] - ttor['d.completed_bytes']) / float(ttor['d.down.rate']))
            else:
                otor['eta'] = 0

            try:
                if full:
                    tracker_url = tlist[0]['url']
                else:
                    tracker_url = self.xcon.t.get_url(ttor['d.hash'], 0)
                otor['tracker_host'] = re.sub(':[0-9]+$', '', urlparse(tracker_url).netloc)
            except:
                otor['tracker_host'] = None

            tlist[ttor['d.hash'].lower()] = otor

        return tlist

    def renameFolder(self, torid, newname):
        """rename torrent directory name"""
        # first, get info on this torrent
        torinfo = self.xcon.call('core.get_torrent_status', torid, [])

        # Check if the dir is the same as torrent name
        if os.path.isdir(torinfo['save_path'] + '/' + torinfo['name']):
            fdir = torinfo['save_path'] + '/' + torinfo['name']
        elif os.path.isdir(os.path.dirname(torinfo['save_path'] + '/' + torinfo['files'][0]['path'])):
            fdir = os.path.dirname(torinfo['save_path'] + '/' + torinfo['files'][0]['path'])
        else:
            logthis("Unable to determine existing directory name for", suffix=torid, loglevel=LL.ERROR)
            return False

        # get base dir from full path
        sdir = os.path.basename(fdir)

        try:
            self.xcon.call('core.rename_folder', torid, sdir, newname)
            return True
        except Exception as e:
            logthis("Failed to rename torrent dir:", prefix=torid, suffix=e, loglevel=LL.ERROR)
            return False

    def moveTorrent(self, torids, destdir):
        """move torrent data (directory or file) to new location"""
        if torids is list: torids = torids[0]
        mcx = multicall(self.xcon)

        rpdir = os.path.realpath(destdir)
        if not os.path.isdir(rpdir):
            logthis("Failed to move torrent storage. Directory does not exist:", suffix=rpdir, loglevel=LL.ERROR)
            return False

        # get current dir of the torrent and torrent name
        tdir, tname = mcx.q('d.get_directory', [torids]).q('d.name', [torids]).run()
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
            logthis("Failed to move torrent storage:", suffix=e, loglevel=LL.ERROR)
            return False

    def __d_multicall_single(self, hashid, calls):
        """run list of calls against single torrent"""
        # queue up calls
        mcx = multicall(self.xcon)
        for tc in calls:
            mcx.q(tc, hashid)

        # then execute
        mcraw = mcx.run()
        mcres = { calls[ikey]: ival for ikey, ival in enumerate(mcraw) }

        return mcres

    def __d_multicall(self, view, calls):
        """get list of torrents in specified view; return a dict with corresponding key-value pairs"""
        # create tuple with view and list of calls with an '=' appended to them
        # then execute d.multicall
        mcraw = self.xcon.d.multicall(tuple([view] + map(lambda x: "%s=" % (x), calls)))

        # create dict with "callname: result" structure
        mcres = []
        for td in mcraw:
            mcres.append({ calls[ikey]: ival for ikey, ival in enumerate(td) })

        return tuple(mcres)

    def __t_multicall(self, hashid, calls):
        """get list of tracker attribs for specified hashid; return a dict with corresponding key-value pairs"""
        # create tuple with view and list of calls with an '=' appended to them
        # then execute t.multicall; this call requires a dummy argument in the first index of second arg
        mcraw = self.xcon.t.multicall(hashid, tuple([0] + map(lambda x: "%s=" % (x), calls)))

        # create dict with "callname: result" structure
        mcres = []
        for td in mcraw:
            mcres.append({ calls[ikey]: ival for ikey, ival in enumerate(td) })

        return tuple(mcres)

    def __f_multicall(self, hashid, calls):
        """get list of file attribs for specified hashid; return a dict with corresponding key-value pairs"""
        # create tuple with view and list of calls with an '=' appended to them
        # then execute f.multicall; this call requires a dummy argument in the first index of second arg
        mcraw = self.xcon.f.multicall(hashid, tuple([0] + map(lambda x: "%s=" % (x), calls)))

        # create dict with "callname: result" structure
        mcres = []
        for td in mcraw:
            mcres.append({ calls[ikey]: ival for ikey, ival in enumerate(td) })

        return tuple(mcres)

    def __statusLookup(self, complete, active, hashing, state):
        """produce status text based upon status bits"""
        if not state: tstatus = "Not Started/Queued"
        elif hashing: tstatus = "Checking"
        elif not complete and not active: tstatus = "Paused"
        elif not complete and active: tstatus = "Downloading"
        elif complete and not active: tstatus = "Complete"
        elif complete and active: tstatus = "Seeding"
        else: tstatus = "Unknown (%d%d%d%d)" % (complete, active, hashing, state)
        return tstatus

    def __del__(self):
        """disconnect from rtorrent"""
        # nothing special required for disconnection, socket/connection
        # will be cleaned up on shutdown
        pass
