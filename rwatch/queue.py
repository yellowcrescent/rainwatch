#!/usr/bin/env python3.5
# coding=utf-8
# vim: set ts=4 sw=4 expandtab syntax=python:
"""

rwatch.queue
Rainwatch > Queue runner

Copyright (c) 2016 J. Hipps / Neo-Retro Group
https://ycnrg.org/

@author     Jacob Hipps <jacob@ycnrg.org>
@repo       https://git.ycnrg.org/projects/YRW/repos/rainwatch

"""

import sys
import os
import re
import time
import json
from setproctitle import setproctitle

from rwatch.logthis import *
from rwatch.util import *
from rwatch.ssh2 import rainshell
from rwatch import db, jabber, tclient


# Queue handler callbacks
handlers = None
conf = None

# Redis object, Deluge client, Parent PID
rdx = None
dlx = None
dadpid = None

def start(xconfig, qname="xfer"):
    global rdx, dlx, dadpid, handlers, conf
    conf = xconfig

    # Fork into its own process
    logthis("Forking...", loglevel=LL.DEBUG)
    dadpid = os.getpid()
    try:
        pid = os.fork()
    except OSError as e:
        logthis("os.fork() failed:", suffix=e, loglevel=LL.ERROR)
        failwith(ER.PROCFAIL, "Failed to fork worker. Aborting.")

    # Return if we are the parent process
    if pid:
        return 0

    # Otherwise, we are the child
    logthis("Forked queue runner. pid =", prefix=qname, suffix=os.getpid(), loglevel=LL.INFO)
    logthis("QRunner. ppid =", prefix=qname, suffix=dadpid, loglevel=LL.VERBOSE)
    setproctitle("rainwatch: queue runner - %s" % (qname))

    # Connect to Redis
    rdx = db.redis({ 'host': conf.redis['host'], 'port': conf.redis['port'], 'db': conf.redis['db'] },
                   prefix=conf.redis['prefix'])

    # Connect to Deluge
    dlx = tclient.TorrentClient(xconfig)

    # Set queue callbacks
    handlers = {
                 'xfer': cb_xfer
               }

    # Start listener loop
    qrunner(qname)

    # And exit once we're done
    logthis("*** Queue runner terminating", prefix=qname, loglevel=LL.INFO)
    sys.exit(0)

def qrunner(qname="xfer"):
    global rdx, mdx, handlers

    qq = "queue_"+qname
    wq = "work_"+qname

    # Crash recovery
    # Check work queue (work_*) and re-queue any unhandled items
    logthis("-- QRunner crash recovery: checking for abandoned jobs...", loglevel=LL.VERBOSE)
    requeued = 0
    while(rdx.llen(wq) != 0):
        crraw = rdx.lpop(wq)
        try:
            critem = json.loads(crraw)
        except Exception as e:
            logthis("!! QRunner crash recovery: Bad JSON data from queue item. Job discarded. raw data:",
                    prefix=qname, suffix=crraw, loglevel=LL.ERROR)
            continue
        cr_jid = critem.get("id", "??")
        logthis("** Requeued abandoned job:", prefix=qname, suffix=cr_jid, loglevel=LL.WARNING)
        rdx.rpush(qq, crraw)
        requeued += 1

    if requeued:
        logthis("-- QRunner crash recovery OK! Jobs requeued:", prefix=qname, suffix=requeued, loglevel=LL.VERBOSE)

    logthis("pre-run queue sizes: %s = %d / %s = %d" % (qq, rdx.llen(qq), wq, rdx.llen(wq)),
            prefix=qname, loglevel=LL.DEBUG)
    logthis("-- QRunner waiting; queue:", prefix=qname, suffix=qname, loglevel=LL.VERBOSE)
    while(True):
        # RPOP from main queue and LPUSH on to the work queue
        # block for 5 seconds, check that the master hasn't term'd, then
        # check again until we get something
        qitem = None
        qiraw = rdx.brpoplpush(qq, wq, 5)
        if qiraw:
            logthis(">> QRunner: discovered a new job in queue", prefix=qname, suffix=qname, loglevel=LL.VERBOSE)

            try:
                qitem = json.loads(qiraw)
            except Exception as e:
                logthis("!! QRunner: Bad JSON data from queue item. Job discarded. raw data:",
                        prefix=qname, suffix=qiraw, loglevel=LL.ERROR)

            # If we've got a valid job item, let's run it!
            if qitem:
                logthis(">> QRunner: job data:\n", prefix=qname, suffix=json.dumps(qitem), loglevel=LL.DEBUG)

                # Execute callback
                rval = handlers[qname](qitem)
                if (rval == 0):
                    logthis("QRunner: Completed job successfully.", prefix=qname, loglevel=LL.VERBOSE)
                elif (rval == 1):
                    logthis("QRunner: Job complete, but with warnings.", prefix=qname, loglevel=LL.WARNING)
                else:
                    logthis("QRunner: Job failed. rval =", prefix=qname, suffix=rval, loglevel=LL.ERROR)

                # Remove from work queue
                rdx.rpop(wq)

            # Show wait message again
            logthis("-- QRunner: waiting; queue:", prefix=qname, suffix=qname, loglevel=LL.VERBOSE)

        # Check if daddy is still alive; prevents this process from becoming a bastard child
        if not master_alive():
            logthis("QRunner: Master has terminated.", prefix=qname, loglevel=LL.WARNING)
            return

def cb_xfer(jdata):
    """
    xfer queue handler
    """
    global dlx, conf

    # get options from job request
    jid  = jdata['id']
    thash  = jdata['thash']
    opts = jdata['opts']

    # Do some loggy stuff
    logthis("xfer: JobID %s / TorHash %s / Opts %s" % (jid, thash, json.dumps(opts)), loglevel=LL.VERBOSE)

    # get updated data from torrent client
    tordata = dlx.getTorrent(thash)

    if not tordata:
        logthis("!! Failed to retrieve torrent data corresponding to supplied hash. Job discarded.", loglevel=LL.ERROR)
        return 101

    # establish SSH connection
    rsh = rainshell(conf.xfer['hostname'], username=conf.xfer['user'],
                    keyfile=conf.xfer['keyfile'], port=int(conf.xfer['port']))

    # download
    if conf.xfer['hostname']:
        # send xfer start notification
        if conf.notify['user'] and conf.notify['hostname']:
            try:
                libnotify_send(conf, "%s\n\nStarted transfer to incoming." % (tordata['name']))
            except Exception as e:
                logthis("Failed to send libnotify message:", suffix=e, loglevel=LL.ERROR)

        # xfer via scp
        try:
            tgpath = ("%s/%s" % (tordata['base_path'], tordata['name']))
            logthis("tgpath:", suffix=tgpath, loglevel=LL.DEBUG)
        except Exception as e:
            logexc(e, "Failed to perform string interpolation for tgpath")
            failwith(ER.PROCFAIL, "Unable to continue.")

        # Until a way can be determine to fix os.stat/open functions when running detached from
        # the terminal, this check is going to be skipped
        #try:
        #    if not path_exists(tgpath):
        #        logthis("!! Path does not exist:", suffix=tgpath, loglevel=LL.ERROR)
        #        return False
        #    else:
        #        logthis(">> Target path:", suffix=tgpath, loglevel=LL.INFO)
        #except Exception as e:
        #    logexc(e, "Unable to determine existence of tgpath")
        #    failwith(ER.PROCFAIL, "Unable to continue.")
        logthis(">> Target path:", suffix=tgpath, loglevel=LL.INFO)

        logthis(">> Starting transfer to remote host:",
                suffix="%s:%s" % (conf.xfer['hostname'], conf.xfer['basepath']), loglevel=LL.INFO)
        xstart = datetime.now()
        #rexec(['/usr/bin/scp', '-B', '-r', tgpath, "%s:'%s'" % (conf.xfer['hostname'], conf.xfer['basepath'])])
        rsh.xfer(tgpath, conf.xfer['basepath'])
        xstop = datetime.now()
        logthis("** Transfer complete.", loglevel=LL.INFO)

        # send xfer complete notification
        xdelta = xstop - xstart
        xdelta_str = re.sub(r'\.[0-9]+$', '', str(xdelta))
        tsize = tordata['total_size']
        trate = float(tsize) / float(xdelta.seconds)
        tsize_str = fmtsize(tsize)
        trate_str = fmtsize(trate, rate=True)
        trate_bstr = fmtsize(trate, rate=True, bits=True)
        jabber.send('send_message', {'mto': conf.xmpp['sendto'],
                    'mbody': "%s -- Transfer Complete (%s) -- Time Elapsed ( %s ) -- Rate [ %s | %s ]" %
                    (tordata['name'], tsize_str, xdelta_str, trate_str, trate_bstr)})
        jabber.send('set_status', { 'show': None, 'status': "Ready" })

    # done
    rsh.close()
    return 0


def enqueue(xredis, qname, thash, opts={}, jid=None, silent=False):
    """
    enqueue a task on the specified queue
    """
    # generate a job ID from the current time
    if not jid:
        jid = str(time.time()).replace(".", "")

    # JSON-encode and LPUSH on to the selected queue
    xredis.lpush("queue_"+qname, json.dumps({'id': jid, 'thash': thash, 'opts': opts }))

    if not silent:
        logthis("Enqueued job# %s in queue:" % (jid), suffix=qname, loglevel=LL.VERBOSE)

    return jid


def master_alive():
    global dadpid
    try:
        os.kill(dadpid, 0)
    except OSError:
        return False
    else:
        return True
