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

import os, sys, time, yaml,logging.config, math, datetime
from listQueue import listQueue
from HashCat import SSHController, results

config = yaml.load(open(os.path.join(os.path.dirname(__file__),'log.yml'), 'r'))
logging.config.dictConfig(config)
log = logging.getLogger('distributor')

stream = file(os.path.join(os.path.dirname(__file__),'config.yml'), 'r')
config = yaml.load(stream)

#My computer list, should be able to ssh to without a password.

class Enum(set):
    def __getattr__(self, name):
        if name in self:
            return name
        raise AttributeError

class Job(object):
    def __init__(self, hostInfo,command, status):
        self.result = results()
        self.startTime = time.ctime()
        self.status=status
        self.command=command
        self.host=hostInfo
        self.HC = SSHController(self.host, self.command, self.result)
        self.host.setStatus=Host.States.Running
        self.HC.start()

    def __str__(self):
        ret = '[Job on host %s: %-15s started %s]' % \
              (self.host.getHostName, self.HC.command[:15], self.startTime)
        return ret
    def terminate(self):
        self.HC.set_aborted(True)
    
    def checkStatus(self):
        if self.result.get_status() == "Cracked":
            self.status['cracked']=True
            self.status['result']=self.result

    def poll(self):
        #return None for testing
        if not self.HC.isAlive():
            self.checkStatus()
            return False
        else:
            return True
    
    def getCurrent(self):
        return self.result
    
    def getHost(self):
        return self.host

class Host(object):
    States = Enum(["NotAvailable","Running","Available","Down","Error"])
    status = States.NotAvailable
    errors = 0
    def __init__(self, host, user, password, port = 22):
        self.hostName = host
        self.userName = user
        self.password = password
        self.port = port
    def getHostName(self):
        return self.hostName
    def getUserName(self):
        return self.userName
    def getPassword(self):
        return self.password
    def getPort(self):
        return self.port
    def setStatus(self,state):
        self.status = state
    def getStatus(self):
        return self.status
    def getErrors(self):
        return self.errors
    def addError(self):
        self.errors+=1
    def resetErrors(self):
        self.errors=0

class JobDistributor(object):
    _instance = None
    #reading config file
    computer_list = []
    maxJobs = 1
    errorQueue = listQueue(10)
    processes = {}  
    #dictionary associating hostname to a list of Job objects.
    totalJobs = 0
    instances = 0
    status = {"cracked":False,"result":results()}
    totalProgress=0.0
    
    def __init__(self):
        if self.instances == 1:
            raise AssertionError('JobDistributor init ERROR: ' + \
                                 'Only one JD object allowed')
        self.instances = 1
        self.computer_list = self.getHostfromConfig()
        for host in self.computer_list:
            if SSHController(host).check_host():
                host.setStatus=Host.States.Available
                self.processes[host.getHostName()] = []
            else:
                host.setStatus=Host.States.Down
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(JobDistributor, cls).__new__(
                                cls, *args, **kwargs)
        return cls._instance
    
    def getErrors(self):
        return len(self.errorQueue)
    
    def getHostfromConfig(self):
        list = config["hosts"]
        pcList=[]
        for host in list:
            h = Host(host["name"], host["user"], host["pass"])
            log.debug("Host %s extracted form config file." % h.getHostName())
            pcList.append(h)
        log.debug("Total number of hosts is: %i" % len(pcList))
        return pcList
    
    def setMaxJobs(self, num):
        self.maxJobs = num

    def isFull(self):
        return len(self) == len(self.processes)*self.maxJobs

    def info(self):
        return (len(self.processes), self.maxJobs*len(self.processes))

    def distribute(self, command):
        procNum = self.totalJobs
        #Simplified for now.  Just to see if the data all works.
        log.info('Searching for host for process %i...' % (procNum))
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

        hostInfo = self.getHostfromList(host)
        log.info('Submited to ' + host + ': ' + command)
        self.processes[host].append(Job(hostInfo,command,self.status))
        self.totalJobs += 1

    def getHost(self):
        """Find a host among the computer_list whose load is less than maxJobs."""
        #Could loop through computer_list here, but computer_list still lists the
        #unavailable ones.  
        log.debug("Finding available host...")
        self.cleanup()
        for host in self.processes:
           
            if len(self.processes[host]) < self.maxJobs:
                hostInfo=self.getHostfromList(host)
                log.debug("Checking host %s" % hostInfo.getHostName())
                if SSHController(hostInfo).check_host() and hostInfo.getErrors()<config['hostErrors']:
                    return host
                else:
                    log.error('getHost() error: host %s not available.' % (host))
                    
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
            for job in self.processes[host]:
                if job.getCurrent().get_command_xcode()!=0:
                    self.errorQueue.enqueue(job.getCurrent().get_command())
                    job.getHost().addError()
                    job.geHost().setStatus=Host.States.Error
                    self.errors=self.errors+1
            self.processes[host] = [job for job in self.processes[host] if job.getCurrent().get_command_xcode()==0]
            self.processes[host] = [job for job in self.processes[host] if job.poll()]
            self.calculateProgress()
        if self.status['cracked']:
            for host in self.processes:
                for job in self.processes[host]:
                    job.terminate() 
        return sum([len(plist) for plist in self.processes.values()])
    
    def getErrorJob(self):
        return self.errorQueue.dequeue()
    
    def calculateProgress(self):
        allProgress=[]
        for host in self.processes:
            for job in self.processes[host]:
                allProgress.append(job.getCurrent().get_progress())    
        maxNumber=0.0
        fraction=0.0
        lenght=sum([len(plist) for plist in self.processes.values()])
        for i in allProgress:
            if i>maxNumber:
                maxNumber=math.modf(i)[1]
            fraction=fraction+math.modf(i)[0]
        maxNumber=maxNumber + 1 - lenght
        if lenght==0:
            self.totalProgress=0
        else:
            self.totalProgress = maxNumber + fraction
    
    def getHostfromList(self,host):
        for hostInfo in self.computer_list:
            if hostInfo.getHostName() == host:
                return hostInfo
   
    #TODO remove the submitMaster file and move the logic here.
    def submitMaster(self):
        log.info("submit Master started...")
        jobQueue = listQueue(100)
    
        log.info("Job Distributor started, with %i nodes, %i jobs possible" % \
              self.info())
    
        while not (len(self) == 0 and jobQueue.isEmpty()):
            jobQueue.enqueue("command")
    
            #Distribute as many jobs as possible.
            while not jobQueue.isEmpty() and not self.isFull():
                self.distribute(jobQueue.dequeue())
            while self.getErrors() != 0:
                jobQueue.enqueue(self.getErrorJob())   

            log.debug("poll_timeout: %d"% int(config["poll_timeout"]))
            time.sleep(int(config["poll_timeout"]))