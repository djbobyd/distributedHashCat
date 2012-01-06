'''
Created on Sep 17, 2011

@author: boby
'''
import os, yaml, logging.config, time
from copy import deepcopy
from configobj import ConfigObj


def _initialize():
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
    return __config, __conf

class Options(object):
    def __init__(self):
        self.__config=ConfigObj()
    def setConfig(self, cfg):
        self.__config.reset()
        self.__config.merge(cfg)
    def getConfig(self):
        return self.__config
        

class Config(object):
    _instance = None
    __Configuration = Options()
    __config,__conf = _initialize()
    logging.config.dictConfig(__conf)
    __Configuration.setConfig(__config)
    
    
    def __init__(self):
        '''
        Init config class
        '''

    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(Config, cls).__new__(cls, *args, **kwargs)
        return cls._instance 
    
    @classmethod
    def getLogger(cls,logName,host=''):
        if host!='':
            log=logging.LoggerAdapter(logging.getLogger("distributor."+host),{'clientip': host})
        else:
            log = logging.getLogger(logName)
        return log
    
    @classmethod
    def getConfig(cls):
        return cls.__Configuration.getConfig()
    
    @classmethod
    def reloadConfig(cls):
        __config, __conf = _initialize()
        logging.config.dictConfig(__conf)
        cls.__Configuration.setConfig(__config)