#!/usr/bin/env python3.5
# coding=utf-8
# vim: set ts=4 sw=4 expandtab syntax=python:
"""

rwatch.cli
Rainwatch > CLI Interface

Copyright (c) 2016 J. Hipps / Neo-Retro Group
https://ycnrg.org/

@author     Jacob Hipps <jacob@ycnrg.org>
@repo       https://git.ycnrg.org/projects/YRW/repos/rainwatch

"""

import sys
import os
import json
import optparse
import time

import requests

from rwatch import *
from rwatch.util import *
from rwatch.logthis import *
from rwatch import rcfile, ruleparser, daemon, tclient

config = None

def show_banner():
    """
    Display banner
    """
    print("")
    print(C.CYN, "*** ", C.WHT, "rainwatch", C.OFF)
    print(C.CYN, "*** ", C.CYN, "Version", __version__, "(" + __date__ + ")", C.OFF)
    print(C.CYN, "*** ", C.GRN, "Copyright (c) 2016 J. Hipps / Neo-Retro Group", C.OFF)
    print(C.CYN, "*** ", C.GRN, "J. Hipps <jacob@ycnrg.org>", C.OFF)
    print(C.CYN, "*** ", C.YEL, "https://ycnrg.org/", C.OFF)
    print("")

def parse_cli():
    """
    Parse command-line options
    """
    global oparser
    oparser = optparse.OptionParser(usage="%prog [options] <[-i] TORRENT_ID>", version=__version__ + " (" + __date__ + ")")

    # General options
    oparser.add_option('-v', '--verbose', action="count", dest="run.verbose", help="Increase logging verbosity (-v Verbose, -vv Debug, -vvv Debug2)")
    oparser.add_option('-L', '--loglevel', action="store", dest="core.loglevel", default=False, metavar="NUM", help="Logging output verbosity (4=error,5=warning,6=info,7=verbose,8=debug,9=debug2)")
    oparser.add_option('-q', action="store_true", dest="run.quiet", default=False, help="Quiet - suppress log messages (use as first option)")
    oparser.add_option('-i', action="store", dest="run.torid", default=False, metavar="TORID", help="Torrent ID")

    oparser.add_option('-d', '--srv', action="store_true", dest="run.srv", default=False, help="Daemon mode")
    oparser.add_option('-l', '--list', action="store_true", dest="run.list", default=False, help="List torrents")
    oparser.add_option('-m', '--move', action="store", dest="run.move", default=None, metavar="PATH", help="Move storage")
    oparser.add_option('-f', '--full', action="store_true", dest="run.full", default=False, help="Full output in torrent list")
    oparser.add_option('-j', '--json', action="store_true", dest="run.json", default=False, help="Output data as JSON")

    oparser.add_option('--fdebug', action="store_true", dest="run.fdebug", default=False, help="Daemon: Flask debug mode")
    oparser.add_option('--nofork', action="store_true", dest="srv.nofork", default=False, help="Daemon: Do not fork into background")

    options, args = oparser.parse_args(sys.argv[1:])
    vout = vars(options)

    if len(args) >= 1:
        vout['run.torid'] = args[0]

    if vout['run.verbose']:
        vout['run.verbose'] += 6
        vout['core.loglevel'] = vout['run.verbose']
    if vout['run.verbose'] or vout['core.loglevel']:
        loglevel(int(vout['core.loglevel']))
    if vout['run.quiet']:
        vout['core.loglevel'] = LL.ERROR
        loglevel(vout['core.loglevel'])

    return vout


def mode_list():
    global dlx

    # if torrent ID is specified, use it to filter
    if config.run['torid']:
        fltr = { 'id': config.run['torid'] }
    else:
        fltr = {}

    # get list of torrents
    if config.run['full']:
        torlist = dlx.getTorrentList(filter=fltr, full=True)
    else:
        torlist = dlx.getTorrentList(filter=fltr)

    if config.run['json']:
        print(json.dumps(torlist, indent=4, separators=(',', ': ')))
    else:
        for ti, tv in torlist.items():
            print("%s: %s (%0.01f) [%s]" % (ti, tv['name'], tv['progress'], tv['tracker_host']))
    return 0

def mode_chook(tid):
    global dlx, jbx

    # get torrent data
    logthis(">> Processing 'complete' exec hook for", suffix=tid, loglevel=LL.INFO)
    tordata = dlx.getTorrent(tid)

    # find matching rules
    rname, rset = ruleparser.match(tordata)
    if rname:
        logthis("++ Matched ruleset:\n", suffix=print_r(rset), loglevel=LL.VERBOSE)
    else:
        logthis("!! No ruleset matched", loglevel=LL.WARNING)

    # move to destination dir
    if rset.get('moveto', None):
        if dlx.moveTorrent(tid, rset['moveto']):
            logthis("** Moved to", suffix=rset['moveto'], loglevel=LL.INFO)
            time.sleep(2)
        else:
            logthis("!! Failed to move to", suffix=rset['moveto'], loglevel=LL.ERROR)

    # enqueue
    qurl = config.srv['url'] + '/api/chook'
    headset = { 'Content-Type': "application/json", 'WWW-Authenticate': config.srv['shared_key'], 'User-Agent': "rainwatch/" + __version__ }
    rq = requests.post(qurl, headers=headset, data=json.dumps({ 'thash': tid, 'opts': False }))

    if rq.status_code == 201:
        logthis(">> Queued torrent for transfer", loglevel=LL.INFO)
        rval = 0
    else:
        logthis("!! Failed to queue for transfer:", suffix=str(rq.status_code)+' '+rq.reason, loglevel=LL.ERROR)
        rval = 101

    logthis("*** Finished with complete exec hook for", suffix=tordata['name'], loglevel=LL.INFO)
    return rval


def mode_move(tid, destdir):
    global dlx, jbx

    # get torrent data
    logthis(">> Retrieving torrent data for", suffix=tid, loglevel=LL.INFO)
    tordata = dlx.getTorrent(tid)
    fnewpath = os.path.realpath(destdir) + '/' + tordata['name']
    logthis(">> Moving: %s ->" % (tordata['path']), suffix=fnewpath, loglevel=LL.INFO)

     # move to destination dir
    if dlx.moveTorrent(tid, destdir):
        logthis("** Moved to", suffix=destdir, loglevel=LL.INFO)
        rval = 0
    else:
        logthis("!! Failed to move to", suffix=destdir, loglevel=LL.ERROR)
        rval = 102
    return rval

##############################################################################
## Entry point
##

def _main():
    """entry point"""

    # Show banner
    if len(sys.argv) < 2 or sys.argv[1] != '--version' and not (len(sys.argv[1]) > 1 and sys.argv[1][1] == 'q'):
        show_banner()

    # Set default loglevel
    loglevel(defaults['core']['loglevel'])

    # parse CLI options and load running config
    xopt = parse_cli()
    config = rcfile.loadConfig(cliopts=xopt)
    loglevel(config.core['loglevel'])
    openlog(config.core['logfile'])

    # Set quiet exception handler for non-verbose operation
    if config.core['loglevel'] < LL.VERBOSE:
        sys.excepthook = exceptionHandler

    # parse rules file
    ruleparser.parse(config)

    # connect to deluge (for non-daemon stuffs)
    if not config.run['srv']:
        dlx = tclient.TorrentClient(config)

    ## process commands

    if config.run['list']:
        # get list of torrents
        rval = mode_list()
    elif config.run['move'] is not None:
        # process 'move' command
        rval = mode_move(config.run['torid'], config.run['move'])
    elif config.run['torid']:
        # process 'complete' hook
        rval = mode_chook(config.run['torid'])
    elif config.run['srv']:
        # start daemon
        rval = daemon.start(config)
    else:
        logthis("Nothing to do.", loglevel=LL.WARNING)
        rval = 1

    closelog()
    sys.exit(rval)

if __name__ == '__main__':
    _main()
