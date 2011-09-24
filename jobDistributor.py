"""
 License: This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 3 of the License, or (at your
 option) any later version. This program is distributed in the hope that it
 will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
 of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
 Public License for more details.
"""

import time, math
from Queue import Queue
from HashCat import HashCat, results
from Host import Host
from Config import Config
from Encryption import Encryption


log = Config().getLogger('distributor')
config = Config().getConfig()
crypto = Encryption()

def singleton(cls):
    instances = {} # Line 2
    def getinstance():
        if cls not in instances:
            instances[cls] = cls() # Line 5
        return instances[cls]
    return getinstance

#My computer list, should be able to ssh to without a password.

class Job(object):
    def __init__(self, host,command):
        self.startTime = time.ctime()
        self.endTime = None
        self.__status=None
        self.__command=command
        self.__host=host
        self.HC = HashCat(self.__host, self.__command)
        self.__status=self.HC.get_result()
        if self.__host.addProcess():
            self.HC.start()
        else:
            self.__status.set_command_xcode(-1000)

    def __str__(self):
        ret = '[Job on host %s: %-15s started %s]' % \
              (self.__host.getHostName(),self.__command.getCommand()[:15], self.startTime)
        return ret
    def terminate(self):
        self.HC.abort(True)
        self.poll()

    def poll(self):
        if not self.HC.isAlive() or self.HC.isAborted():
            log.debug("Waiting for thread to finish...")
            self.HC.join()
            self.endTime=time.ctime()
            self.__host.delProcess()
            if self.__status.get_command_xcode()!=0:
                self.__host.addError()
            else:
                self.__host.resetErrors()
            return False
        elif self.__status.get_command_xcode()==-1000:
            self.__host.addError()
            return False
        else:
            return True
    
    def getStatus(self):
        return self.__status

@singleton
class JobDistributor(object):
    
    def __init__(self):
        self.__maxJobs = config["hostJobs"]
        self.__maxErrors = config["hostErrors"]
        self.errorQueue = Queue(100)  
        self.totalJobs = 0
        self.instances = 0
        self.__status = {"cracked":False,"result":results()}
        self.__totalProgress=0.0
        self.computer_list = self.__getHostfromConfig(self.__maxJobs, self.__maxErrors)
        self.__processes = {}
    
    def getErrors(self):
        return self.errorQueue.qsize()
    
    def getErrorJob(self):
        return self.errorQueue.get()
    
    def getResultCode(self):
        return self._status['result'].get_crackCode()
    
    def getProgress(self):
        return self.__totalProgress

    def isFull(self):
        log.debug("Length is: %i  Processes: %i"%(len(self), len(self.__processes)*self.__maxJobs))
        return len(self) == len(self.__processes)*self.__maxJobs
    
    def isDone(self):
        return self.__status['cracked']
    
    def stopAll(self):
        log.debug("Terminating all jobs, please standby ...")
        for host in self.__processes:
                for job in self.__processes[host]:
                    job.terminate()

    def info(self):
        return (len(self.__processes), self.__maxJobs*len(self.__processes))

    def distribute(self, command):
        procNum = self.totalJobs
        #Simplified for now.  Just to see if the data all works.
        log.info('Searching for host for process %i...' % (procNum))
        hostFound = False
        waitCycles = 0
        while not hostFound:
            try:
                host = self.__getHost()
                log.info('Host %s chosen for proc %i.' % (host.getHostName(), procNum))
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

        log.info('Submited to ' + host.getHostName() + ': ' + command.getCommand())
        self.__processes[host.getHostName()].append(Job(host,command))
        self.totalJobs += 1

    def __getHost(self):
        """Find a host among the computer_list whose load is less than maxJobs."""
        #Could loop through computer_list here, but computer_list still lists the
        #unavailable ones.  
        log.info("Finding available host...")
        self.__cleanup()
        for host in self.__processes:
            hostInfo=self.__getHostfromList(host)
            log.debug("Checking host %s" % hostInfo.getHostName())
            if hostInfo.getStatus() in [Host.States.Available, Host.States.Running]:
                return hostInfo
            else:
                log.error('__getHost() error: host %s not available.' % (host))
                    
        raise ValueError('__getHost() failed: could not find host.')

    def __getHostfromConfig(self,maxProcess, maxError):
        list = config["hosts"]
        pcList=[]
        for host in list:
            h = Host(host["name"], host["user"], crypto.decrypt(host["pass"]))
            h.setMaxProcess(maxProcess)
            h.setMaxErrors(maxError)
            log.debug("Host %s extracted from config file." % h.getHostName())
            pcList.append(h)
        log.debug("Total number of hosts is: %i" % len(pcList))
        return pcList

    def __str__(self):
        if self.__cleanup()==0:
            if self.__status["cracked"]:
                return 'JobDistributor: !!! hash cracked !!! result available on host: '+self.__status["result"].get_host().getHostName()
            else:
                return 'JobDistributor: cracking failed!!!'
        else:
            return '[JobDistributor: %i jobs on %i hosts]' % (len(self), len(self.__processes))
    
    def __len__(self):
        #Return number of jobs running
        return self.__cleanup()

    def __cleanup(self):
        log.debug("Cleaning dead hosts...")
        self.__cleanDeadHosts()
        log.debug("cleaning finished jobs...")
        for host in self.__processes:
            for job in self.__processes[host]:
                # check for errors
                if job.getStatus().get_command_xcode()!=0:
                    self.errorQueue.put(job.getStatus().get_command())
                # check for crack code
                if job.getStatus().get_status() == "Cracked":
                    self.__status['cracked']=True
                    self.__status['result']=job.getStatus()
            #clean up finished processes.
            self.__processes[host] = [job for job in self.__processes[host] if job.poll()]
        self.__calculateProgress()
        # stop all running jobs in case crack is found
        if self.__status['cracked']:
            self.stopAll()
        return sum([len(plist) for plist in self.__processes.values()])
    
    def __cleanDeadHosts(self):
        for host in self.computer_list:
            log.debug("checking host %s"%host.getHostName())
            if host.checkHost():
                log.debug("Host is alive")
                if host.getStatus() in (Host.States.Running, Host.States.Full):
                    log.debug("Host has some jobs running on.")
                    self.__processes[host.getHostName()]=self.__processes[host.getHostName()]
                    continue
                if host.getStatus() == Host.States.Error:
                    log.debug("Host has too many errors, skipping...")
                    continue
                self.__processes[host.getHostName()] = []
    
    def __calculateProgress(self):
        allProgress=[]
        for host in self.__processes:
            for job in self.__processes[host]:
                allProgress.append(job.getStatus().get_progress())    
        maxNumber=0.00
        fraction=0.00
        for i in allProgress:
            if i>maxNumber:
                maxNumber=math.modf(i)[1]
            fraction=fraction+math.modf(i)[0]
        self.__totalProgress = maxNumber + fraction
    
    def __getHostfromList(self,host):
        for hostInfo in self.computer_list:
            if hostInfo.getHostName() == host:
                return hostInfo
            
if __name__ == '__main__':
    pass