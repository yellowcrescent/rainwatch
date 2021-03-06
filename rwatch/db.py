#!/usr/bin/env python3.5
# coding=utf-8
"""

rwatch.db
Rainwatch > Database interface

Copyright (c) 2016 J. Hipps / Neo-Retro Group
https://ycnrg.org/

@author     Jacob Hipps <jacob@ycnrg.org>
@repo       https://git.ycnrg.org/projects/YRW/repos/rainwatch

"""

from urllib.parse import urlparse

from pymongo import MongoClient
from pymongo.errors import *
import redis as xredis

#from rwatch.logthis import *
#from rwatch.logthis import LL, ER, logthis, logexc, failwith


class mongo:
    """Hotamod class for handling Mongo stuffs"""
    xcon = None
    xcur = None
    silence = False

    def __init__(self, uri=None, silence=False):
        """Initialize and connect to MongoDB"""
        from rwatch.logthis import LL, ER, C, logthis, logexc, failwith
        self.silence = silence
        try:
            self.xcon = MongoClient(uri)
        except InvalidURI as e:
            logexc(e, "Invalid mongodb URI (%s)" % (uri))
            failwith(ER.CONF_BAD, "Invalid MongoDB configuration")
        except ConfigurationError as e:
            logexc(e, "Invalid mongodb URI (%s)" % (uri))
            failwith(ER.CONF_BAD, "Invalid MongoDB configuration")
        except Exception as e:
            logexc(e, "Failed to connect to MongoDB (%s)" % (uri))
            failwith(ER.CONF_BAD, "Unable to connect to MongoDB. Please check configuration.")

        muri = urlparse(uri)
        if len(muri.path) > 1:
            self.xcur = self.xcon[muri.path[1:]]
            if not self.silence: logthis("Connected to Mongo OK", loglevel=LL.DEBUG, ccode=C.GRN)
        else:
            logthis("MongoDB URI provided does not include a database (example: 'mongodb://localhost/mydatabase')",
                    loglevel=LL.ERROR)
            failwith(ER.CONF_BAD, "Invalid MongoDB configuration")

    def find(self, collection, query):
        xresult = {}
        xri = 0
        for tresult in self.xcur[collection].find(query):
            xresult[xri] = tresult
            xri += 1
        return xresult

    def update_set(self, collection, monid, setter):
        try:
            self.xcur[collection].update({'_id': monid}, {'$set': setter})
        except Exception as e:
            #logthis("Failed to update document(s) in Mongo --", loglevel=LL.ERROR, suffix=e)
            pass

    def upsert(self, collection, monid, indata):
        try:
            self.xcur[collection].update({'_id': monid}, indata, upsert=True)
        except Exception as e:
            #logthis("Failed to upsert document in Mongo --", loglevel=LL.ERROR, suffix=e)
            pass

    def findOne(self, collection, query):
        return self.xcur[collection].find_one(query)

    def insert(self, collection, indata):
        return self.xcur[collection].insert_one(indata).inserted_id

    def insert_many(self, collection, indata):
        return self.xcur[collection].insert_many(indata).inserted_ids

    def count(self, collection):
        return self.xcur[collection].count()

    def getone(self, collection, start=0):
        for trez in self.xcur[collection].find().skip(start).limit(1):
            return trez

    def delete(self, collection, query):
        return self.xcur[collection].delete_one(query)

    def get_collections(self):
        return self.xcur.collection_names()

    def create_collection(self, collection, **kwargs):
        return self.xcur.create_collection(collection, **kwargs)

    def close(self):
        if self.xcon:
            self.xcon.close()

    def __del__(self):
        """Disconnect from MongoDB"""
        if self.xcon:
            self.xcon.close()


class redis:
    """Hotamod class for Redis stuffs"""
    rcon = None
    rpipe = None
    conndata = {}
    rprefix = 'hota'
    silence = False

    def __init__(self, cdata={}, prefix='', silence=False):
        """Initialize Redis"""
        from rwatch.logthis import LL, ER, C, logthis, logexc, failwith
        self.silence = silence
        if cdata:
            self.conndata = cdata
        if prefix:
            self.rprefix = prefix
        try:
            self.rcon = xredis.Redis(encoding='utf-8', decode_responses=True, **self.conndata)
        except Exception as e:
            logthis("Error connecting to Redis", loglevel=LL.ERROR, suffix=e)
            return

        if not self.silence:
            logthis("Connected to Redis OK", loglevel=LL.INFO, ccode=C.GRN)


    def set(self, xkey, xval, usepipe=False, noprefix=False):
        if noprefix: zkey = xkey
        else:        zkey = '%s:%s' % (self.rprefix, xkey)
        if usepipe:
            xrez = self.rpipe.set(zkey, xval)
        else:
            xrez = self.rcon.set(zkey, xval)
        return xrez

    def setex(self, xkey, xval, expiry, usepipe=False, noprefix=False):
        if noprefix: zkey = xkey
        else:        zkey = '%s:%s' % (self.rprefix, xkey)
        if usepipe:
            xrez = self.rpipe.setex(zkey, xval, expiry)
        else:
            xrez = self.rcon.setex(zkey, xval, expiry)
        return xrez

    def get(self, xkey, usepipe=False, noprefix=False):
        if noprefix: zkey = xkey
        else:        zkey = '%s:%s' % (self.rprefix, xkey)
        if usepipe:
            xrez = self.rpipe.set(zkey)
        else:
            xrez = self.rcon.get(zkey)
        return xrez

    def incr(self, xkey, usepipe=False):
        if usepipe:
            xrez = self.rpipe.incr('%s:%s' % (self.rprefix, xkey))
        else:
            xrez = self.rcon.incr('%s:%s' % (self.rprefix, xkey))
        return xrez

    def exists(self, xkey, noprefix=False):
        return self.rcon.exists('%s:%s' % (self.rprefix, xkey))

    def keys(self, xkey, noprefix=False):
        if noprefix: zkey = xkey
        else:        zkey = '%s:%s' % (self.rprefix, xkey)
        return self.rcon.keys(zkey)

    def makepipe(self):
        try:
            self.rpipe = self.rcon.pipeline()
        except Exception as e:
            #logthis("Error creating Redis pipeline", loglevel=LL.ERROR, suffix=e)
            pass

    def execpipe(self):
        if self.rpipe:
            self.rpipe.execute()
            #logthis("Redis: No pipeline to execute", loglevel=LL.ERROR)

    def count(self):
        return self.rcon.dbsize()

    def lrange(self, qname, start, stop):
        return self.rcon.lrange(self.rprefix+":"+qname, start, stop)

    def llen(self, qname):
        return self.rcon.llen(self.rprefix+":"+qname)

    def lpop(self, qname):
        return self.rcon.lpop(self.rprefix+":"+qname)

    def lpush(self, qname, xval):
        return self.rcon.lpush(self.rprefix+":"+qname, xval)

    def rpop(self, qname):
        return self.rcon.rpop(self.rprefix+":"+qname)

    def rpush(self, qname, xval):
        return self.rcon.rpush(self.rprefix+":"+qname, xval)

    def blpop(self, qname, timeout=0):
        return self.rcon.blpop(self.rprefix+":"+qname, timeout)

    def brpop(self, qname, timeout=0):
        return self.rcon.brpop(self.rprefix+":"+qname, timeout)

    def brpoplpush(self, qsname, qdname, timeout=0):
        return self.rcon.brpoplpush(self.rprefix+":"+qsname, self.rprefix+":"+qdname, timeout)

    def __del__(self):
        pass
        #if not self.silence: logthis("Disconnected from Redis")

