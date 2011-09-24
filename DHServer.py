'''
Created on Sep 4, 2011

@author: boby
'''
import os, thread, md5
import restlite
import sys, ast
from wsgiref.simple_server import make_server
from submitMaster import SubmitMaster
from Encryption import Encryption
from Config import Config

# The top-level directory for all file requests

directory = '.'
crypto=Encryption()
config=Config.getConfig()
log=Config().getLogger('root')


# create an authenticated data model with one user and perform authentication for the resource

model = restlite.AuthModel()
model.register('hashcat', 'localhost', crypto.decrypt(config['serverPass']))


@restlite.resource
def stoptasks():
    def POST(request,entity):
        model.login(request)
        sm.stopTaskProcessing()
        return request.response(('status','Initiated global stop!'))
    return locals()

@restlite.resource
def starttasks():
    def POST(request,entity):
        model.login(request)
        sm.startTaskProcessing()
        return request.response(('status','Initiated global start!'))
    return locals()

@restlite.resource
def hash():
    def POST(request, entity):
        model.login(request)
        dic=ast.literal_eval(entity)
        priority=dic["priority"]
        hash=dic["hash"]
        imei=dic["imei"]
        sm.enqueueTask(imei,hash,priority)
        return request.response(('hash','Accepted'))
    return locals()

@restlite.resource
def progress():
    def GET(request):
        model.login(request)
        return request.response(('progress',sm.getTasks()))
    return locals()

# all the routes

routes = [
    (r'POST /hash', hash),
    (r'GET /progress', progress),
    (r'POST /stoptasks', stoptasks),
    (r'POST /starttasks', starttasks)
]  
sm=SubmitMaster()
sm.start()
httpd = make_server(config["serverHost"], config["serverPort"], restlite.router(routes))
try: 
    httpd.serve_forever()
except KeyboardInterrupt:
    log.info("Keyboard interrupted")
    sm.quit()
    sys.exit(0)