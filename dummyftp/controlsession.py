from __future__ import division
from __future__ import absolute_import
from __future__ import unicode_literals
from future.builtins import (str, bytes)

from future.backports.socketserver import BaseRequestHandler

import logging
import socket

class ControlSession(BaseRequestHandler):
    def __init__(self, request, client_address, server):
        self.file_system = server.file_system
        self.users = server.users
        self.sess_user = None
        self.sess_auth = False
        self.sess_path = '/'
        self.sess_home = '/'
        self.sess_binary = False
        self.sess_data = None
        self.data_socket = None

        BaseRequestHandler.__init__(self, request, client_address, server)

    def setup(self):
        BaseRequestHandler.setup(self)

        self.id = self.server.counter
        self.server.counter = self.server.counter + 1

        logging.info('[SOCKET:{}] Client {} has connected'.format(self.id, self.client_address))

    def handle(self):
        self.sendControlResponse('220 (vsFTPd 2.2.2)')
        cmd = ''
        while True:
            try:
                line = self.request.recv(1024)
            except:
                break
            if not line:
                break
            line = str(line,'utf-8').rstrip()
            cmd_parts = line.split(' ', 1)
            cmd = cmd_parts[0].upper()
            arg = cmd_parts[1] if len(cmd_parts)>1 else ''

            logging.info('[RECV:{}] {}'.format(self.id, line.replace('\r','\\r').replace('\n','\\n').replace('\t','\\t')))
            if cmd:
                resp = self.ftpCommand(cmd, arg)
                if resp == 'QUIT':
                    break
                elif resp:
                    self.sendControlResponse(resp)

        self.sendControlResponse('221 Goodbye.')

    def finish(self):
        logging.info('[SOCKET:{}] Client {} has disconnected'.format(self.id, self.client_address))
        if self.data_socket:
            self.data_socket.close()


    def sendControlResponse(self, response):
        try:
            line = self.request.sendall(bytes(response+'\r\n','utf-8'))
            logging.info("[SEND:{}] {}".format(self.id, response.replace('\r','\\r').replace('\n','\\n').replace('\t','\\t')))
        except:
            pass

    def ftpCommand(self, cmd, arg):
        #QUIT <CRLF> ####################################################
        if cmd == 'QUIT':
            return 'QUIT'

        #USER <SP> <username> <CRLF> ####################################################
        elif cmd == 'USER':
            if self.sess_auth:
                return '530 Can\'t change to another user.';
            elif arg in self.users:
                self.sess_user = arg
                return '331 Please specify the password.'
            else:
                self.sess_user = None
                return '530 Permission denied.'

        elif self.sess_user is None:
            return '503 Login with USER first.'

        #PASS <SP> <password> <CRLF> ####################################################
        elif cmd == 'PASS':
            if self.sess_auth:
                return '230 Already logged in.';
            elif 'pass' not in self.users[self.sess_user] or self.users[self.sess_user]['pass'] == arg:
                self.sess_auth = True
                if 'home' in self.users[self.sess_user]:
                    self.sess_home = self.users[self.sess_user]['home']
                
                self.sess_path = self.sess_home
                return '230 Login successful.'
            else:
                self.sess_user = None
                return '530 Login incorrect.'
        elif not self.sess_auth:
            return '530 Please login with USER and PASS.'

        #PWD  <CRLF> ####################################################
        elif cmd == 'PWD':
            return '257 "{}"'.format(self.sess_path)

        #CWD  <SP> <pathname> <CRLF> ####################################################
        elif cmd == 'CWD':
            new_path = self.file_system.resolve(self.sess_path, arg, self.sess_home)

            if new_path and self.file_system.isDir(new_path):
                self.sess_path = new_path
                return '250 Directory successfully changed.'
            else:
                return '550 Failed to change directory.'

        #SYST <CRLF> ####################################################
        elif cmd == 'SYST':
            return '215 UNIX Type: L8'

        #FEAT <CRLF> ####################################################
        elif cmd == 'FEAT':
            out  = '211-Features:\n'
            out += ' EPRT\n'
            out += ' EPSV\n'
            out += ' MDTM\n'
            out += ' PASV\n'
            out += ' REST STREAM\n'
            out += ' SIZE\n'
            out += ' TVFS\n'
            out += ' UTF8\n'
            out += '211 End'
            return out

        #OPTS [<SP> <pathname>] <CRLF> ####################################################
        elif cmd == 'OPTS':
            return '200 Always in UTF8 mode.'

        #TYPE <SP> <type-code> <CRLF> ####################################################
        elif cmd == 'TYPE':
            if arg == 'A' or arg == 'A N':
                self.sess_binary = False
                return '200 Switching to ASCII mode.'
            elif arg == 'I' or arg == 'L 8':
                self.sess_binary = True
                return '200 Switching to Binary mode.'
            else:
                return '500 Unrecognised TYPE command.'

        #EPSV <CRLF> ####################################################
        #PASV <CRLF> ####################################################
        elif cmd == 'PASV' or cmd == 'EPSV':
            if self.data_socket:
                self.data_socket.close()

            if cmd == 'PASV' and self.server.address_family != socket.AF_INET:
                return '522 Bad network protocol.'
            elif cmd == 'EPSV' and self.server.address_family != socket.AF_INET6:
                return '522 Bad network protocol.'


            serversocket = socket.socket(self.server.address_family, socket.SOCK_STREAM) 
            serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            serversocket.bind(('', 0))

            port = serversocket.getsockname()[1]
            serversocket.listen(1)

            self.data_socket = serversocket

            if cmd == 'PASV':
                host = self.request.getsockname()[0]
                parts = host.split('.')
                parts.append(int(port/256))
                parts.append(port%256)
                return '227 Entering Passive Mode ({},{},{},{},{},{}).'.format(*(parts))
            elif cmd == 'EPSV':
                return '229 Entering Extended Passive Mode (|||{}|).'.format(port)


        #LIST [<SP> <pathname>] <CRLF> ####################################################
        elif cmd == 'LIST':
            if self.data_socket is None:
                return '425 Use PORT or PASV first.'
            serversocket = self.data_socket
            
            (clientsocket, address) = serversocket.accept()
            self.sendControlResponse('150 Here comes the directory listing.')
            clientsocket.sendall(str(self.file_system.list(self.sess_path)).encode('utf-8'))
            serversocket.close()
            self.data_socket = None
            return '226 Directory send OK.'

        #RETR <SP> <pathname> <CRLF> ####################################################
        elif cmd == 'RETR':
            if self.data_socket is None:
                return '425 Use PORT or PASV first.'

            serversocket = self.data_socket
            
            file_path = self.file_system.resolve(self.sess_path, arg, self.sess_home)

            if file_path is None or not self.file_system.isFile(file_path):
                return '550 Failed to open file.'

            (clientsocket, address) = serversocket.accept()
            file_path = self.file_system.resolve(self.sess_path, arg, self.sess_home)
            content = self.file_system.getFile(file_path)
            self.sendControlResponse('150 Opening BINARY mode data connection for token.txt ({} bytes).'.format(len(content)))
            clientsocket.sendall(bytes(content, 'utf-8'))
            serversocket.close()
            self.data_socket = None
            return '226 Transfer complete.'
        #SIZE <CRLF> ####################################################
        elif cmd == 'SIZE':
            file_path = self.file_system.resolve(self.sess_path, arg, self.sess_home)

            if file_path is None or not self.file_system.isFile(file_path):
                return '550 Could not get file size.'

            file_path = self.file_system.resolve(self.sess_path, arg, self.sess_home)
            content = self.file_system.getFile(file_path)
            return '213 {}'.format(len(content))
        #NOOP <CRLF> ####################################################
        elif cmd == 'NOOP':
            return '200 NOOP ok.'
        #Unknown Command ####################################################
        else:
            self.sendControlResponse('421 Server busy, please try later.')
            return 'QUIT'
        

        #ACCT <SP> <account-information> <CRLF>
        #CDUP <CRLF>
        #SMNT <SP> <pathname> <CRLF>
        #QUIT <CRLF>
        #REIN <CRLF>
        #PORT <SP> <host-port> <CRLF>
        
        #STRU <SP> <structure-code> <CRLF>
        #MODE <SP> <mode-code> <CRLF>
        #STOR <SP> <pathname> <CRLF>
        #STOU <CRLF>
        #APPE <SP> <pathname> <CRLF>
        #ALLO <SP> <decimal-integer>
        #[<SP> R <SP> <decimal-integer>] <CRLF>
        #REST <SP> <marker> <CRLF>
        #RNFR <SP> <pathname> <CRLF>
        #RNTO <SP> <pathname> <CRLF>
        #ABOR <CRLF>
        #DELE <SP> <pathname> <CRLF>
        #RMD  <SP> <pathname> <CRLF>
        #MKD  <SP> <pathname> <CRLF>
        #NLST [<SP> <pathname>] <CRLF>
        #SITE <SP> <string> <CRLF>
        #STAT [<SP> <pathname>] <CRLF>
        #HELP [<SP> <string>] <CRLF>
