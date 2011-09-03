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

class SSHController(Thread):
        
    """Connect to remote host with SSH and execute and control hashcat.
    
    This is a facade/wrapper that uses paramiko to spawn and control an SSH client. 
    You must have OpenSSH installed. 
        
    @ivar host_name: Host name or IP address
    @ivar user_name: User name 
    @ivar password: Password
    @ivar prompt: Command prompt (or partial string matching the end of the prompt)
    @ivar ssh: Instance of a paramiko.SSHClient object
    """
    conf = yaml.load(open(os.path.join(os.path.dirname(__file__),'log.yml'), 'r'))
    stream = file(os.path.join(os.path.dirname(__file__),'config.yml'), 'r')
    config = yaml.load(stream)
        
    def __init__(self, hostInfo,command='',result=None):
        """
        @param host_name: Host name or IP address
        @param user_name: User name 
        @param password: Password
        @param command: The hashcat command that have to be executed
        @param results: A list that will contain the results once this thread is completed.
         
        """
        Thread.__init__(self)
        if not os.path.exists('logs'):
            os.makedirs('logs')
        self.conf["handlers"][hostInfo.getHostName()+"_file"]={'filename': 'logs/'+hostInfo.getHostName()+'.log', 'formatter': 'detailed', 'backupCount': 3, 'class': 'logging.handlers.RotatingFileHandler', 'maxBytes': 1000000}
        self.conf["loggers"][hostInfo.getHostName()]={'level': 'DEBUG', 'propagate': False, 'handlers': ['threaded_console', hostInfo.getHostName()+'_file']}
        logging.config.dictConfig(self.conf)
        global log
        log = logging.LoggerAdapter(logging.getLogger(hostInfo.getHostName()),{'clientip': hostInfo.getHostName()})
        if result == None:
            self.results=results()
        else:    
            self.results=result
        self.results.set_host(hostInfo)
        self.results.set_command(command)
        self.chan = None
        self.connection = None
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.interval = int(self.config["heartbeat_timeout"])
        self.be_alive = False
        self.aborted = False

    def get_command_xcode(self):
        return self.results.get_command_xcode()

    
    def __str__(self) :
        #return str(self.__dict__)
        return str({"host_name":self.results.get_host().getHostName(), "user_name":self.results.get_host().getUserName()})

    def __eq__(self, other) : 
        return self.__dict__ == other.__dict__
    
    def set_aborted(self,value):
        self.aborted = value
        
    def set_command(self,value):
        self.results.set_command(value)
    
    def run(self):
        if not self.check_host():
            return
        self.login()
        self.run_command(self.results.get_command())
        self.ping()
        self.logout()
              
    def login(self):
        """Connect to a remote host and login.
            
        """

        log.debug("Making connection to remote host: %s with user: %s" % (self.results.get_host().getHostName(), self.results.get_host().getUserName()))
        self.connection = self.ssh.connect(self.results.get_host().getHostName(),self.results.get_host().getPort(), self.results.get_host().getUserName(), self.results.get_host().getPassword(), timeout=5)
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
        time.sleep(int(self.config["init_timeout"]))
        self.be_alive = True
        self.read_proc()
        return self.chan.send_ready()
    
    def check_host(self):
        log.debug("Start checking of host...")
        try:
            log.debug("Making connection to remote host: %s with user: %s" % (self.results.get_host().getHostName(), self.results.get_host().getUserName()))
            self.connection = self.ssh.connect(self.results.get_host().getHostName(),self.results.get_host().getPort(), self.results.get_host().getUserName(), self.results.get_host().getPassword(), timeout=5)
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
                self.results.set_status(line.split(":")[1].strip())
                for case in switch(self.results.get_status()):
                    if case('Running'):
                        self.be_alive=True
                        break
                    if case('Finished'):
                        self.be_alive=False
                        break
                    if case('Cracked'):
                        self.be_alive=False
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
                try:
                    self.results.set_progress(float(line[line.find("(")+1:-1]))
                except:
                    self.results.set_progress(-1.0)
                continue
            if line.startswith("Time.Running."):
                self.results.set_elapsed_time(self.parseTime(line.split(":")[1].strip()))
                continue
            if line.startswith("Time.Left."):
                self.results.set_estimated_time(self.parseTime(line.split(":")[1].strip()))
                continue
            if [True for i in ["$ ","$ s","# ","# s","ss"] if line.endswith(i)]:
                self.results.set_last_output(line_arr)
                self.be_alive=False
                self.evaluate_xcode()
                if self.results.get_command_xcode()!=0:
                    self.results.set_status("Error")
                continue
            log.warning("Line cannot be recognized: %s" % line)
                
    def parseTime(self,timeString):
        days=0
        hours=0
        minutes=0
        seconds=0
        time_arr=timeString.split(",")
        for timeLine in time_arr:
            if timeLine.strip().split(" ")[1].strip() in ["day","days"]:
                days=int(timeLine.strip().split(" ")[0].strip())
            if timeLine.strip().split(" ")[1].strip() in ["hour","hours"]:
                hours=int(timeLine.strip().split(" ")[0].strip())
            if timeLine.strip().split(" ")[1].strip() in ["min","mins"]:
                minutes=int(timeLine.strip().split(" ")[0].strip())
            if timeLine.strip().split(" ")[1].strip() in ["sec","secs"]:
                seconds=int(timeLine.strip().split(" ")[0].strip())
        return "%i:%i:%i" %(24*days+hours,minutes,seconds)
    
    def evaluate_xcode(self):
        lines=''
        command="echo $?"
        self.write_proc("\b"*10)
        log.debug("sending command: '%s' to host" % command)
        self.chan.send(command+'\n')
        while not [True for i in ["=> ","$ ","$ s","# ","# s","ss"] if lines.endswith(i)]:
            if self.chan.recv_ready():
                line=self.chan.recv(9999)
                lines=lines+''.join(line)
        log.debug("Exit Code Line: %s" % lines)
        line_arr=lines.splitlines()
        try:
            self.results.set_command_xcode(int(line_arr[1]))
        except:
            log.exception("Line: %s - does not contain an integer value!!!" % line_arr[1])
        log.debug("Exit Code is: %d" % self.results.get_command_xcode())
    
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
        log.info("closing connection to host %s" % self.results.get_host().getHostName())
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

        def get_host(self):
            return self.host

        def get_command_xcode(self):
            return self.command_xcode

        def get_command(self):
            return self.command

        def get_status(self):
            return self.status

        def get_progress(self):
            return self.progress

        def get_elapsed_time(self):
            return self.elapsed_time

        def get_estimated_time(self):
            return self.estimated_time

        def get_be_alive(self):
            return self.be_alive

        def get_aborted(self):
            return self.aborted

        def get_last_output(self):
            return self.last_output

        def set_host(self, value):
            self.host = value

        def set_command_xcode(self, value):
            self.command_xcode = value

        def set_command(self, value):
            self.command = value

        def set_status(self, value):
            self.status = value

        def set_progress(self, value):
            self.progress = value

        def set_elapsed_time(self, value):
            self.elapsed_time = value

        def set_estimated_time(self, value):
            self.estimated_time = value

        def set_be_alive(self, value):
            self.be_alive = value

        def set_aborted(self, value):
            self.aborted = value

        def set_last_output(self, value):
            self.last_output = value

        def __init__(self):
            self.host = None
            self.command_xcode=0
            self.command = ''
            self.status = ''
            self.progress = 0.0
            self.elapsed_time = ''
            self.estimated_time = ''
            self.be_alive = None
            self.aborted = None
            self.last_output = ''

        
        