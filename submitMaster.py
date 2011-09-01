"""
Joshua Stough
W&L, Image Group
July 2011
This defines the submitMaster thread using the JobDistributor.
This process should be started by the script that generates commands
(like calculateSIFTsDistributively or testSubmitMaster) and that then
sends this thread (Process) one side of the Pipe (a Connection object).
This thread periodically polls the connection to the caller, looking for
a command to execute, then either sends it to the JobDistributor or 
queues it up if the JobDistributor is full. And then it sleeps for a
sec and repeats.

This code could obviously be much more complicated, as the caller may like some
feedback on the processes that have been sent.  I'll deal with that later, this
is just can it work (read: am I smart enough, because it obviously can work).

I guess the caller needs a doneYet option, to know when to join this process and
quit...

I've added processCommandsInParallel to this file.  This function accepts a list
of commands and does all the "start submitMaster, submit jobs, wait til finished"
stuff.  Thus, the orginal caller's code doesn't need Pipes and all, just
"generate commands, processCommandsInParallel(commands)" (as pseudocode).
See testSubmitMaster.py.

 License: This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 3 of the License, or (at your
 option) any later version. This program is distributed in the hope that it
 will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
 of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
 Public License for more details.
"""

import time,logging.config,yaml,os
#from multiprocessing import Connection
from listQueue import listQueue
from multiprocessing import Process, Pipe
from jobDistributor import *

config = yaml.load(open(os.path.join(os.path.dirname(__file__),'log.yml'), 'r'))
logging.config.dictConfig(config)
log = logging.getLogger('distributor')

stream = file('config.yml', 'r')
config = yaml.load(stream)

def submitMaster(conn):
    log.info("submit Master started...")
    JD = JobDistributor()
    jobQueue = listQueue(100)

    log.info("Job Distributor started, with %i nodes, %i jobs possible" % \
          JD.info())

    while True:
        #See if there is something to do.
        if conn.poll():
            command = conn.recv()
            if command.lower() in ['dy','doneyet','finished','done']:
                #TODO insert update information for the display
                log.info("Current progress is: %.2f" % JD.totalProgress)
                if len(JD) == 0 and jobQueue.isEmpty() :
                    log.info(JD)
                    conn.send('yes')
                    conn.close()
                    return
                else:
                    conn.send('no')
            else:
                jobQueue.enqueue(command)

        #Distribute as many jobs as possible.
        while not jobQueue.isEmpty() and not JD.isFull():
            JD.distribute(jobQueue.dequeue())
        while JD.getErrors() != 0:
            jobQueue.enqueue(JD.getErrorJob())   
            
        if not conn.poll():
            #print('Going to sleep...')
            log.debug("poll_timeout: %d"% int(config["poll_timeout"]))
            time.sleep(int(config["poll_timeout"]))


"""
Convenience function for the caller.  Every caller basically wants this:
send in jobs, wait til they're finished.
"""
def processCommandsInParallel(commands):
    #Start the submit master, which will keep track of the jobs, etc.
    pconn, cconn = Pipe()
    p = Process(target=submitMaster,args=(cconn,))
    p.start()
    log.debug("Sending commands to Job Distributor...")
    #Send the jobs in.
    for command in commands:
        pconn.send(command)

    #Don't quit until the submitMaster says it's done.
    waitCycles = int(config["wait_timeout"])
    log.debug("wait_timeout: %d"% waitCycles)
    #TODO add more logic to act as a server that can receive and execute jobs on demand
    while True:
        pconn.send('dy')
        if pconn.recv() == 'yes':
            p.join()
            return
        log.info("Still not done")
        time.sleep(waitCycles)
