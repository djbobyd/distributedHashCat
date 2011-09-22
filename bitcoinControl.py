'''
Created on Aug 22, 2011

@author: boby
'''
import paramiko ,os, getopt, sys
import time, logging.config, yaml
from threading import Thread
from Encryption import Encryption
from Config import Config

config = Config().getConfig()
log = Config().getLogger('root')

class BTControl(Thread):
        
    def __init__(self, host_name, user_name, password,command=''):
        Thread.__init__(self)    
        self.host_name = host_name
        self.user_name = user_name
        self.__password = password
        self.__port = 22  #default SSH __port
        self.__chan = None
        self.command = command
        self.connection = None
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    def __str__(self) :
        #return str(self.__dict__)
        return str({"host_name":self.host_name, "user_name":self.user_name})

    def __eq__(self, other) : 
        return self.__dict__ == other.__dict__
    
    def run(self):
        if not self.check_host():
            return
        self.login()
        self.run_command(self.command)
        self.logout()
        
    def login(self):
        """Connect to a remote host and login.
            
        """
        #self.ssh.load_system_host_keys()
        #self.ssh.set_missing_host_key_policy(paramiko.WarningPolicy)
        log.debug("Making connection to remote host: %s with user: %s" % (self.host_name, self.user_name))
        self.connection = self.ssh.connect(self.host_name,self.__port, self.user_name, self.__password, timeout=5)
        log.debug("Starting Shell!")
        self.__chan = self.ssh.invoke_shell()
        log.debug("Connection established!")

    def run_command(self, command):
        """Run a command on the remote host.
            
        @param command: Unix command
        @return: Command output
        @rtype: String
        """ 
        log.debug("sending command: '%s' to host" % command)
        self.__chan.send(command+'\n')
        time.sleep(5)
        return self.__chan.send_ready()
    
    def check_host(self):
        try:
            log.debug("Making connection to remote host: %s with user: %s" % (self.host_name, self.user_name))
            self.connection = self.ssh.connect(self.host_name,self.__port, self.user_name, self.__password, timeout=5)
            log.debug("Starting Shell!")
            self.__chan = self.ssh.invoke_shell()
            self.ssh.close()
            log.debug("Host is alive and running!")
        except Exception:
            log.error("A connection to the host cannot be established!!!")
            return False
        return True
    
    def logout(self):
        """
        Close the connection to the remote host.    
        """
        log.info("closing connection to host %s" % self.host_name)
        self.ssh.close()

def usage():
    print"This is a help utility for stopping or starting bitcoins on remote machines."
    print "Usage:  %s [flags] start/stop" % os.path.basename(__file__)
    print "Flags available:"
    print "    -h help"
    print "    -d debug flag"

def main(argv):                         
                     
    try:                                
        opts, args = getopt.getopt(argv, "hd", ["help", "debug"]) 
    except getopt.GetoptError:           
        usage()                          
        sys.exit(2)   
    
    global debug
    debug=0
    
    for opt, arg in opts:                
        if opt in ("-h", "--help"):      
            usage()                     
            sys.exit()                  
        elif opt == '-d':                               
            debug = 1                  

    hash = "".join(args)
    
    if debug==1:
        log.setLevel(logging.DEBUG)
    else:
        log.setLevel(logging.INFO)
    
    if len(hash)==0:
        print "No command provided"
        usage()
        sys.exit(0)  
    
    return hash 

def execute(hash):
    computer_list = config["hosts"]
    log.info("The command is: %s" % hash)
    enc=Encryption()
    if hash == "start":
        command="bash /home/user/startpoc/sp1_as_user.sh"
    elif hash == "stop":
        #command="killall poclbm.py"
        command="screen -r \n exit"
    else:
        usage()
        sys.exit(1)
    for host in computer_list:
        RC=BTControl(host["name"], host["user"], enc.decrypt(host["pass"]), command)
        RC.start()
        
if __name__ == "__main__":
    execute(main(sys.argv[1:]))