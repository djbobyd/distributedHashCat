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

# The resource to list all the file information under path relative to the top-level directory

@restlite.resource
def files():
    def GET(request):
        global directory
        if '..' in request['PATH_INFO']: raise restlite.Status, '400 Invalid Path'
        path = os.path.join(directory, request['PATH_INFO'][1:] if request['PATH_INFO'] else '')
        try:
            files = [(name, os.path.join(path, name), request['PATH_INFO'] + '/' + name) for name in os.listdir(path)]
        except: raise restlite.Status, '404 Not Found'
        def desc(name, path, url):
            if os.path.isfile(path):
                return ('file', (('name', name), ('url', '/file'+url), ('size', os.path.getsize(path)), ('mtime', int(os.path.getmtime(path)))))
            elif os.path.isdir(path):
                return ('dir', (('name', name), ('url', '/files'+url)))
        files = [desc(*file) for file in files]
        return request.response(('files', files))
    return locals()

# download a given file from the path under top-level directory

def file(env, start_response):
    global directory
    path = os.path.join(directory, env['PATH_INFO'][1:] if env['PATH_INFO'] else '')
    if not os.path.isfile(path): raise restlite.Status, '404 Not Found'
    start_response('200 OK', [('Content-Type', 'application/octet-stream')])
    try:
        with open(path, 'rb') as f: result = f.read()
    except: raise restlite.Status, '400 Error Reading File'
    return [result]

# create an authenticated data model with one user and perform authentication for the resource

model = restlite.AuthModel()
model.register('hashcat', 'localhost', crypto.decrypt(config['serverpass']))


@restlite.resource
def stoptasks():
    def POST(request,entity):
        global model
        model.login(request)
        sm.stopTaskProcessing()
        return request.response(('status','Initiated global stop!'))
    return locals()

@restlite.resource
def starttasks():
    def POST(request,entity):
        global model
        model.login(request)
        sm.startTaskProcessing()
        return request.response(('status','Initiated global start!'))
    return locals()

@restlite.resource
def hash():
    def POST(request, entity):
        global model
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
        global model
        model.login(request)
        return request.response(('progress',sm.getTasks()))
    return locals()

# all the routes

routes = [
    (r'GET,PUT,POST /(?P<type>((xml)|(plain)))/(?P<path>.*)', 'GET,PUT,POST /%(path)s', 'ACCEPT=text/%(type)s'),
    (r'GET,PUT,POST /(?P<type>((json)))/(?P<path>.*)', 'GET,PUT,POST /%(path)s', 'ACCEPT=application/%(type)s'),
    (r'POST /hash', hash),
    (r'GET /progress', progress),
    (r'GET /files', files),
    (r'GET /file', file),
    (r'POST /stoptasks', stoptasks),
    (r'POST /starttasks', starttasks)
]  
sm=SubmitMaster()
sm.start()
httpd = make_server('', 8000, restlite.router(routes))
try: 
    httpd.serve_forever()
except KeyboardInterrupt:
    log.info("Keyboard interrupted")
    sm.quit()
    sys.exit(0)