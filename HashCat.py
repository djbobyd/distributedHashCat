#!/usr/bin/env python

#  Copyright (c) 2005, Corey Goldberg
#
#  HashCat.py is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.

 
"""

@author: Corey Goldberg
@copyright: (C) 2005 Corey Goldberg
@license: GNU General Public License (GPL)
"""


import time
from threading import Thread
from Config import Config


class HashCat(Thread):
        
    """Connect to remote host with SSH and execute and control hashcat.
    
    This is a facade/wrapper that uses paramiko to spawn and control an SSH client. 
    You must have OpenSSH installed. 
        
    @ivar host_name: Host name or IP address
    @ivar user_name: User name 
    @ivar password: Password
    @ivar prompt: Command prompt (or partial string matching the end of the prompt)
    @ivar ssh: Instance of a paramiko.SSHClient object
    """

    config = Config().getConfig()
        
    def __init__(self, hostInfo,command):
        """
        @param host_name: Host name or IP address
        @param user_name: User name 
        @param password: Password
        @param command: The hashcat command that have to be executed
        @param results: A list that will contain the results once this thread is completed.
         
        """
        Thread.__init__(self)
        self.log = Config().getLogger('distributor.'+hostInfo.getHostName(), hostInfo.getHostName())
        self.log.debug("Logging has been configured!!!")
        self.results=results()
        self.results.set_host(hostInfo)
        self.results.set_command(command)
        self.__chan = None
        self.__ssh = None
        self.interval = int(HashCat.config["heartbeat_timeout"])
        self.be_alive = False
        self.aborted = False
        self.__channelLostCount=0

    def get_command_xcode(self):
        return self.results.get_command_xcode()

    
    def __str__(self) :
        #return str(self.__dict__)
        return str({"host_name":self.results.get_host().getHostName(), "user_name":self.results.get_host().getUserName()})

    def __eq__(self, other) : 
        return self.__dict__ == other.__dict__
    
    def abort(self,value):
        self.aborted = value
    def isAborted(self):
        return self.aborted
        
    def set_command(self,value):
        self.results.set_command(value)
    
    def run(self):
        if self.run_command(self.results.get_command()):
            self.ping()
            self.stop_proc()
        self.quit()
        if self.aborted:
            self.results.set_command_xcode(-500)

    
    def run_command(self, command):
        """Run a command on the remote host.
            
        @param command: Unix command
        @return: Command output
        @rtype: String
        """ 
        self.__ssh=self.results.get_host().getChannel()
        if self.__ssh == None:
            return False
        self.__chan=self.__ssh.invoke_shell()
        self.log.debug("sending command: '%s' to host" % command.getCommand())
        self.__chan.send(command.getCommand()+'\n')
        time.sleep(int(HashCat.config["init_timeout"]))
        self.be_alive = True
        self.read_proc()
        return self.__chan.send_ready()
    
    
    def ping(self):
        self.log.debug("Heartbeat is: %s and override is: %s" % (self.be_alive, self.aborted))
        while self.be_alive and not self.aborted:
            self.write_proc("s")
            self.read_proc()
            self.log.debug("Sleeping for %d seconds" % self.interval)
            time.sleep(self.interval)
        
    def parse(self, lines):
        line_arr=lines.splitlines()
        self.log.debug("Lines array: %s" % line_arr)
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
                        self.getCrackCode()
                        self.be_alive=False
                        break
                    if case('Aborted'):
                        self.be_alive=False
                        break
                    if case('Initializing'):
                        self.be_alive=True
                        break
                    if case():
                        self.log.warning("Unexpected value: %s" % self.results.get_status())
                continue 
            if line.startswith("Progress."):
                try:
                    prg=float(line[line.find("(")+1:line.find(")")-1])
                    if prg==float(self.results.get_command().getID())+1.0:
                        prg=0.99
                    self.results.set_progress(prg)
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
                if not self.results.get_command_xcode() in [0,1]:
                    self.results.set_status("Error")
                continue
            #self.log.debug("Line cannot be recognized: %s" % line)
                
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
        self.log.debug("sending command: '%s' to host" % command)
        self.__chan.send(command+'\n')
        while not [True for i in ["=> ","$ ","$ s","# ","# s","ss"] if lines.endswith(i)]:
            if self.__chan.recv_ready():
                line=self.__chan.recv(9999)
                lines=lines+''.join(line)
        self.log.debug("Exit Code Line: %s" % lines)
        line_arr=lines.splitlines()
        try:
            self.results.set_command_xcode(int(line_arr[1]))
        except:
            self.log.exception("Line: %s - does not contain an integer value!!!" % line_arr[1])
        self.log.debug("Exit Code is: %d" % self.results.get_command_xcode())
    
    def stop_proc(self):
        self.log.info("Sending stop command to process...")
        self.be_alive = False
        self.write_proc("q")
        self.read_proc()
    
    def read_proc(self):
        lines=''
        count=0
        while not [True for i in ["=> ","$ ","$ s","# ","# s","ss"] if lines.endswith(i)]:
            try:
                self.log.debug("Channel receive status: %s" % self.__chan.recv_ready())
                while not self.__chan.recv_ready() and not count >=10:
                    time.sleep(1)
                    count+=1 
                if self.__chan.recv_ready():
                    line=self.__chan.recv(9999)
                    lines=lines+''.join(line)
                else:
                    self.__channelLostCount+=1
                    break
            except (RuntimeError, IOError):
                print "Stream not ready!!!"
        if self.__channelLostCount>=10:
            self.be_alive=False
            self.results.set_command_xcode(-100)
            self.results.set_status('Aborted')
            return
        self.parse(lines)
        
    def write_proc(self, message):
        if self.__chan.send_ready():
            self.log.debug("Sending message: %s through the channel..." % message)
            self.__chan.send(message)
            return True
        else:
            return False
    
    def quit(self):
        self.log.debug("Quitting thread on host %s ..."% self.results.get_host().getHostName())
        if self.__ssh!= None:
            self.results.get_host().closeChannel(self.__ssh)
    
    def getCrackCode(self):
        #read code from file
        cmdline=self.results.get_command().getCommand().split(" ")
        for cmd in cmdline:
            if cmd.startswith('--outfile'):
                filename=cmd.split("=")[1]
        if filename != None:
            tmp=self.results.get_host().getFile(filename)
            crackCode=tmp[0][:-1].split(':')[2]
        if crackCode != None:
            self.results.set_crackCode(crackCode)
    
    def get_result(self):
        return self.results
    
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
      
class results(object):

        def get_host(self):
            return self.host

        def get_command_xcode(self):
            return self.command_xcode

        def get_command(self):
            return self.command

        def get_status(self):
            return self.__status

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
            self.__status = value

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
            
        def get_crackCode(self):
            return self.crackCode
        
        def set_crackCode(self,value):
            self.crackCode = value

        def __init__(self):
            self.host = None
            self.command_xcode=0
            self.command = ''
            self.__status = ''
            self.progress = 0.0
            self.elapsed_time = ''
            self.estimated_time = ''
            self.be_alive = None
            self.aborted = None
            self.last_output = ''
            self.crackCode=None

if __name__ == '__main__':
    pass    
        