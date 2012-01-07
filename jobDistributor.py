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
from HashCat import HashCat
from Host import Host
from Config import Config
from Encryption import Encryption
from Task import States
from threading import Thread


log = Config().getLogger('distributor')
config = Config().getConfig()
crypto = Encryption()

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
            self.HC.join(300.0)
            self.endTime=time.ctime()
            self.__host.delProcess()
            if self.__status.get_command_xcode()!=0:
                if self.__status.get_command_xcode()!=-500:
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


class JobDistributor(Thread):
    
    def __init__(self,task):
        Thread.__init__(self)
        self.__maxJobs = config["hostJobs"]
        self.__maxErrors = config["hostErrors"]
        self.totalJobs = 0
        self.instances = 0
        self.__task=task
        self.__status = States.Pending
        self.computer_list = self.__getHostfromConfig(self.__maxJobs, self.__maxErrors)
        self.__processes = {}
        self.__jobQueue = Queue(100)
    
    def getTask(self):
        return self.__task
    
    def terminate(self):
        self.__status=States.Aborted
        self.__task.setStatus(States.Aborted)
        self.__stopAll()
    def __stopAll(self):
        log.debug("Terminating all jobs, please standby ...")
        for host in self.__processes:
                for job in self.__processes[host]:
                    job.terminate()

    def run(self):
        commands=self.__task.createCommandList()
        log.debug("Adding commands to queue...")
        for command in commands:
            self.__jobQueue.put(command, block=False)
        self.__task.setStatus(States.Running)
        while not self.__jobQueue.empty() and self.__status not in [States.Completed, States.Aborted]:
            log.debug("JD.run - jobQ %s and status %s"%(self.__jobQueue.qsize(),self.__status))
            self.distribute(self.__jobQueue.get(block=False))
        while len(self)!=0:
            log.debug("JD.run end - len is %s"%len(self))
            self.__cleanup()
            time.sleep(config["poll_timeout"])
        if not self.__task.getStatus() in [States.Completed,States.Aborted]:
            self.__task.setStatus(States.Failed)

    def distribute(self, command):
        if self.__status==States.Pending:
            self.__status=States.Running
        procNum = command.getID()
        host=None
        sleepTime=0
        maxSleepTime=config["maxHostWait"]
        log.info('Searching for host for process %i...' % (procNum))
        while host==None and self.__status not in [States.Completed, States.Aborted]:
            log.debug("Waiting %i seconds for available host!"%sleepTime)
            time.sleep(sleepTime)
            if sleepTime<maxSleepTime:
                sleepTime+=10
            host = self.__getHost()   
        if self.__status not in [States.Completed, States.Aborted]:
            log.info('Host %s chosen for proc %i.' % (host.getHostName(), procNum))
            self.__processes[host.getHostName()].append(Job(host,command))
            log.info('Submited to ' + host.getHostName() + ': ' + command.getCommand())
            self.totalJobs += 1
            return True
        return False

    def __getHost(self):
        """Find a host among the computer_list whose load is less than maxJobs."""
        log.info("Finding available host...")
        self.__cleanup()
        for host in self.__processes:
            hostInfo=self.__getHostfromList(host)
            log.debug("Checking host %s" % hostInfo.getHostName())
            if hostInfo.getStatus() in [Host.States.Available, Host.States.Running]:
                return hostInfo
        return None     


    def __getHostfromConfig(self,maxProcess, maxError):
        lst = config["hosts"]
        pcList=[]
        for host in lst:
            h = Host(host["name"], host["user"], crypto.decrypt(host["pass"]))
            h.setMaxProcess(maxProcess)
            h.setMaxErrors(maxError)
            log.debug("Host %s extracted from config file." % h.getHostName())
            pcList.append(h)
        log.debug("Total number of hosts is: %i" % len(pcList))
        return pcList

    def __cleanup(self):
        processes={}
        for host in self.computer_list:
            if host.checkHost() and host.getStatus() != Host.States.Error: #host is alive
                if host.getStatus() in (Host.States.Running, Host.States.Full): # host is working
                        if self.__processes.has_key(host.getHostName()): #current process list contains this host
                            jobs=[]
                            for job in self.__processes[host.getHostName()]:
                                if job.poll(): # process is still working
                                    jobs.append(job) 
                                else: #process is done
                                    if job.getStatus().get_status() == "Cracked": # check for crack code
                                        self.__status = States.Completed
                                        self.__task.setStatus(States.Completed)
                                        self.__task.setCode(job.getStatus().get_crackCode())
                                        self.__stopAll()
                                        break
                                    if job.getStatus().get_command_xcode()!=0:  # check for errors
                                        self.__jobQueue.put(job.getStatus().get_command(),block=False)
                                        continue
                                    if not self.__status==States.Aborted: # remove completed from task
                                        self.__task.delJobID(job.getStatus().get_command().getID())
                            processes[host.getHostName()]=jobs
                        else:
                            log.error("Something is very wrong!!! There are hosts with assigned tasks that are not in the current jobs list.")
                else: # host is idle, add empty proc list
                    processes[host.getHostName()]=[]
            else:  # host is error, or dead
                if self.__processes.has_key(host.getHostName()):
                    for job in self.__processes[host.getHostName()]:
                        #add to error queue
                        job.terminate()
                        log.debug("Host %s is dead returning job %s in the queue!"%(host.getHostName(),job.getStatus().get_command()))
                        self.__jobQueue.put(job.getStatus().get_command(),block=False)
        self.__processes=processes
        self.__task.setProgress(self.__calcTaskProgress(self.__task.getJobCount(),self.__calculateProgress()))
    
    def __len__(self):
        return sum([len(plist) for plist in self.__processes.values()])
    
    def __repr__(self):
        errors=0
        for host in self.computer_list:
            if host.getStatus()==Host.States.Error:
                errors+=1
        return (errors,self.__status)
    
    def __calcTaskProgress(self,jCount,fraction):
        answer=100 - jCount + fraction 
        log.debug("progress part is: %f"%answer)
        return answer
    
    def __calculateProgress(self):
        allProgress=[]
        for host in self.__processes:
            for job in self.__processes[host]:
                allProgress.append(job.getStatus().get_progress())    
        fraction=0.00
        for i in allProgress:
            fraction=fraction+math.modf(i)[0]
        return fraction
    
    def resetErrorHost(self):
        for host in self.computer_list:
            if host.getStatus()==Host.States.Error:
                host.resetErrors()
            
    def __getHostfromList(self,host):
        for hostInfo in self.computer_list:
            if hostInfo.getHostName() == host:
                return hostInfo
            
if __name__ == '__main__':
    pass