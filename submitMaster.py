"""
Joshua Stough
W&L, Image Group
July 2011
This defines the submitMaster thread using the JobDistributor.
This process should be started by the script that generates commands
(like calculateSIFTsDistributively or testSubmitMaster) and that then
sends this thread (Process) one side of the Pipe (a Connection object).
This thread periodically polls the connection to the caller, looking for
a command to execute, then either sends it to the JobDistributor or 
queues it up if the JobDistributor is full. And then it sleeps for a
sec and repeats.

This code could obviously be much more complicated, as the caller may like some
feedback on the processes that have been sent.  I'll deal with that later, this
is just can it work (read: am I smart enough, because it obviously can work).

I guess the caller needs a doneYet option, to know when to join this process and
quit...

I've added processCommandsInParallel to this file.  This function accepts a list
of commands and does all the "start submitMaster, submit jobs, wait til finished"
stuff.  Thus, the orginal caller's code doesn't need Pipes and all, just
"generate commands, processCommandsInParallel(commands)" (as pseudocode).
See testSubmitMaster.py.

 License: This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 3 of the License, or (at your
 option) any later version. This program is distributed in the hope that it
 will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
 of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
 Public License for more details.
"""

import time
from Queue import PriorityQueue, Queue
from threading import Thread
from jobDistributor import JobDistributor
from Config import Config
from Persistence import DB
from Task import Task, Priorities, States

log = Config().getLogger('submitMaster')
config=Config().getConfig()

def singleton(cls):
    instances = {} # Line 2
    def getinstance():
        if cls not in instances:
            instances[cls] = cls() # Line 5
        return instances[cls]
    return getinstance

@singleton
class SubmitMaster(Thread):
    
    def __init__(self):
        Thread.__init__(self)
        self.pq=PriorityQueue(100)
        self.JD = JobDistributor()
        self.__stopProcessing=False
    
    def run(self):
        # Load initial queue from DB on start
        self.__loadQueue()
        while True:
            log.debug("Queue is %s and Status is %s"%(self.pq.empty(), self.__stopProcessing)) 
            if not self.pq.empty() and not self.__stopProcessing:
                task=self.pq.get()
                log.debug("Processing task "+ str(task))
                self.__processTask(task)
            time.sleep(5)
    
    def __loadQueue(self):
        log.debug("Start loading queue")
        db=DB()
        db.connect()
        tasks=db.getAllTasks()
        for task in tasks:
            if task.getStatus()!= States.Completed:
                log.debug("Load task "+str(task))
                self.pq.put(task)
        db.close()
    
    def enqueueTask(self,imei,hash,priority=Priorities.Low):
        db=DB()
        db.connect()
        task=Task(imei, hash, priority)
        db.addTask(task)
        self.pq.put(task)
        db.close()
    
    def stopTaskProcessing(self):
        log.debug("Setting Stop Processing to True")
        self.__stopProcessing=True
        
    def startTaskProcessing(self):
        log.debug("Setting Stop Processing to False")
        self.__stopProcessing=False
        
    def __processTask(self,task):
        db = DB()
        db.connect()
        commands=task.createCommandList()
        jobQueue=Queue(100)
        log.debug("Adding commands to queue...")
        for command in commands:
            jobQueue.put(command)
        task.setStatus(States.Running)
        # loop while there are jobs in the queue and the crack is still not found
        while not jobQueue.empty() and not self.__stopProcessing:
            log.debug("jobQueue empty: %s"% jobQueue.empty())
            if not self.JD.isFull():
                log.debug("Sending command to JobDistributor.")
                self.JD.distribute(jobQueue.get())
            log.debug("Turning errors back to command queue.")
            while self.JD.getErrors() != 0:
                jobQueue.put(self.JD.getErrorJob())
            #update task status
            log.debug("Updating task status in the DB.")
            task.setProgress(self.JD.getProgress())
            db.updateTask(task)
            time.sleep(config["poll_timeout"])
        # Force JD to stop all jobs.
        if self.__stopProcessing:
            self.JD.stopAll()
        # Wait for JD to finish all jobs left.
        while len(self.JD)!=0:
            log.debug("JD info is: "+str(self.JD.info()))
            time.sleep(config["poll_timeout"])
        # if the crack is found get the result
        if self.JD.isDone():
            log.debug("Job Distributor is done.")
            task.setCode(self.JD.getResultCode())
            task.setStatus(States.Completed)
        else:
            log.debug("Task has failed")
            task.setStatus(States.Failed)
        if self.__stopProcessing:
            self.pq.put(task)
        db.updateTask(task)
        db.close()

    def getTasks(self):
        db = DB()
        db.connect()
        response=[]
        tasks=db.getAllTasks()
        for task in tasks:
            response.append({'imei':task.getIMEI(),'hash':task.getHash(),'code':task.getCode(),'status':str(task.getStatus()),'progress':task.getProgress()})
        db.close()
        #Return a tuple of all tasks and their parameters. To be used in a call to the DHServer
        print tuple(response)
        return response

if __name__ == '__main__':
    pass