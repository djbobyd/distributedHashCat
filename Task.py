'''
Created on Sep 18, 2011

@author: boby
'''
import random, time, string
from Enum import Enum
from Config import Config

log = Config().getLogger('submitMaster.Task')
config = Config().getConfig()

class Command(object):
    def __init__(self,cmd,env=[]):
        self.cmd=cmd
        self.env=env
    def getCommand(self):
        command=''
        if self.env==[]:
            return self.cmd
        else:
            for var in self.env:
                command=var[0]+'='+var[1]+' '
            return command+self.cmd
    def __str__(self):
        return "Command is %s" % self.cmd

class Priorities(Enum):
    Low=50
    Normal=20
    High=10
    Critical=0
        
class States(Enum):
    Pending=0
    Running=10
    Failed=20
    Completed=30
    
    
class Task(object):
    N=6
    
    @classmethod
    def deserialize(Task,text):
        task=Task('','')
        Task.__fillInstance(task,text)
        return task
    
    def __init__(self, imei, hash, priority=Priorities.Low, executable="oclHashcat-lite64.bin"):
        self.__exec=executable
        self.__prio=Priorities.__enum__(int(priority))
        self.__hash=hash
        self.__imei= imei
        self.__taskID=''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(self.N))
        self.__code=None
        self.__outFile=self.__taskID+'.txt'
        self.__creationTime=time.ctime()
        self.__startTime=None
        self.__completionTime=None
        self.__status=States.Pending
        self.__progress=0.0

    def __fillInstance(self,text):
        print text
        text=text.split('|')
        self.__exec=text[0]
        self.__prio=getattr(Priorities,text[1].split(".")[1])
        self.__imei= text[2]
        self.__hash=text[3]
        self.__taskID=text[4]
        self.__code=text[5]
        self.__outFile=text[6]
        self.__creationTime=time.strftime(text[7])
        self.__startTime=time.strftime(text[8])
        self.__completionTime=time.strftime(text[9])
        self.__status=getattr(States,text[10].split(".")[1])
        self.__progress=float(text[11])
    
    def __cmp__(self,other):
        if self.__prio==other.__prio:
            if self.__creationTime>other.__creationTime: return 1
            if self.__creationTime==other.__creationTime: return 0
            if self.__creationTime<other.__creationTime: return -1
        if self.__prio<other.__prio: return 1
        if self.__prio>other.__prio: return -1
    
    def __repr__(self):
        return "(%s|%s)" % (self.__imei, self.__hash)
    
    def serialize(self):
        return "%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s"%(self.__exec,self.__prio,self.__imei,self.__hash,self.__taskID,self.__code,self.__outFile,self.__creationTime,self.__startTime,self.__completionTime,self.__status,self.__progress)
    
    def __calculateStart(self,percent):
        return percent*1000000000
    
    def getTaskID(self):
        return self.__taskID
    def getHash(self):
        return self.__hash
    def getIMEI(self):
        return self.__imei
    def getCreationTime(self):
        return self.__creationTime
    def getStartTime(self):
        return self.__startTime
    def getEndTime(self):
        return self.__completionTime
    def getPrio(self):
        return self.__prio
    def getProgress(self):
        return self.__progress
    def getStatus(self):
        return self.__status
    def getCode(self):
        return self.__code
    
    def setCode(self,value):
        self.__code=value
    def setStatus(self,status):
        self.__status=status
        if self.__status == States.Running: self.__startTime=time.ctime()
        if self.__status in [States.Completed, States.Failed]:self.__completionTime=time.ctime()
    def setProgress(self,progress):
        self.__progress=float(progress)
    
    def __calculateEnd(self,percent):
        return percent*10000000000000
    
    def createCommandList(self):
        cmdList=[]
        envList=[]
        env=config['env']
        for envItem in env:
            if envItem["value"]!= " ":
                envList.append((envItem["name"],envItem["value"]))
        hashIMEI=str(self.__hash)+":00"+str(self.__imei)[:-1]+"00"
        for i in range(100):
            command=self.__exec+" "+hashIMEI+" -m 1900 -n 160 --pw-skip="+str(self.__calculateStart(i))+" --pw-limit="+str(self.__calculateEnd(i+1))+" --restore-timer=5 --gpu-watchdog=100 --outfile-format=1 --outfile="+self.__outFile+" -1 00010203040506070809 ?1?1?1?1?1?1?1?1?1?1?1?1?1?1?1"
            cmdList.append(Command(command,envList))
        #log.debug(cmdList)
        return cmdList