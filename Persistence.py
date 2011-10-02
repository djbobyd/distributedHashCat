'''
Created on Sep 17, 2011

@author: boby
'''
import sqlite3
from Config import Config
from Task import Task

log = Config().getLogger('submitMaster.Persistence')

class DB(object):
    '''
    classdocs
    '''

    def connect(self):
        self.__connection = sqlite3.connect('hash.db', detect_types = sqlite3.PARSE_DECLTYPES)
        self.__cursor = self.__connection.cursor()
        try:
            self.__cursor.execute('CREATE TABLE tasks (tsk Task unique)')
            self.__connection.commit()
        except sqlite3.OperationalError:
            log.debug("couldn't create table, it may already exist!")
        sqlite3.register_adapter(Task, self.__taskAdapt)
        sqlite3.register_converter("Task", self.__taskConvert)
        
    def __taskAdapt(self,task):
        return task.serialize()
    def __taskConvert(self,text):
        return Task.deserialize(text)   
    
    def addTask(self,Tsk):
        if self.getTaskByID(Tsk.getIMEI,Tsk.getHash) == None:
            self.__cursor.execute('INSERT INTO tasks(tsk) VALUES (?)',(Tsk,))
            self.__connection.commit()
            return True
        else:
            log.debug("Task already exist in DB!")
            return False
    
    def delTaskByID(self,imei,hash):
        self.__cursor.execute("DELETE FROM tasks WHERE tsk LIKE ?",('%'+str(imei)+'|'+str(hash)+'%',))
        self.__connection.commit()
    
    def getTaskByID(self,imei,hash):
        self.__cursor.execute("SELECT tsk FROM tasks WHERE tsk LIKE ?",('%'+str(imei)+'|'+str(hash)+'%',))
        try:
            tsk=self.__cursor.fetchone()[0]
            return tsk 
        except:
            log.debug("No element with imei: %s and hash: %s found"%(imei,hash))
            return None
    
    def getTasksWithID(self,hashID):
        #TODO test this method
        resultTSK=[]
        for item in hashID:
            tsk=self.getTaskByID(item["imei"],item["hash"])
            if not tsk == None: 
                resultTSK.append()
        return resultTSK
    
    def getAllTasks(self):
        self.__cursor.execute("SELECT tsk FROM tasks")
        tpl=self.__cursor.fetchall()
        task= []
        for t in tpl:
            task.append(t[0])
        return tuple(task)
    
    def updateTask(self,Tsk):
        self.__cursor.execute("UPDATE tasks SET tsk=? WHERE tsk LIKE ?",(Tsk,'%'+str(Tsk.getIMEI())+'|'+str(Tsk.getHash())+'%',))
        self.__connection.commit()
    
    def close(self):
        self.__cursor.close()
        self.__connection.close()