'''
Created on Sep 20, 2011

@author: boby
'''
from Crypto.Cipher import AES
import base64
import os, string, random, getopt, sys


class Encryption(object): 
    # the block size for the cipher object; must be 16, 24, or 32 for AES
    __BLOCK_SIZE = 32
     
    # the character used for padding--with a block cipher such as AES, the value
    # you encrypt must be a multiple of BLOCK_SIZE in length. This character is
    # used to ensure that your value is always a multiple of BLOCK_SIZE
    __PADDING = '{'
    
    # generate a random secret key
    #secret = os.urandom(__BLOCK_SIZE)
    
    def __init__(self): 
        # one-liner to sufficiently pad the text to be encrypted
        self.pad = lambda s: s + (Encryption.__BLOCK_SIZE - len(s) % Encryption.__BLOCK_SIZE) * Encryption.__PADDING
        # one-liners to encrypt/encode and decrypt/decode a string
        # encrypt with AES, encode with base64
        self.__EncodeAES = lambda c, s: base64.b64encode(c.encrypt(self.pad(s)))
        self.__DecodeAES = lambda c, e: c.decrypt(base64.b64decode(e)).rstrip(Encryption.__PADDING)
        if not os.path.exists('encryption.key'):
            self.__secret = ''.join(random.choice(string.printable) for x in range(32))
            file = open('encryption.key',"w")
            file.write(self.__secret)
            file.close()
        else:
            file = open('encryption.key')
            self.__secret = file.read()
        # create a cipher object using the random secret
        self.__cipher = AES.new(self.__secret)
    
    def encrypt(self, plainPass):
        return self.__EncodeAES(self.__cipher, plainPass)
    def decrypt(self,cryptPass):
        return self.__DecodeAES(self.__cipher, cryptPass)


def usage():
    print "Usage:  %s [flags] string"% os.path.basename(__file__)
    print "Flags available:"
    print "    -h help"
    print "    -d decrypt the given password"
    print "    -e encrypt the given text"

def main(argv):                         
    
    action=''
    string=''
                     
    try:                                
        opts, args = getopt.getopt(argv, "hed", ["help", "encrypt" , "decrypt"]) 
    except getopt.GetoptError:           
        usage()                          
        sys.exit(2)   
    
    global debug
    
    for opt, arg in opts:                
        if opt in ("-h", "--help"):      
            usage()                     
            sys.exit()                                   
        elif opt in ("-d", "--decrypt"): 
            action="Decrypt"
        elif opt in ("-e", "--encrypt"): 
            action="Encrypt"             

    string = "".join(args)

    if len(string)==0:
        print "No password for processing has been provided! Exiting..."
        usage()
        sys.exit(0)
    
    enc=Encryption()
    if action=="Decrypt":    
        print enc.decrypt(string)
    elif action=="Encrypt":
        print enc.encrypt(string)

if __name__ == "__main__":
    main(sys.argv[1:])