'''
Created on Sep 17, 2011

@author: boby
'''
import os, yaml, logging.config
from copy import deepcopy

class Config(object):
    _instance = None
    __stream = file(os.path.join(os.path.dirname(__file__),'config.yml'), 'r')
    __config = yaml.load(__stream)
    __conf = yaml.load(open(os.path.join(os.path.dirname(__file__),'log.yml'), 'r'))
    __list = __config["hosts"]
    if not os.path.exists('logs'):
        os.makedirs('logs')
    for host in __list:
        hostHandler=deepcopy(__conf["handlers"]["file"])
        hostHandler["filename"]='logs/'+host["name"]+'.log'
        __conf["handlers"][host["name"]+"_file"]=hostHandler
        hostLogger=deepcopy(__conf["loggers"]["distributor"])
        handlerList=hostLogger["handlers"]
        handlerList.remove("file")
        handlerList.append(host["name"]+'_file')
        hostLogger["handlers"]=handlerList
        __conf["loggers"]["distributor."+host["name"]]=hostLogger
    logging.config.dictConfig(__conf)
    
    def __init__(self):
        '''
        Init config class
        '''
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Config, cls).__new__(cls, *args, **kwargs)
        return cls._instance 
    
    @classmethod
    def getLogger(self,logName,host=''):
        if host!='':
            log=logging.LoggerAdapter(logging.getLogger("distributor."+host),{'clientip': host})
        else:
            log = logging.getLogger(logName)
        return log
    @classmethod
    def getConfig(self):
        return Config.__config