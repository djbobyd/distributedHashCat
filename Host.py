'''
Created on Sep 6, 2011

@author: boby
'''
import paramiko, socket
from Enum import Enum
from Config import Config
from apscheduler.scheduler import Scheduler
from datetime import datetime
from dateutil.relativedelta import relativedelta


class Host(object):
    '''
    classdocs
    '''
    
    class States(Enum):
        NotAvailable=0
        Running=1
        Available=2
        Down=3
        Error=4
        Full=5
    
    def __init__(self, host, user, password, port = 22):
        self.__status = Host.States.NotAvailable
        self.__errors = 0
        self.__maxErrors=3
        self.__processes = 0
        self.__maxProcess = 0
        self.__hostName = host
        self.__userName = user
        self.__password = password
        self.__port = port
        self.log = Config().getLogger('distributor.'+host,host)
        self.__sched = Scheduler()
        self.__sched.start()
        
        
    def checkHost(self):
        self.log.debug("Start checking of host...")
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        try:
            self.log.debug("Making connection to remote host: %s on port: %i with user: %s " % (self.__hostName,self.__port, self.__userName))
            s.connect((self.__hostName, int(self.__port)))
            self.log.debug("Closing connection...")
            s.shutdown(2)
            self.log.debug("Host is alive and running!")
            if self.__status==Host.States.NotAvailable:
                self.__status=Host.States.Available
            return True
        except:
            self.log.error("A connection to the host cannot be established!!!")
            self.__status=Host.States.Down
            timechange=datetime.now()+relativedelta(seconds=5)
            job = self.__sched.add_date_job(self.__resetDown, timechange)
            return False
    
    def __resetDown(self):
        self.__status=Host.States.NotAvailable
    
    def __getSSH(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        return ssh
    
    
    def getChannel(self):
        ssh=self.__getSSH()
        try:
            self.log.debug("Making connection to remote host: %s with user: %s"%(self.__hostName, self.__userName))
            ssh.connect(self.__hostName,self.__port, self.__userName, self.__password, timeout=5)
        except:
            self.log.exception("Connection cannot be established!!!")
            return None
        self.log.debug("Connection Established!")
        return ssh
    
    def getFile(self,fileName):
        ssh=self.getChannel()
        sftp=ssh.open_sftp()
        try:
            file=sftp.open(fileName)
            string=file.readlines()
            return string
        except IOError:
            self.log.debug("No such file!!!")
            return None
    
    def closeChannel(self,ssh):
        """
        Close the connection to the remote host.    
        """
        self.log.info("Closing connection to host %s" % self.__hostName)
        ssh.close()
        self.log.debug("Connection closed!")
    
    def getHostName(self):
        return self.__hostName
    def getUserName(self):
        return self.__userName
    def getPassword(self):
        return self.__password
    def getPort(self):
        return self.__port
    def setMaxProcess(self,value):
        self.__maxProcess=value
    def setMaxErrors(self,value):
        self.__maxErrors=value
    def getStatus(self):
        return self.__status
    def addError(self):
        self.log.debug("Adding error to host")
        if self.__errors<self.__maxErrors:
            self.log.debug("Error added to host!")
            self.__errors+=1
            return self.__stateSystem()
        return False
            
    def addProcess(self):
        self.log.debug("Adding process to host")
        if self.__processes<self.__maxProcess:
            self.log.debug("Process added to host!")
            self.__processes+=1
            return self.__stateSystem()
        return False
    def delProcess(self):
        self.log.debug("Removing process from host")
        if self.__processes>0:
            self.log.debug("Process removed from host!")
            self.__processes-=1
            return self.__stateSystem()
        return False
    
    def __stateSystem(self):
        if not self.__status in [Host.States.NotAvailable, Host.States.Down]:
            if self.__processes>=self.__maxProcess:
                self.__status=Host.States.Full
            if self.__processes<=0:
                self.__status=Host.States.Available
            if 0<self.__processes<self.__maxProcess:
                self.__status=Host.States.Running
            if self.__errors>=self.__maxErrors:
                self.__status=Host.States.Error
            self.log.debug("Status of host %s is: %s"% (self.__hostName,self.__status))
            return True
        else:
            self.log.debug("Status of host %s is: %s"% (self.__hostName,self.__status))
            return False
    
    def resetErrors(self):
        self.log.debug("Errors reset for host: %s !!!"%self.__hostName)
        self.__errors=0
        self.__stateSystem()   