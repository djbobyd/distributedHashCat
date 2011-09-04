'''
Created on Sep 4, 2011

@author: boby
'''
import unittest
from jobDistributor import *

class TestJobDistributor(unittest.TestCase):


    def setUp(self):
        self.JD=JobDistributor()


    def tearDown(self):
        pass


    def testInfo(self):
        self.assertTrue(self.JD.info())


suite = unittest.TestLoader().loadTestsFromTestCase(TestJobDistributor)
unittest.TextTestRunner(verbosity=2).run(suite)