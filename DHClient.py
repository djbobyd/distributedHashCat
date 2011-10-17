'''
Created on Aug 27, 2011

@author: boby
'''
import ast, getopt
import sys
from restkit import Resource, BasicAuth

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
        opts, args = getopt.getopt(argv, "hs:e:f:", ["help", "startPercent=" , "endPercent=" , "outFile="]) 
    except getopt.GetoptError:           
        usage()                          
        sys.exit(2)   
    
    for opt, arg in opts:                
        if opt in ("-h", "--help"):      
            usage()                     
            sys.exit()                                  
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

    if len(hash)==0:
        print "No hash to crack has been provided! Exiting..."
        usage()
        sys.exit(0)   

if __name__ == "__main__":
    auth = BasicAuth("hashcat", "P@ssw0rd")
    r = Resource("http://localhost:8000", filters=[auth])
    s=r.get('/progress')
    d=ast.literal_eval(s.body_string())
    print d['progress']


    