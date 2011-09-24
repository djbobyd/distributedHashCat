"""
Joshua Stough
W&L, Image Group
July 2011
This script tests the submitMaster and the JobDistributor. 
I'm going to ask for the execution of testScript, which is a
unix shell script that resolves the hostname and stuff like 
that, make sure we have everything working. 
[you@somewhere distributedPythonCode]$ python testSubmitMaster.py


 License: This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License as published by
 the Free Software Foundation; either version 3 of the License, or (at your
 option) any later version. This program is distributed in the hope that it
 will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty
 of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
 Public License for more details.
"""

from submitMaster import *
import os, sys, getopt
import logging.config, yaml
config = yaml.load(open('log.yml', 'r'))
logging.config.dictConfig(config)
log = logging.getLogger()

#Generate some commands.
#The extra double quotes in this commented-out set created problems:  the host
#thought the command to execute was "./testScript 'testing'" with the quotes,
#but no such file or directory is found.
#commands = ["\"./testScript 'Testing Process number %i'" % (number) + "\" &> output%i.out" % (number) \
#            for number in range(4)]
#This became wrong when I stopped using shlex to split the command in
#JobDistributor.
startPercent=''
endPercent=''
outFile=''
hash=''
debug=0

command="oclHashcat-lite64.bin"

def usage():
    print "Usage:  command [flags] hash"
    print "Flags available:"
    print "    -h help"
    print "    -d debug flag"
#    print "    -s start percent"
#    print "    -s end percent"
    print "    -f output file"

def main(argv):                         
                     
    try:                                
        opts, args = getopt.getopt(argv, "hds:e:f:", ["help", "debug" , "startPercent=" , "endPercent=" , "outFile="]) 
    except getopt.GetoptError:           
        usage()                          
        sys.exit(2)   
    
    global debug
    
    for opt, arg in opts:                
        if opt in ("-h", "--help"):      
            usage()                     
            sys.exit()                  
        elif opt == '-d':                               
            debug = 1                  
        elif opt in ("-s", "--startPercent"): 
            global startPercent
            startPercent=arg
        elif opt in ("-e", "--endPercent"): 
            global endPercent
            endPercent=arg
        elif opt in ("-f", "--outFile"): 
            global outFile
            outFile=arg               

    if len(outFile)==0:
        print "Output file cannot be empty!!! Exiting..."
        usage()
        sys.exit(2)

    global hash
    hash = "".join(args)
    
    if debug==1:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
    
    if len(hash)==0:
        print "No hash to crack has been provided! Exiting..."
        usage()
        sys.exit(0)   

if __name__ == "__main__":
    main(sys.argv[1:])

def calculateStart(percent):
    return percent*1000000000

def calculateEnd(percent):
    return percent*10000000000000

def createCommandList():
    cmdList=[]
    global command
    for i in range(100):
        cmdList.append(command+" "+hash+" -m 1900 -n 160 --pw-skip="+str(calculateStart(i))+" --pw-limit="+str(calculateEnd(i+1))+" --restore-timer=5 --gpu-watchdog=100 --outfile-format=1 --outfile="+outFile+" -1 00010203040506070809 ?1?1?1?1?1?1?1?1?1?1?1?1?1?1?1")
    log.debug(cmdList)
    return cmdList
"""
Get current dir, so we can we can cd to that in our command.
Again, as described in submitMaster and JobDistributor, it is
our responsibility to generate the line as it should be executed
on the host machines.
"""
#curDir = os.path.abspath('.')
#commands = ["cd %s; ./testScript 'Testing Process number %i'" % (curDir, number) + " &> output%i.out" % (number) for number in range(50)]
#commands = ["ping -c 10 dir.bg","ping -c 10 data.bg"]

#for comm in commands:
#    print(comm)
log.info("Sending command list to Submit Master...")
#processCommandsInParallel(commands)
#processCommandsInParallel(createCommandList())
#print createCommandList()