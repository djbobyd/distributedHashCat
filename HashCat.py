#!/usr/bin/env python

#  Copyright (c) 2005, Corey Goldberg
#
#  SSHController.py is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.

 
"""

@author: Corey Goldberg
@copyright: (C) 2005 Corey Goldberg
@license: GNU General Public License (GPL)
"""


import paramiko, os
import time, logging.config, yaml
from threading import Thread

config = yaml.load(open(os.path.join(os.path.dirname(__file__),'log.yml'), 'r'))
logging.config.dictConfig(config)
log = logging.getLogger('hashcat')

stream = file(os.path.join(os.path.dirname(__file__),'config.yml'), 'r')
config = yaml.load(stream)

class SSHController():
        
    """Connect to remote host with SSH and execute and control hashcat.
    
    This is a facade/wrapper that uses paramiko to spawn and control an SSH client. 
    You must have OpenSSH installed. 
        
    @ivar host_name: Host name or IP address
    @ivar user_name: User name 
    @ivar password: Password
    @ivar prompt: Command prompt (or partial string matching the end of the prompt)
    @ivar ssh: Instance of a paramiko.SSHClient object
    """
        
    def __init__(self, host_name, user_name, password,command='',results=None):
        """
        @param host_name: Host name or IP address
        @param user_name: User name 
        @param password: Password
        @param command: The hashcat command that have to be executed
        @param results: A list that will contain the results once this thread is completed.
         
        """  
        self.results=results
        self.host_name = host_name
        self.user_name = user_name
        self.password = password
        self.port = 22  #default SSH port
        self.chan = None
        self.command = command
        self.connection = None
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.status = None
        self.progress = None
        self.elapsed_time = None
        self.estimated_time = None
        self.interval = int(config["heartbeat_timeout"])
        self.be_alive = False
        self.aborted = False
        self.last_output= ''
    
    def __str__(self) :
        #return str(self.__dict__)
        return str({"host_name":self.host_name, "user_name":self.user_name})

    def __eq__(self, other) : 
        return self.__dict__ == other.__dict__
    
    def set_aborted(self,value):
        self.aborted = value
        
    def set_command(self,value):
        self.command = value
    
    def __call__(self):
        if not self.check_host():
            return
        self.login()
        self.run_command(self.command)
        self.ping()
        self.logout()
        self.fill_results()
        
    def fill_results(self):
        if self.results <> None:
            self.results.set_host_name(self.host_name)
            self.results.set_user_name(self.user_name)
            self.results.set_password(self.password)
            self.results.set_command(self.command) 
            self.results.set_status(self.status)
            self.results.set_progress(self.progress)
            self.results.set_elapsed_time(self.elapsed_time)
            self.results.set_estimated_time(self.estimated_time)
            self.results.set_be_alive(self.be_alive)
            self.results.set_aborted(self.aborted)
            self.results.set_last_output(self.last_output)
        
    def login(self):
        """Connect to a remote host and login.
            
        """
        #self.ssh.load_system_host_keys()
        #self.ssh.set_missing_host_key_policy(paramiko.WarningPolicy)
        log.debug("Making connection to remote host: %s with user: %s" % (self.host_name, self.user_name))
        self.connection = self.ssh.connect(self.host_name,self.port, self.user_name, self.password)
        log.debug("Starting Shell!")
        self.chan = self.ssh.invoke_shell()
        log.debug("Connection established!")

    def run_command(self, command):
        """Run a command on the remote host.
            
        @param command: Unix command
        @return: Command output
        @rtype: String
        """ 
        log.debug("sending command: '%s' to host" % command)
        self.chan.send(command+'\n')
        time.sleep(5)
        self.be_alive = True
        self.read_proc()
        #self.thread = thread.start_new_thread(self.ping,())
        #self.stdin, self.stdout, self.stderr=self.ssh.exec_command(command)
        return self.chan.send_ready()
    
    def check_host(self):
        try:
            log.debug("Making connection to remote host: %s with user: %s" % (self.host_name, self.user_name))
            self.connection = self.ssh.connect(self.host_name,self.port, self.user_name, self.password)
            log.debug("Starting Shell!")
            self.chan = self.ssh.invoke_shell()
            self.ssh.close()
            log.debug("Host is alive and running!")
        except Exception:
            log.error("A connection to the host cannot be established!!!")
            return False
        return True
    
    def ping(self):
        log.debug("Heartbeat is: %s and override is: %s" % (self.be_alive, self.aborted))
        while self.be_alive and not self.aborted:
            self.write_proc("s")
            self.read_proc()
            log.debug("Sleeping for %d seconds" % self.interval)
            time.sleep(self.interval)
        
    def parse(self, lines):
        line_arr=lines.splitlines()
        log.debug("Lines array: %s" % line_arr)
        for line in line_arr:
            if line.startswith("Status."):
                self.status=line.split(":")[1].strip()
                for case in switch(self.status):
                    if case('Running'):
                        self.be_alive=True
                        break
                    if case('Finished'):
                        self.be_alive=False
                        break
                    if case('Cracked'):
                        self.be_alive=False
                        self.get_result(lines)
                        break
                    if case('Aborted'):
                        self.be_alive=False
                        break
                    if case('Initializing'):
                        self.be_alive=True
                        break
                    if case():
                        log.warning("Unexpected value: %s" % self.status)
                continue 
            if line.startswith("Progress."):
                self.progress=line[line.find("(")+1:-1]
                continue
            if line.startswith("Time.Running."):
                self.elapsed_time=line.split(":")[1].strip()
                continue
            if line.startswith("Time.Left."):
                self.estimated_time=line.split(":")[1].strip()
                continue
            if [True for i in ["$ ","$ s","# ","# s","ss"] if lines.endswith(i)]:
                self.last_output=line_arr
                self.be_alive=False
                continue
            log.warning("Line cannot be recognized: %s" % line)
                

    
    def stop_proc(self):
        log.info("Sending stop command to process...")
        self.be_alive = False
        self.write_proc("q")
        self.read_proc()
    
    def read_proc(self):
        lines=''
        while not [True for i in ["=> ","$ ","$ s","# ","# s","ss"] if lines.endswith(i)]:
            try:
                log.debug("Channel receive status: %s" % self.chan.recv_ready())
                if self.chan.recv_ready():
                    line=self.chan.recv(9999)
                else:
                    break
                lines=lines+''.join(line)
            except (RuntimeError, IOError):
                print "Stream not ready!!!"
        self.parse(lines)
        
    def write_proc(self, message):
        if self.chan.send_ready():
            log.debug("Sending message: %s through the channel..." % message)
            self.chan.send(message)
            return True
        else:
            return False
    
    def get_result(self, lines):
        return self.results
    
    def logout(self):
        """
        Close the connection to the remote host.    
        """
        log.info("closing connection to host %s" % self.host_name)
        self.ssh.close()

class switch(object):
    def __init__(self, value):
        self.value = value
        self.fall = False

    def __iter__(self):
        """Return the match method once, then stop"""
        yield self.match
        raise StopIteration
    
    def match(self, *args):
        """Indicate whether or not to enter a case suite"""
        if self.fall or not args:
            return True
        elif self.value in args: # changed for v1.5, see below
            self.fall = True
            return True
        else:
            return False
      
class results():

        def get_host_name(self):
            return self.__host_name


        def get_user_name(self):
            return self.__user_name


        def get_password(self):
            return self.__password


        def get_command(self):
            return self.__command


        def get_status(self):
            return self.__status


        def get_progress(self):
            return self.__progress


        def get_elapsed_time(self):
            return self.__elapsed_time


        def get_estimated_time(self):
            return self.__estimated_time


        def get_be_alive(self):
            return self.__be_alive


        def get_aborted(self):
            return self.__aborted


        def get_last_output(self):
            return self.__last_output


        def set_host_name(self, value):
            self.__host_name = value


        def set_user_name(self, value):
            self.__user_name = value


        def set_password(self, value):
            self.__password = value


        def set_command(self, value):
            self.__command = value


        def set_status(self, value):
            self.__status = value


        def set_progress(self, value):
            self.__progress = value


        def set_elapsed_time(self, value):
            self.__elapsed_time = value


        def set_estimated_time(self, value):
            self.__estimated_time = value


        def set_be_alive(self, value):
            self.__be_alive = value


        def set_aborted(self, value):
            self.__aborted = value


        def set_last_output(self, value):
            self.__last_output = value


        def del_host_name(self):
            del self.__host_name


        def del_user_name(self):
            del self.__user_name


        def del_password(self):
            del self.__password


        def del_command(self):
            del self.__command


        def del_status(self):
            del self.__status


        def del_progress(self):
            del self.__progress


        def del_elapsed_time(self):
            del self.__elapsed_time


        def del_estimated_time(self):
            del self.__estimated_time


        def del_be_alive(self):
            del self.__be_alive


        def del_aborted(self):
            del self.__aborted


        def del_last_output(self):
            del self.__last_output

        host_name = ''
        user_name = ''
        password = ''
        command = ''
        status = ''
        progress = ''
        elapsed_time = ''
        estimated_time = ''
        be_alive = None
        aborted = None
        last_output = ''
        host_name = property(get_host_name, set_host_name, del_host_name, "host_name's docstring")
        user_name = property(get_user_name, set_user_name, del_user_name, "user_name's docstring")
        password = property(get_password, set_password, del_password, "password's docstring")
        command = property(get_command, set_command, del_command, "command's docstring")
        status = property(get_status, set_status, del_status, "status's docstring")
        progress = property(get_progress, set_progress, del_progress, "progress's docstring")
        elapsed_time = property(get_elapsed_time, set_elapsed_time, del_elapsed_time, "elapsed_time's docstring")
        estimated_time = property(get_estimated_time, set_estimated_time, del_estimated_time, "estimated_time's docstring")
        be_alive = property(get_be_alive, set_be_alive, del_be_alive, "be_alive's docstring")
        aborted = property(get_aborted, set_aborted, del_aborted, "aborted's docstring")
        last_output = property(get_last_output, set_last_output, del_last_output, "last_output's docstring")

        
        