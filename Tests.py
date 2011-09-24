'''
Created on Sep 4, 2011

@author: boby
'''
import unittest
from jobDistributor import *
from HashCat import *
from Task import Task, Priorities

class TestJobDistributor(unittest.TestCase):


    def setUp(self):
        self.Host=Host("localhost", "boby", "098334057")
        #self.JD=JobDistributor()
        #self.HC=HashCat(self.Host)


    def tearDown(self):
        pass

    def testInfo(self):
        #self.assertTrue(self.JD.info())
        pass


class TestHost(unittest.TestCase):
    
    def setUp(self):
        self.host=Host("localhost", "boby", "098334057")
        
    def tearDown(self):
        pass
    
    def testCheckHost(self):
        self.host.checkHost()
        self.assertTrue(self.host.getStatus() in [Host.States.Available, Host.States.Down], "CheckHost function failed")
        
    def testErrors(self):
        self.host.checkHost()
        self.host.setMaxErrors(1)
        self.host.addError()
        self.assertTrue(self.host.getStatus() == Host.States.Error, "Host errors are not the expected status!!!")
        self.host.resetErrors()
        
    def testaddProcess(self):
        self.host.checkHost()
        self.host.setMaxProcess(2)
        self.host.addProcess()
        self.assertTrue(self.host.getStatus() == Host.States.Running, "Host process are not reported!!!")
        
    def testdelProcess(self):
        self.host.checkHost()
        self.host.setMaxProcess(2)
        self.host.addProcess()
        self.host.delProcess()
        self.assertTrue(self.host.getStatus() == Host.States.Available, "Host process are not reported!!!")
        
    def testfullProcess(self):
        self.host.checkHost()
        self.host.setMaxProcess(1)
        self.host.addProcess()
        self.assertTrue(self.host.getStatus() == Host.States.Full, "Host process are not reported!!!")
    
    def testdelfromFullProcess(self):
        self.host.checkHost()
        self.host.setMaxProcess(2)
        self.host.addProcess()
        self.host.addProcess()
        self.host.delProcess()
        self.assertTrue(self.host.getStatus() == Host.States.Running, "Host process are not reported!!!")

class TestCommand(unittest.TestCase):
    
    def setUp(self):
        pass
    def tearDown(self):
        pass

class TestTask(unittest.TestCase):
    
    def setUp(self):
        pass
        
    def tearDown(self):
        pass
    
    def testHashCreation(self):
        task=Task("123", "4567890", Priorities.Critical, "oclHashcat-lite64.bin")
        cmds=task.createCommandList()
        self.assertTrue(cmds[0].getCommand().find("4567890:001200")!=-1, "Hash is not calculated right!!!")
  
suite = unittest.TestLoader().loadTestsFromTestCase(TestJobDistributor)
suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestHost))
suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestCommand))
suite.addTests(unittest.TestLoader().loadTestsFromTestCase(TestTask))
unittest.TextTestRunner(verbosity=2).run(suite)