#!/usr/bin/env python2

from __future__ import with_statement
from __future__ import absolute_import

import logging
import logging.handlers

import dummyftp.controlsession
import dummyftp.filesystem
import socket
import os
from future.backports.socketserver import TCPServer, ThreadingTCPServer

LOG_FILENAME = 'dummy_ftp.log'

logger = logging.getLogger()
logger.setLevel(logging.INFO)

logConsoleHandler = logging.StreamHandler()
formatter = logging.Formatter(u'%(levelname)s - %(asctime)s - %(message)s')
logConsoleHandler.setFormatter(formatter)
logger.addHandler(logConsoleHandler)

#handler = logging.handlers.TimedRotatingFileHandler(LOG_FILENAME, when='midnight', interval=1, utc=True)
#logger.addHandler(handler)

ftp_users = {
    'someuser':{
        'pass':'AAAbbb',
        'home':'/home/someuser'
    },
    'anonymous':{
    },
    '':{
        'pass':'',
        'home':'/home/someuser'
    },
}
ftp_files = {
    '?owner':'root',
    '?group':'root',
    '?perms':0o755,

    'home':{
        'someuser':{
            '?owner':'someuser',
            '?group':'someuser',
        }
    },
    'var':{
        'ftp':{
            'pub':{
                'derp.txt':'some content'
            }
        }
    }
}
dummyftp_fs = dummyftp.FileSystem(ftp_files)


class ThreadedTCPServer(ThreadingTCPServer, TCPServer):
    address_family = socket.AF_INET #AF_INET6
    daemon_threads = True
    allow_reuse_address = True
    

if __name__ == '__main__':
    server = ThreadedTCPServer(('', 21), dummyftp.ControlSession)
    server.file_system = dummyftp_fs
    server.users = ftp_users
    server.counter = 0
    try:
        logging.info('Starting up the server')
        server.serve_forever()
    except:
        logging.info('Shutting down the server')
        server.shutdown()
        