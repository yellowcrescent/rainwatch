#!/usr/bin/env python3.5
# coding=utf-8
# vim: set ts=4 sw=4 expandtab syntax=python:
"""

rwatch.jabber
Rainwatch > Jabber/XMPP client

XMPP client using SleekXMPP <http://sleekxmpp.com/>

Copyright (c) 2016 J. Hipps / Neo-Retro Group
https://ycnrg.org/

@author     Jacob Hipps <jacob@ycnrg.org>
@repo       https://git.ycnrg.org/projects/YRW/repos/rainwatch

"""

import os
import sys
import json
import logging
import ssl
import time

import arrow
from setproctitle import setproctitle
from PIL import Image
from sleekxmpp import ClientXMPP, JID
from sleekxmpp.exceptions import IqError, IqTimeout, XMPPError
from sleekxmpp.version import __version__ as sleekxmpp_version

from rwatch import __version__, __date__
from rwatch import db
from rwatch.logthis import *

# valid presence states
PSTATES = (None, "dnd", "xa", "away", "chat")

jbx = None
rdx = None
conf = None

def spawn(xconfig):
    """
    spawn a Jabber client in its own process
    """
    global conf
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
    logthis("Forked jabber client. pid =", suffix=os.getpid(), loglevel=LL.INFO)
    logthis("Jabber ppid =", suffix=dadpid, loglevel=LL.VERBOSE)
    setproctitle("rainwatch: jabber")

    # Connect to Redis
    rdx = db.redis({ 'host': conf.redis['host'], 'port': conf.redis['port'], 'db': conf.redis['db'] },
                   prefix=conf.redis['prefix'])

    # Create Jabber client object
    jbx = XClient(jid=conf.xmpp['user'], password=conf.xmpp['pass'], avatar_img=conf.xmpp['avatar_img'],
                  nick=conf.xmpp['nick'], redis_con=rdx)

    logthis("Spawning non-blocking threads to handle XMPP", loglevel=LL.DEBUG)
    jbx.process()

    # Main loop
    while True:
        qiraw = None
        qmsg = None

        # block until we receive a message; max of 2 seconds
        qiraw = rdx.brpop("jabber_out", 2)

        if qiraw:
            try:
                qmsg = json.loads(qiraw[1])
            except Exception as e:
                logthis("!! Jabber: Bad JSON data from message. Msg discarded. Error: %s\nraw data:" % (e),
                        suffix=qiraw, loglevel=LL.ERROR)

        if qmsg:
            if qmsg.get('method', False) and qmsg.get('params', False):
                try:
                    # dynamically call the class method
                    getattr(jbx, qmsg['method'])(**qmsg['params'])
                except IOError as e:
                    logexc(e, "!! Failed to call method '%s':" % (qmsg.get('method', "[NONE]")))
                    jbx.reconnect()
                except Exception as e:
                    logexc(e, "!! Failed to call method '%s':" % (qmsg.get('method', "[NONE]")))

        # check if parent is alive
        if not master_alive(dadpid):
            logthis("Jabber: Master has terminated.", loglevel=LL.WARNING)
            break

    # And exit once we're done
    logthis("*** Jabber terminating", loglevel=LL.INFO)
    jbx.disconnect(wait=True)
    sys.exit(0)


def setup(xconfig):
    """
    setup communication with Jabber process
    """
    global rdx, conf
    conf = xconfig
    rdx = db.redis({ 'host': conf.redis['host'], 'port': conf.redis['port'], 'db': conf.redis['db'] },
                   prefix=conf.redis['prefix'])


def send(method, params={}):
    """
    send command to jabber client process
    """
    global rdx, conf
    if conf.xmpp['user'] and conf.xmpp['pass']:
        rdx.lpush("jabber_out", json.dumps({ 'method': method, 'params': params }))


def recv(timeout=False):
    """
    check for incoming messages, blocking for specified amount of time
    timeout=False -- No waiting/blocking
    timeout=0 -- Block forever until a message is received
    timeout=X -- Where X is a positive integer, block for that number of seconds
    """
    global rdx
    if timeout is False:
        outmsg = rdx.rpop("jabber_in")
    else:
        outmsg = rdx.brpop("jabber_in", timeout)

    return outmsg


def master_alive(ppid):
    try:
        os.kill(ppid, 0)
    except OSError:
        return False
    else:
        return True


class XClient(ClientXMPP):
    host_override = ()
    avatar_path = None
    use_tls = True
    priority = 0
    nick = None
    redis = None
    ready = False

    def __init__(self, jid, password, priority=0, avatar_img=None, nick=None, auto_authsub=True,
                 host=None, port=5222, use_tls=True, use_sslv3=False, redis_con=None):
        # make parent class do the hard stuff
        super(XClient, self).__init__(jid, password)
        self.priority = priority
        self.nick = nick
        self.auto_authorize = auto_authsub
        self.auto_subscribe = auto_authsub
        self.redis = redis_con

        # Allow overriding SRV records (or specifying host if domain does not provide SRV records)
        if host is not None:
            self.host_override = (host, int(port))

        # Force SSLv3 if required by server (OpenFire)
        self.use_tls = use_tls
        if use_sslv3 is True:
            self.ssl_version = ssl.PROTOCOL_SSLv3

        # Register event handlers
        self.add_event_handler("session_start", self.cb_session_start)
        self.add_event_handler("message", self.cb_message)

        # Register plugins to support various XEP caps
        self.register_plugin('xep_0004') # Data Forms <http://xmpp.org/extensions/xep-0004.html>
        self.register_plugin('xep_0012') # Last Activity <http://xmpp.org/extensions/xep-0012.html>
        self.register_plugin('xep_0020') # Feature Negotiation <http://xmpp.org/extensions/xep-0020.html>
        self.register_plugin('xep_0030') # Service Discovery <http://xmpp.org/extensions/xep-0030.html>
        self.register_plugin('xep_0045') # Multi-User Chat (MUC) <http://xmpp.org/extensions/xep-0045.html>
        self.register_plugin('xep_0084') # User Avatar <http://xmpp.org/extensions/xep-0084.html>
        self.register_plugin('xep_0092') # Software Version <http://xmpp.org/extensions/xep-0092.html>
        self.register_plugin('xep_0153') # vCard-based Avatars <http://xmpp.org/extensions/xep-0153.html>
        self.register_plugin('xep_0199') # XMPP Ping <http://xmpp.org/extensions/xep-0199.html>

        # Set client version
        self['xep_0030'].add_identity("client", "bot", "Rainwatch")
        self['xep_0092'].software_name = "Rainwatch (SleekXMPP {})".format(sleekxmpp_version)
        self['xep_0092'].version = "{} ({})".format(__version__, __date__)
        self['xep_0092'].os = os.uname().sysname

        if avatar_img is not None:
            self.avatar_path = os.path.realpath(os.path.expanduser(avatar_img))

        self.connect()

    def connect(self):
        """connect to XMPP server using initialized parameters"""
        super(XClient, self).connect(address=self.host_override, use_tls=self.use_tls)

    def cb_session_start(self, event):
        """session_start callback"""
        try:
            self.send_presence(pshow=None, ppriority=self.priority, pnick=self.nick)
            self.get_roster()
        except IqError as e:
            logthis("iq error:", suffix=iq['error']['condition'], loglevel=LL.ERROR)
            logexc(e, "Session start failed:", prefix="session_start")
            self.disconnect()
        except IqTimeout as e:
            logexc(e, "Connection timed out:", prefix="session_start")
            self.disconnect()

        # If provided, set avatar from supplied image
        if self.avatar_path is not None:
            self.set_avatar()

        # We ready!
        self['xep_0012'].set_last_activity()
        self.set_status(None, "Ready")
        self.ready = True
        logthis("XMPP initialization complete. Ready.", loglevel=LL.VERBOSE)

    def cb_message(self, msg):
        """message callback"""
        if msg['type'] in ('chat', 'normal'):
            logthis("Got message from", suffix=str(msg['from']), loglevel=LL.DEBUG)
            tmsg = {
                    'id': msg['id'],
                    'thread': msg['thread'],
                    'type': msg['type'],
                    'to': str(msg['to']),
                    'from': str(msg['from']),
                    'subject': msg['subject'],
                    'body': str(msg['body']),
                    'time': time.time()
                   }

            # push the message onto the jabber_in message stack
            if self.redis:
                self.redis.lpush("jabber_in", json.dumps(tmsg))

    def set_status(self, show=None, status=None):
        """
        set status and send presence notification
        @show in ("dnd", "xa", "away", None, "chat"); default None (Available)
        @status is the extra status message
        """
        self.send_presence(pshow=show, pstatus=status, ppriority=self.priority, pnick=self.nick)

    def set_avatar(self, imgpath=None, resize=False):
        """publish avatar from image at supplied path @imgpath"""
        if imgpath:
            self.avatar_path = os.path.realpath(os.path.expanduser(imgpath))

        try:
            with open(self.avatar_path, 'rb') as f:
                idata = f.read()
                ilen = os.stat(self.avatar_path).st_size
            with Image.open(self.avatar_path) as img:
                isize = img.size
                imime = Image.MIME[img.format]
        except FileNotFoundError:
            logthis("Failed to load avatar from image. File not found:", suffix=self.avatar_path, loglevel=LL.ERROR)
            return False
        except OSError as e:
            logexc(e, "Failed to load avatar from image")
            return False

        # Publish avatar as described in XEP-0084
        xep84 = False
        try:
            self['xep_0084'].publish_avatar(idata)
            xep84 = True
        except XMPPError:
            logthis("Failed to publish XEP-0084 avatar data", loglevel=LL.WARNING)

        # Update vCard entry with new avatar (XEP-0153)
        try:
            self['xep_0153'].set_avatar(avatar=idata, mtype=imime)
            logthis("Updated vCard entry with new avatar", loglevel=LL.DEBUG)
        except XMPPError:
            logthis("Failed to update vCard entry with new avatar", loglevel=LL.WARNING)

        if xep84 is True:
            try:
                imetadata = {'id': self['xep_0084'].generate_id(idata), 'type': imime, 'bytes': ilen}
                self['xep_0084'].publish_avatar_metadata([imetadata])
            except XMPPError:
                logthis("Failed to publish XEP-0084 avatar metadata", loglevel=LL.WARNING)
                return False

        return True

