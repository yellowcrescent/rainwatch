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

    # Connect to Redis
    rdx = db.redis({ 'host': conf['redis']['host'], 'port': conf['redis']['port'], 'db': conf['redis']['db'] },prefix=conf['redis']['prefix'])

    # Create Jabber client object
    jbx = client(conf['xmpp']['user'], conf['xmpp']['pass'], redis=rdx)

    # Main loop
    while(True):
        qiraw = None
        qmsg = None

        # check for incoming messages; block for max of 2 seconds
        jbx.process(2)

        # block until we receive a message; max of 2 seconds
        qiraw = rdx.brpop("jabber_out",2)

        if qiraw:
            try:
                qmsg = json.loads(qiraw[1])
            except Exception as e:
                logthis("!! Jabber: Bad JSON data from message. Msg discarded. Error: %s\nraw data:" % (e),suffix=qiraw,loglevel=LL.ERROR)

        if qmsg:
            if qmsg.get('method',False) and qmsg.get('params',False):
                try:
                    # dynamically call the class method
                    getattr(jbx, qmsg['method'])(**qmsg['params'])
                except IOError as e:
                    logexc(e, "!! Failed to call method '%s':" % (qmsg.get('method',"[NONE]")))
                    jbx.reconnect()
                except Exception as e:
                    logexc(e, "!! Failed to call method '%s':" % (qmsg.get('method',"[NONE]")))

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
    global rdx
    conf = __main__.xsetup.config

    # connect to Redis, if not already connected
    if not rdx:
        rdx = db.redis({ 'host': conf['redis']['host'], 'port': conf['redis']['port'], 'db': conf['redis']['db'] },prefix=conf['redis']['prefix'])

    # send data
    if conf['xmpp']['user'] and conf['xmpp']['pass']:
        rdx.lpush("jabber_out", json.dumps({ 'method': method, 'params': params }))


def recv(timeout=False):
    """
    check for incoming messages, blocking for specified amount of time
    timeout=False -- No waiting/blocking
    timeout=0 -- Block forever until a message is received
    timeout=X -- Where X is a positive integer, block for that number of seconds
    """
    global rdx
    conf = __main__.xsetup.config

    # connect to Redis, if not already connected
    if not rdx:
        rdx = db.redis({ 'host': conf['redis']['host'], 'port': conf['redis']['port'], 'db': conf['redis']['db'] },prefix=conf['redis']['prefix'])

    # get data
    if timeout is False:
        outmsg = rdx.rpop("jabber_in")
    else:
        outmsg = rdx.brpop("jabber_in",timeout)

    return outmsg


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
    rdx = None
    connected = False
    ccreds = { 'jid': None, 'jpass': None, 'jserver': None, 'jport': None }

    def __init__(self, juser, jpass, jres='rainwatch', jserver=None, jport=5222, redis=None, abortfail=True):

        # derive JID
        jid = xmpp.protocol.JID(juser+'/'+jres)
        self.clx = xmpp.Client(jid.getDomain(),debug=[])

        # save connection data, should we need to reconnect later
        self.ccreds = { 'jid': jid, 'jpass': jpass, 'jserver': jserver, 'jport': jport }

        # establish connection
        self.connect(**self.ccreds)

        # store redis connection object
        if redis:
            self.rdx = redis

        # setup message handler
        self.clx.RegisterHandler('message',self.msgHandler)

        # enable presence
        self.clx.sendInitPresence()
        self.connected = True

    def connect(self, jid, jpass, jres='rainwatch', jserver=None, jport=5222):
        """connect to jabber server"""

        # check if using explicit server/port,
        if jserver: jsx = (jserver,jport)
        else: jsx = None

        # if server and port not specified, use the SRV records to determine server name and port
        crez = self.clx.connect(jsx)
        if not crez:
            logthis("Connection to Jabber server failed for",suffix=jid.getUser(),loglevel=LL.ERROR)
            return False
        else:
            self.ccon = crez
            logthis("Connected to Jabber server via",suffix=crez.upper(),ccode=C.GRN,loglevel=LL.INFO)

        # authenticate
        arez = self.clx.auth(jid.getNode(),jpass,jid.getResource)
        if not arez:
            logthis("Failed to authenticate to Jabber server for",suffix=jid.getUser(),loglevel=LL.ERROR)
            return False
        else:
            self.acon = arez
            logthis("Authenticated to Jabber server via",suffix=arez.upper(),ccode=C.GRN,loglevel=LL.INFO)


    def reconnect():
        """reconnect if the connection has dropped or timed out"""
        logthis(">> Attempting to re-establish connection to Jabber server...",loglevel=LL.INFO)
        self.connect(**self.ccreds)

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

    def msgHandler(self,session,message):
        """
        callback handler for received messages & events
        """
        # don't bother processing empty messages (typically used for the 'Typing...' notifications)
        if message.getBody():
            logthis("[msgHandler] got message from",suffix=str(message.getFrom()),loglevel=LL.DEBUG)
            tmsg = {
                    'id': message.getID(),
                    'thread': message.getThread(),
                    'type': message.getType(),
                    'to': str(message.getTo()),
                    'from': str(message.getFrom()),
                    'subject': message.getSubject(),
                    'body': message.getBody(),
                    'time': time.time()
                   }

            # push the message onto the jabber_in message stack
            if self.rdx:
                self.rdx.lpush("jabber_in", json.dumps(tmsg))

    def process(self,timeout=1):
        """
        run Process with specified timeout
        used to process events and check for incoming messages
        """
        self.clx.Process(timeout)

    def __del__(self):
        self.connected = False
