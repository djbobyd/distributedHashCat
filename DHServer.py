'''
Created on Aug 27, 2011

@author: boby
'''
import socket
import threading
import SocketServer

class ThreadedTCPRequestHandler(SocketServer.StreamRequestHandler):

    def handle(self):
        data = self.rfile.readline().strip()
        cur_thread = threading.currentThread()
        response = "%s: %s" % (cur_thread.getName(), data)
        self.wfile.write(response)

class ThreadedTCPServer(SocketServer.ThreadingMixIn, SocketServer.TCPServer):
    pass

def client(ip, port, message):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ip, port))
    sock.send(message)
    response = sock.recv(1024)
    print "Received: %s" % response
    sock.close()

if __name__ == "__main__":
    # Port 0 means to select an arbitrary unused port
    HOST, PORT = "localhost", 0

    server = ThreadedTCPServer((HOST, PORT), ThreadedTCPRequestHandler)
    ip, port = server.server_address

    # Start a thread with the server -- that thread will then start one
    # more thread for each request
    server_thread = threading.Thread(target=server.serve_forever)
    # Exit the server thread when the main thread terminates
    server_thread.setDaemon(True)
    server_thread.start()
    print "Server loop running in thread:", server_thread.getName()

    client(ip, port, "Hello World 1\n")
    client(ip, port, "Hello World 2\n")
    client(ip, port, "Hello World 3\n")

    server.shutdown()