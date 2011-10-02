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
from Task import States


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
        log.debug("Job status is: %s"%self.HC.isAlive())
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
        self.doneQueue = Queue(100)  
        self.totalJobs = 0
        self.instances = 0
        self.__status = {"status":States.Pending,"result":results()}
        self.__totalProgress=0.0
        self.computer_list = self.__getHostfromConfig(self.__maxJobs, self.__maxErrors)
        self.__processes = {}
    
    def getErrors(self):
        return self.errorQueue.qsize()
    def getDoneNumber(self):
        return self.doneQueue.qsize()
    
    def getErrorJob(self):
        return self.errorQueue.get(block=False)
    def getCompletedJob(self):
        return self.doneQueue.get(block=False)
    
    def getResultCode(self):
        return self._status['result'].get_crackCode()
    
    def getProgress(self):
        return self.__totalProgress

    def isFull(self):
        processes=len(self)
        maxProcess=len(self.__processes)*self.__maxJobs
        log.debug("Length is: %i  Processes: %i"%(processes, maxProcess))
        return processes == maxProcess
    
    def isDone(self):
        return self.__status['status'] == States.Completed
    
    def stopAll(self):
        log.debug("Terminating all jobs, please standby ...")
        self.__status['status']=States.Aborted
        for host in self.__processes:
                for job in self.__processes[host]:
                    job.terminate()

    def info(self):
        return (len(self.__processes), self.__maxJobs*len(self.__processes))

    def distribute(self, command):
        if self.__status['status']==States.Pending:
            self.__status['status']=States.Running
        procNum = self.totalJobs
        host=None
        sleepTime=0
        maxSleepTime=config["maxHostWait"]
        #Simplified for now.  Just to see if the data all works.
        log.info('Searching for host for process %i...' % (procNum))
        while host==None:
            log.debug("Waiting %i seconds for available host!"%sleepTime)
            time.sleep(sleepTime)
            if sleepTime<maxSleepTime:
                sleepTime+=10
            host = self.__getHost()   
        log.info('Host %s chosen for proc %i.' % (host.getHostName(), procNum))
        self.__processes[host.getHostName()].append(Job(host,command))
        log.info('Submited to ' + host.getHostName() + ': ' + command.getCommand())
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
        return None     


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
            if self.__status["status"]==States.Completed:
                return 'JobDistributor: !!! hash cracked !!! result available on host: '+self.__status["result"].get_host().getHostName()
            else:
                return 'JobDistributor: cracking failed!!!'
        else:
            return '[JobDistributor: %i jobs on %i hosts]' % (len(self), len(self.__processes))
    
    def __len__(self):
        #Return number of jobs running
        return self.__cleanup()

    def __cleanup(self):
        processes={}
        for host in self.computer_list:
            if host.checkHost() and host.getStatus() != Host.States.Error:
                if host.getStatus() in (Host.States.Running, Host.States.Full):
                        if self.__processes.has_key(host.getHostName()):
                            jobs=[]
                            for job in self.__processes[host.getHostName()]:
                                if job.poll():
                                    jobs.append(job) 
                                else:
                                    if job.getStatus().get_command_xcode()!=0:  # check for errors
                                        self.errorQueue.put(job.getStatus().get_command())
                                    # check for crack code
                                    if job.getStatus().get_status() == "Cracked":
                                        self.__status['status']=States.Completed
                                        self.__status['result']=job.getStatus()
                                    if not self.__status['status']==States.Aborted:
                                        self.doneQueue.put(job.getStatus().get_command())
                            processes[host.getHostName()]=jobs
                else:
                    #add empty proc list
                    processes[host.getHostName()]=[]
            else:
                if self.__processes.has_key(host.getHostName()):
                    for job in self.__processes[host.getHostName()]:
                        #add to error queue
                        job.terminate()
                        self.errorQueue.put(job.getStatus().get_command())
        self.__processes=processes
        self.__calculateProgress()
        # stop all running jobs in case crack is found
        if self.__status['status'] == States.Completed:
            self.stopAll()
        tmp=sum([len(plist) for plist in self.__processes.values()])
        return tmp
    
    
    def __calculateProgress(self):
        allProgress=[]
        for host in self.__processes:
            for job in self.__processes[host]:
                allProgress.append(job.getStatus().get_progress())    
        fraction=0.00
        for i in allProgress:
            fraction=fraction+math.modf(i)[0]
        self.__totalProgress = fraction
            
    def __getHostfromList(self,host):
        for hostInfo in self.computer_list:
            if hostInfo.getHostName() == host:
                return hostInfo
            
if __name__ == '__main__':
    pass