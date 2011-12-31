'''
Created on Sep 4, 2011

@author: boby
'''
import ast
import restlite
import sys, json
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
    def GET(request):
        model.login(request)
        sm.stopTaskProcessing()
        return request.response(('status','Initiated global stop!'))
    return locals()

@restlite.resource
def starttasks():
    def GET(request):
        model.login(request)
        sm.startTaskProcessing()
        return request.response(('status','Initiated global start!'))
    return locals()


@restlite.resource
def deljob():
    def POST(request, entity):
        model.login(request)
        try:
            dic=dict(json.loads(json.dumps(entity)))
            Hash=dic["hash"]
            imei=dic["imei"]
        except:
            try:
                dic=dict(ast.literal_eval(entity))
                Hash=dic["hash"]
                imei=dic["imei"]
            except:
                try:
                    dic=dict(entity)
                    Hash=dic["hash"]
                    imei=dic["imei"]
                except:
                    log.error("Wrong input format: %s"%entity)
                    return request.response(('status','False'))
        if len(imei) != 0 and len(Hash) != 0:
            return request.response(('status',sm.dequeueTask(imei,Hash)))
        else:
            log.error("one of the mandatory parameters was not present. hash is: %s , imei is: %s"%(Hash,imei))
            return request.response(('status','False'))
    return locals()
@restlite.resource
def job():
    def POST(request, entity):
        model.login(request)
        try:
            dic=dict(json.loads(json.dumps(entity)))
            priority=dic["priority"]
            Hash=dic["hash"]
            imei=dic["imei"]
        except:
            try:
                dic=dict(ast.literal_eval(entity))
                priority=dic["priority"]
                Hash=dic["hash"]
                imei=dic["imei"]
            except:
                try:
                    dic=dict(entity)
                    priority=dic["priority"]
                    Hash=dic["hash"]
                    imei=dic["imei"]
                except:
                    log.error("Wrong input format: %s"%entity)
                    return request.response(('status','False'))
        if len(imei) != 0 and len(Hash) != 0:
            return request.response(('status',sm.enqueueTask(imei,Hash,priority)))
        else:
            log.error("one of the mandatory parameters was not present. hash is: %s , imei is: %s"%(Hash,imei))
            return request.response(('status','False'))
    return locals()

@restlite.resource
def progress():
    def POST(request, entity):
        model.login(request)
        try:
            dic=dict(json.loads(json.dumps(entity)))
        except:
            try:
                dic=dict(ast.literal_eval(entity))
            except:
                try:
                    dic=dict(entity)
                except:
                    log.error("Wrong input format: %s"%entity)
                    return request.response(('progress','False'))
        return request.response(('progress',sm.getTasks(dic["progress"])))
    def GET(request):
        model.login(request)
        return request.response(('progress',sm.getTasks()))
    return locals()

@restlite.resource
def delete():
    def POST(request,entity):
        model.login(request)
        try:
            dic=dict(json.loads(json.dumps(entity)))
        except:
            try:
                dic=dict(ast.literal_eval(entity))
            except:
                try:
                    dic=dict(entity)
                except:
                    log.error("Wrong input format: %s"%entity)
                    return request.response(('progress','False'))
        return request.response((sm.deleteTasks(dic)))
    return locals()

@restlite.resource
def status():
    def GET(request):
        model.login(request)
        return request.response((sm.status()))
    return locals()

@restlite.resource
def reset():
    def GET(request):
        model.login(request)
        return request.response(('Hosts errors reset status',sm.hostReset()))
    return locals()

# all the routes

routes = [
    (r'POST /job', job),
    (r'POST /deljob', deljob),
    (r'POST /progress', progress),
    (r'GET /stoptasks', stoptasks),
    (r'GET /starttasks', starttasks),
    (r'GET /progress', progress),
    (r'GET /status', status),
    (r'POST /delete', delete),
    (r'GET /reset', reset)
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