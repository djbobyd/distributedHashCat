"""
Joshua Stough
W&L, Image Group
July 2011
A job distributor class, that maintains a list of available machines,
and distributes jobs to them. My idea is that someone uses this by
generating their own command lines, like 'echo hello; cd ~/teaching; ls'
and this class basically makes the system call
'ssh host command'.  It's the caller's responsibility to generate
appropriate command lines, redirecting output as they see fit.

uses subprocess to do this, instantiating a process to execute the
ssh command.  Process information is then stored in a Job object,
which can in turn be queried.

This class should be instantiated by an independent thread, which
periodically checks for the completion of jobs and maintains a job
queue.  See submitMaster and testSubmitMaster for guidance. When
presented with a job to distribute when all hosts are busy to their
capacity, this code will hang, waiting for a spot to open up.  It's
someone else's responsibility to keep the original caller informed
about the submissions made--again, see submitMaster.

 License: This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 3 of the License, or (at your
 option) any later version. This program is distributed in the hope that it
 will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
 of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
 Public License for more details.
"""

import os, sys, time, yaml,logging.config
from listQueue import listQueue
from HashCat import SSHController, results
from multiprocessing import Process, Pipe, Queue

config = yaml.load(open(os.path.join(os.path.dirname(__file__),'log.yml'), 'r'))
logging.config.dictConfig(config)
log = logging.getLogger('distributor')

stream = file(os.path.join(os.path.dirname(__file__),'config.yml'), 'r')
config = yaml.load(stream)

#My computer list, should be able to ssh to without a password.

class Job(object):
    def __init__(self, sshController, q, status):
        self.queue = q
        self.sshController = sshController
        self.startTime = time.ctime()
        self.status=status

    def __str__(self):
        ret = '[Job on host %s: %-15s started %s]' % \
              (self.sshController.host_name, self.sshController.command[:15], self.startTime)
        return ret

    def checkStatus(self):
        res=self.queue.get()
        if res.get_status() == "Cracked":
            self.status['cracked']=True
            self.status['result']=res

    def poll(self):
        #return None for testing
        if not self.sshController.is_alive():
            self.checkStatus()
            self.sshController.join
            return False
        else:
            return True

class JobDistributor(object):
    #Some static members.  Replace the elements of 
    #computer_list with hostnames you have ssh access to
    #without a password (see ssh-keygen)
    #reading config file
    
    
    computer_list = config["hosts"]

    maxJobs = 1
    processes = {}  
    #dictionary associating hostname to a list of Job objects.
    totalJobs = 0
    instances = 0
    status = {"cracked":False,"result":results()}
    
    def __init__(self):
        if self.instances == 1:
            raise AssertionError('JobDistributor init ERROR: ' + \
                                 'Only one JD object allowed')
        self.instances = 1
        for host in self.computer_list:
            self.processes[host["name"]] = []
        self.cleanComputerList()
              

    def setMaxJobs(self, num):
        self.maxJobs = num

    def isFull(self):
        return len(self) == len(self.processes)*self.maxJobs

    def info(self):
        return (len(self.processes), self.maxJobs*len(self.processes))

    def distribute(self, command):
        procNum = self.totalJobs
        #Simplified for now.  Just to see if the data all works.
        log.info('\nSearching for host for process %i...' % (procNum))
        hostFound = False
        waitCycles = 0
        while not hostFound:
            try:
                host = self.getHost()
                log.info('Host %s chosen for proc %i.' % (host, procNum))
                hostFound = True
                break
            except ValueError:
                log.exception('%sWaiting to find host for proc %i.' % \
                      ('.'*waitCycles, procNum))
                waitCycles += 1
                time.sleep(waitCycles)
                #The exception here should not happen, because the
                #submitMaster that calls this ensures there is
                #availability.  This will hang if it was mistaken.
        #print('Starting command.')
#       command_line = 'ssh ' + host + ' ' + command

        hostInfo = self.getHostfromList(host)
        res = results()
        q = Queue()
        HC = SSHController(hostInfo["name"],hostInfo["user"],hostInfo["pass"], command, q)
        p = Process(target=HC,args=())
        p.start()
        log.info('Submited to ' + host + ': ' + command)
        self.processes[host].append(Job(p,q,self.status))
        self.totalJobs += 1

    def getHost(self):
        """Find a host among the computer_list whose load is less than maxJobs."""
        #Could loop through computer_list here, but computer_list still lists the
        #unavailable ones.  
        log.debug("Finding available host...")
        for host in self.processes:
            #clean out finished jobs. Keep only those which haven't terminated.
            self.processes[host] = [HC for HC in self.processes[host] if HC.poll()]

            if len(self.processes[host]) < self.maxJobs:
                hostInfo=self.getHostfromList(host)
                log.debug("Checking host %s" % hostInfo["name"])
                if SSHController(hostInfo["name"],hostInfo["user"],hostInfo["pass"]).check_host():
                    return host
                else:
                    log.error('getHost() error: host %s not available.' % (host))
                    
        #print('getHost(): could not find host.\n')
        raise ValueError('getHost() failed: could not find host.')

    def __str__(self):
        if self.cleanup()==0:
            if self.status["cracked"]:
                return 'JobDistributor: !!! hash cracked !!! result available on host: '+self.status["result"].get_host_name()
            else:
                return 'JobDistributor: cracking failed!!!'
        else:
            return '[JobDistributor: %i jobs on %i hosts]' % (len(self), len(self.processes))
    
    def __len__(self):
        #Return number of jobs running
        return self.cleanup()

    def cleanup(self):
        for host in self.processes:
            #clean up finished processes.
            self.processes[host] = [HC for HC in self.processes[host] if HC.poll()]
        if self.status['cracked']:
            for host in self.processes:
                for job in self.processes[host]:
                    job.sshController.set_aborted=True    
        return sum([len(plist) for plist in self.processes.values()])

    def cleanComputerList(self):
        log.debug("Cleaning computer list ...")
        processes={}
        for host in self.processes:
            hostInfo=self.getHostfromList(host)
            HC=SSHController(hostInfo["name"],hostInfo["user"],hostInfo["pass"])
            if not HC.check_host():
                log.warning(str(HC)+" is not available!!! Removing from list...")
                continue
            processes[host]=self.processes[host]
        self.processes=processes
    
    def getHostfromList(self,host):
        for hostInfo in self.computer_list:
            if hostInfo["name"] == host:
                return hostInfo
   

