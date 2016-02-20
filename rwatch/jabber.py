#!/usr/bin/env python
# coding=utf-8
###############################################################################
#
# jabber - rwatch/jabber.py
# Rainwatch: Jabber/XMPP functions
#
# @author   J. Hipps <jacob@ycnrg.org>
# @repo     https://bitbucket.org/yellowcrescent/rainwatch
#
# Copyright (c) 2016 J. Hipps / Neo-Retro Group
#
# https://ycnrg.org/
#
###############################################################################

import __main__
import sys
import os
import re
import json
import signal
import optparse
import operator
import time
import socket
import xmpp
from setproctitle import setproctitle

from rwatch.logthis import *
from rwatch import db

jbx = None
rdx = None

def spawn():
    """
    spawn a Jabber client in its own little thread
    """
    conf = __main__.xsetup.config

    # Fork into its own process
    logthis("Forking...",loglevel=LL.DEBUG)
    dadpid = os.getpid()
    try:
        pid = os.fork()
    except OSError, e:
        logthis("os.fork() failed:",suffix=e,loglevel=LL.ERROR)
        failwith(ER.PROCFAIL, "Failed to fork worker. Aborting.")

    # Return if we are the parent process
    if pid:
        return 0

    # Otherwise, we are the child
    logthis("Forked jabber client. pid =",suffix=os.getpid(),loglevel=LL.INFO)
    logthis("Jabber ppid =",suffix=dadpid,loglevel=LL.VERBOSE)
    setproctitle("rainwatch: jabber")

    # Create Jabber client object
    jbx = client(conf['xmpp']['user'], conf['xmpp']['pass'])

    # Connect to Redis
    rdx = db.redis({ 'host': conf['redis']['host'], 'port': conf['redis']['port'], 'db': conf['redis']['db'] },prefix=conf['redis']['prefix'])

    # Main loop
    while(True):
        qiraw = None
        qmsg = None

        # block until we receive a message; max of 5 seconds
        qiraw = rdx.brpop("jabber_out",5)
        if qiraw:
            try:
                qmsg = json.loads(qiraw)
            except Exception as e:
                logthis("!! Jabber: Bad JSON data from message. Msg discarded. raw data:",suffix=qiraw,loglevel=LL.ERROR)

        if qmsg:
            if qmsg.get('method',False) and qmsg.get('params',False):
                try:
                    # dynamically call the class method
                    getattr(jbx, qmsg['method'])(**qmsg['params'])
                except Exception as e:
                    logthis("!! Failed to call method '%s':" % (qmsg.get('method',"[NONE]")),suffix=e,loglevel=LL.ERROR)

        # check if parent is alive
        if not master_alive(dadpid):
            logthis("Jabber: Master has terminated.",prefix=qname,loglevel=LL.WARNING)
            break

    # And exit once we're done
    logthis("*** Jabber terminating",loglevel=LL.INFO)
    sys.exit(0)


def send(method,params={}):
    """
    send command to jabber client process
    """
    conf = __main__.xsetup.config

    # connect to Redis, if not already connected
    if not rdx:
        rdx = db.redis({ 'host': conf['redis']['host'], 'port': conf['redis']['port'], 'db': conf['redis']['db'] },prefix=conf['redis']['prefix'])

    # send data
    rdx.lpush("jabber_out", json.dumps({ 'method': method, 'params': params }))


def master_alive(ppid):
    try:
        os.kill(ppid, 0)
    except OSError:
        return False
    else:
        return True


class client:
    """
    class for handling XMPP client comms
    """
    clx = None
    ccon = None
    acon = None
    connected = False

    def __init__(self, juser, jpass, jres='rainwatch', jserver=None, jport=5222, abortfail=True):
        if jserver: jsx = (jserver,jport)
        else: jsx = None
        jid = xmpp.protocol.JID(juser)
        self.clx = xmpp.Client(jid.getDomain(),debug=[])

        # if server and port not specified, use the SRV records to determine server name and port
        crez = self.clx.connect(jsx)
        if not crez:
            logthis("Connection to Jabber server failed for",suffix=juser,loglevel=LL.ERROR)
            return
        else:
            self.ccon = crez
            logthis("Connected to Jabber server via",suffix=crez.upper(),ccode=C.GRN,loglevel=LL.INFO)

        # authenticate
        arez = self.clx.auth(jid.getNode(),jpass,jres)
        if not arez:
            logthis("Failed to authenticate to Jabber server for",suffix=juser,loglevel=LL.ERROR)
            return
        else:
            self.acon = arez
            logthis("Authenticated to Jabber server via",suffix=arez.upper(),ccode=C.GRN,loglevel=LL.INFO)

        # enable presence
        self.clx.sendInitPresence()
        self.connected = True

    def sendmsg(self, jid, msg):
        """send a message (msg) to a user (jid)"""
        self.clx.send(xmpp.protocol.Message(xmpp.protocol.JID(jid),msg))

    def authorize(self, jid):
        """authorize a JID"""
        self.clx.Roster.Authorize(xmpp.protocol.JID(jid))

    def set_status(self, status="", type='available', show='chat'):
        """
        broadcast presence information
        status: human-readable status message
        types: [available, unavailable, error, probe, subscribe, subscribed, unsubscribe, unsubscribed]
        show: [away, chat, dnd, xa]
        """
        self.clx.send(xmpp.Presence(typ=type,show=show,status=status))

    def __del__(self):
        self.clx.disconnect()
        self.connected = False
