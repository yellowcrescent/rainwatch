#!/usr/bin/env python
# coding=utf-8
###############################################################################
#
# daemon - rwatch/daemon.py
# Rainwatch: API Service Daemon
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
import signal
import time
from setproctitle import setproctitle
from flask import Flask,json,jsonify,make_response,request

# Logging & Error handling
from rwatch.logthis import *

from rwatch import queue,jabber,db,deluge
from rwatch.util import *

# rainwatch server Flask object
xsrv = None
rdx = None
dlx = None
conf = None

def start(bind_ip="0.0.0.0",bind_port=4464,fdebug=False):
    """
    Start Rainwatch daemon
    """
    global rdx,dlx,xsrv,conf
    conf = __main__.xsetup.config

    # first, fork
    if not conf['srv']['nofork']: dfork()

    # set process title
    setproctitle("rainwatch: master process (%s:%d)" % (bind_ip, bind_port))
    pidfile_set()

    # spawn queue runners
    queue.start('xfer')

    # spawn jabber handler
    if conf['xmpp']['user'] and conf['xmpp']['pass']:
        jabber.spawn()
    else:
        logthis("!! Not spawning Jabber client, no JID defined in rc file",loglevel=LL.WARNING)

    # connect to Redis
    rdx = db.redis({ 'host': conf['redis']['host'], 'port': conf['redis']['port'], 'db': conf['redis']['db'] },prefix=conf['redis']['prefix'])

    # connect to Deluge
    dlx = deluge.delcon(conf['deluge']['user'], conf['deluge']['pass'], conf['deluge']['hostname'], int(conf['deluge']['port']))

    # create flask object, and map API routes
    xsrv = Flask('rainwatch')
    xsrv.add_url_rule('/','root',view_func=route_root,methods=['GET'])
    xsrv.add_url_rule('/api/auth','auth',view_func=route_auth,methods=['GET','POST'])
    xsrv.add_url_rule('/api/chook','chook',view_func=route_chook,methods=['GET','POST','PUT'])
    xsrv.add_url_rule('/api/torrent/list','torrent_list',view_func=torrent_list,methods=['GET','POST'])
    xsrv.add_url_rule('/api/torrent/getinfo','torrent_getinfo',view_func=torrent_getinfo,methods=['GET','POST'])

    # start flask listener
    logthis("Starting Flask...",loglevel=LL.VERBOSE)
    xsrv.run(bind_ip,bind_port,fdebug,use_evalex=False)

def dfork():
    """Fork into the background"""
    logthis("Forking...",loglevel=LL.DEBUG)
    try:
        # first fork
        pid = os.fork()
    except OSError, e:
        logthis("os.fork() failed:",suffix=e,loglevel=LL.ERROR)
        failwith(ER.PROCFAIL, "Failed to fork into background. Aborting.")
    if (pid == 0):
        # become parent of session & process group
        os.setsid()
        try:
            # second fork
            pid = os.fork()
        except OSError, e:
            logthis("os.fork() [2] failed:",suffix=e,loglevel=LL.ERROR)
            failwith(ER.PROCFAIL, "Failed to fork into background. Aborting.")
        if pid:
            # ... and kill the other parent
            os._exit(0)

        logthis("** Forked into background. PID:",suffix=os.getpid(),loglevel=LL.INFO)
        # Redirect stdout & stderr to /dev/null
        sys.stdout.flush()
        sys.stdout = open(os.devnull,'w')
        sys.stderr.flush()
        sys.stderr = open(os.devnull,'w')
    else:
        # otherwise, kill the parent; _exit() so we don't mess with any
        # open file handles or streams; sleep for 0.5s to let the
        # "forked into background" message appear before the bash
        # prompt is given back to the user
        time.sleep(0.5)
        os._exit(0)

def dresponse(objx,rcode=200):
    rx = make_response(pjson(objx),rcode)
    rx.headers['Content-Type'] = "application/json; charset=utf-8"
    rx.headers['Server'] = "rainwatch/"+__main__.xsetup.version
    rx.headers['Accept'] = 'application/json'
    return rx

def precheck(rheaders=False,require_ctype=True):
    # Check for proper Content-Type
    if require_ctype:
        try:
            ctype = request.headers['Content-Type']
        except KeyError:
            ctype = None
        if not re.match('^(application\/json|text\/x-json)', ctype, re.I):
            logthis("Content-Type mismatch. Not acceptable:",suffix=ctype,loglevel=LL.WARNING)
            if rheaders: return ({ 'status': "error", 'error': "json_required", 'message': "Content-Type must be application/json" }, "417 Content Mismatch")
            else: return False

    # Check authentication
    try:
        wauth = request.headers['WWW-Authenticate']
    except KeyError:
        wauth = None
    skey = __main__.xsetup.config['srv']['shared_key']
    if wauth:
        if wauth == skey:
            logthis("Authentication passed",loglevel=LL.VERBOSE)
            if rheaders: return ({ 'status': "ok" }, "212 Login Validated")
            else: return True
        else:
            logthis("Authentication failed; invalid credentials",loglevel=LL.WARNING)
            if rheaders: return ({ 'status': "error", 'error': "auth_fail", 'message': "Authentication failed" }, "401 Unauthorized")
            else: return False
    else:
        logthis("Authentication failed; WWW-Authenticate header missing from request",loglevel=LL.WARNING)
        if rheaders: return ({ 'status': "error", 'error': "www_authenticate_header_missing", 'message': "Must include WWW-Authenticate header" }, "400 Bad Request")
        else: return False

def pjson(oin):
    return json.dumps(oin,indent=4,separators=(',', ': '))

def pidfile_set():
    pfname = __main__.xsetup.config['srv']['pidfile']
    try:
        fo = open(pfname,"w")
        fo.write("%d\n" % os.getpid())
        fo.close()
    except:
        logthis("Failed to write data to PID file:",suffix=pfname,loglevel=LL.ERROR)
        failwith(PROCFAIL,"Ensure write permission at the PID file location.")

def make_fail(errorname,message,rcode="400 Bad Request"):
    return ({ 'status': "error", 'error': errorname, 'message': message }, rcode)

def make_success(indata,rcode="200 OK"):
    return ({ 'status': "ok", 'result': indata }, rcode)

###############################################################################
##
## Routes
##

def route_root():
    rinfo = {
                'app': "rainwatch",
                'description': "Deluge download manager and RPC client",
                'version': __main__.xsetup.version,
                'date': __main__.xsetup.vdate,
                'author': "J. Hipps <jacob@ycnrg.org>",
                'copyright': "Copyright (c) 2016 J. Hipps/Neo-Retro Group",
                'license': "MIT"
            }
    return dresponse(rinfo)


def route_auth():
    return dresponse(*precheck(rheaders=True))


def route_chook():
    global rdx
    logthis(">> Received chook request",loglevel=LL.VERBOSE)

    if precheck():
        indata = request.json
        jobid = queue.enqueue(rdx,"xfer",indata.get('thash',False),indata.get('opts',False))
        resp = dresponse({ 'status': "ok", 'message': "Queued as job %s" % (jobid) }, "201 Queued")
    else:
        resp = dresponse(*precheck(rheaders=True))

    return resp


def torrent_list():
    global rdx, dlx

    if precheck():
        # get list of torrents
        resp = dresponse(*make_success(dlx.getTorrentList(filter={})))
    else:
        resp = dresponse(*precheck(rheaders=True))

    return resp


def torrent_getinfo():
    global rdx, dlx

    # get list of torrents
    if precheck():
        indata = request.json
        tid = indata.get('id', False)
        if tid:
            resp = dresponse(*make_success(dlx.getTorrentList(filter={ 'id': tid },fields=[])))
        else:
            resp = dresponse(*make_fail("missing_params", "Required parameter 'id' is missing from request"))
    else:
        resp = dresponse(*precheck(rheaders=True))

    return resp
