"""
Joshua Stough
W&L, Image Group
July 2011

 License: This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 3 of the License, or (at your
 option) any later version. This program is distributed in the hope that it
 will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
 of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
 Public License for more details.
"""

import time, thread
from Queue import PriorityQueue, Queue
from threading import Thread, Semaphore
from jobDistributor import JobDistributor
from Config import Config
from Persistence import DB
from Task import Task, Priorities, States
from bitcoinControl import execute

log = Config().getLogger('submitMaster')
config=Config().getConfig()


class SubmitMaster(Thread):
    
    def __init__(self):
        Thread.__init__(self)
        self.pq=PriorityQueue(100)
        self.__stopProcessing=False
        self.__quit=False
        self.__JD=None
    
    def run(self):
        # Load initial queue from DB on start
        self._loadQueue()
        while not self.__quit:
            log.debug("Queue is %s and Status is %s"%(self.pq.empty(), self.__stopProcessing)) 
            if not self.pq.empty() and not self.__stopProcessing:
                task=self.pq.get()
                log.debug("Queue size is: %s"%self.pq.qsize())
                log.debug("Processing task "+ str(task))
                self._processTask(task)
            else:
                if config["executeBitCoin"]:
                    execute("start")                # Start bitcoins if there is no hash to brake
                while (self.__stopProcessing or self.pq.empty()) and  not self.__quit:
                    log.debug("Waiting for a task, or start of the execution...")
                    time.sleep(5)               # Sleep untill 
                if config["executeBitCoin"]:
                    execute("stop")                 # Stop bitcoins and continue with hash tasks
            time.sleep(5)
    
    def _loadQueue(self):
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
        status=db.addTask(task)
        if status: self.pq.put(task)
        db.close()
        isChanged=False
        if priority == Priorities.Critical:
            thread.start_new_thread(self.__realTimeJob,())
        return status
    
    def __realTimeJob(self):
        if not self.__stopProcessing:
            self.__stopProcessing = True
            isChanged=True
        while self.__JD != None:
            time.sleep(10)
        if isChanged:
            self.__stopProcessing = False
    
    def stopTaskProcessing(self):
        log.debug("Setting Stop Processing to True")
        self.__stopProcessing=True
        
    def startTaskProcessing(self):
        log.debug("Setting Stop Processing to False")
        self.__stopProcessing=False
        
    def _processTask(self,task):
        self.__JD = JobDistributor(task)
        self.__JD.start()
        while self.__JD.isAlive():
            time.sleep(config["poll_timeout"])
            self.__dbUpdate(self.__JD.getTask())
            if self.__stopProcessing:
                self.__JD.terminate()
                self.pq.put(task, block=False)
        self.__dbUpdate(self.__JD.getTask())
        self.__JD.join()
        self.__JD=None
    
    def __dbUpdate(self,task):
        db = DB()
        db.connect()
        db.updateTask(task)
        db.close()
    
    def __calcTaskProgress(self,jCount,fraction):
        return 100 - jCount + fraction

    def getTasks(self,tskList=None):
        db = DB()
        db.connect()
        response=[]
        tasks=db.getTasksWithID(tskList)
        for task in tasks:
            response.append({'imei':task.getIMEI(),'hash':task.getHash(),'code':task.getCode(),'status':str(task.getStatus()),'progress':task.getProgress()})
        db.close()
        #Return a tuple of all tasks and their parameters. To be used in a call to the DHServer
        return response
    
    def hostReset(self):
        if not self.__JD==None: 
            self.__JD.resetErrorHost()
            return True
        return False
    
    def deleteTasks(self,tskList):
        db = DB()
        db.connect()
        response=[]
        for item in tskList:
            db.delTaskByID(item['imei'], item['hash'])
            response.append({'imei':item['imei'],'hash':item['hash'],'status':'deleted'})
        return response
    
    def status(self):
        response={'JD Status':self.__JD,'JD Length':len(self.__JD),'JD Task':self.__JD.getTask(),'SM Stopped':self.__stopProcessing,'SM Length':self.pq.qsize()}
        return response
    
    def quit(self):
        self.__stopProcessing=True
        self.__quit=True

if __name__ == '__main__':
    pass