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
    def __init__(self,cmd,id,env=[]):
        self.__cmd=cmd
        self.__env=env
        self.__id=id
        
    def getID(self):
        return self.__id
    def setID(self,id):
        self.__id=id
    def getCommand(self):
        command=''
        if self.__env==[]:
            return self.__cmd
        else:
            for var in self.__env:
                command=command+var[0]+'='+var[1]+' '
            return command+self.__cmd
    def __str__(self):
        return "Command is %s" % self.__cmd
    def __repr__(self):
        return self.__cmd

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
    Paused=40
    Aborted=50
    
    
class Task(object):
    N=6
    
    @classmethod
    def deserialize(Task,text):
        task=Task('','')
        Task.__fillInstance(task,text)
        return task
    
    def __init__(self, imei, hash, priority=Priorities.Low, executable=config["executable"]):
        self.__exec=executable
        try:
            self.__prio=getattr(Priorities, priority.split(".")[1])
        except:
            self.__prio=Priorities.__enum__(int(priority))
        self.__hash=hash
        self.__imei= imei
        self.__taskID=''.join(random.choice(string.ascii_uppercase + string.digits) for x in range(self.N))
        self.__code=None
        self.__outFile=self.__taskID+'.txt'
        self.__creationTime=time.gmtime()
        self.__startTime=None
        self.__completionTime=None
        self.__status=States.Pending
        self.__progress=0.0
        self.__jobList=range(100)

    def __fillInstance(self,text):
        text=text.split('|')
        self.__exec=text[0]
        self.__prio=getattr(Priorities,text[1].split(".")[1])
        self.__imei= text[2]
        self.__hash=text[3]
        self.__taskID=text[4]
        self.__code=text[5]
        self.__outFile=text[6]
        self.__creationTime=time.strptime(text[7])
        try:
            self.__startTime=time.strptime(text[8])
        except:
            self.__startTime=None
        try:
            self.__completionTime=time.strptime(text[9])
        except:
            self.__completionTime=None
        self.__status=getattr(States,text[10].split(".")[1])
        self.__progress=float(text[11])
        self.__jobList= [int(i) for i in text[12][1:-1].split(",")]
        
    
    def __cmp__(self,other):
        """
        Comparison works the opposite way, as the PriorityQueue that we use returns the lowest element first 
        """
        if not other == None:
            if self.__prio==other.__prio:
                if self.__creationTime>other.__creationTime: return 1
                if self.__creationTime==other.__creationTime: return 0
                if self.__creationTime<other.__creationTime: return -1
            if self.__prio<other.__prio: return -1
            if self.__prio>other.__prio: return 1
        else:
            return -2
    
    def __repr__(self):
        return "(%s|%s)" % (self.__imei, self.__hash)
    def __str__(self):
        return self.serialize()
    
    def serialize(self):
        creationTime=time.asctime(self.__creationTime)
        try:
            startTime=time.asctime(self.__startTime)
        except:
            startTime=str(None)
        try:
            completionTime=time.asctime(self.__completionTime)
        except:
            completionTime=str(None)
        return "%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s|%s"%(self.__exec,self.__prio,self.__imei,self.__hash,self.__taskID,self.__code,self.__outFile,creationTime,startTime,completionTime,self.__status,self.__progress,self.__jobList)
    
    def __calculateStart(self,percent):
        return percent*1000000000
    
    def getTaskID(self):
        return self.__taskID
    def getHash(self):
        return self.__hash
    def getIMEI(self):
        return self.__imei
    def getCreationTime(self):
        return time.asctime(self.__creationTime)
    def getStartTime(self):
        try:
            time=time.asctime(self.__startTime)
        except:
            time=str(None)
        return time
    def getEndTime(self):
        try:
            time=time.asctime(self.__completionTime)
        except:
            time=str(None)
        return time
    def getPrio(self):
        return self.__prio
    def getProgress(self):
        return self.__progress
    def getStatus(self):
        return self.__status
    def getCode(self):
        return self.__code
    
    def delJobID(self,id):
        self.__jobList.remove(id)
    def addJobID(self):
        self.__jobList.insert(0,id)
    def getJobCount(self):
        return len(self.__jobList)
    
    def setCode(self,value):
        self.__code=value
    def setStatus(self,status):
        self.__status=status
        if self.__status == States.Running: self.__startTime=time.gmtime()
        if self.__status in [States.Completed, States.Failed]:self.__completionTime=time.gmtime()
    def setProgress(self,progress):
        self.__progress=float(progress)
    
    def __calculateEnd(self,percent):
        return percent*10000000000000
    
    def createCommandList(self):
        cmdList=[]
        envList=[]
        env=config['env']
        for envItem in env:
            if envItem["value"]!= "":
                envList.append((envItem["name"],envItem["value"]))
        hashIMEI=str(self.__hash)+":00"+str(self.__imei)[:-1]+"00"
        for i in self.__jobList:
            command = "%s %s -m %s -n %s --pw-skip=%i --pw-limit=%i --restore-timer=5 --gpu-watchdog=%s --outfile-format=1 --outfile=%s -1 00010203040506070809 ?1?1?1?1?1?1?1?1?1?1?1?1?1?1?1"%(self.__exec,hashIMEI,config["hashcatType"],config["hashcatGPULoad"],self.__calculateStart(i),self.__calculateEnd(i+1),config["hashcatGPUTemp"],self.__outFile)
            cmdList.append(Command(command,i,envList))
        return cmdList