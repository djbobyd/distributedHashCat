'''
Created on Aug 18, 2011

@author: boby
'''
import logging.config, yaml
from HashCat import SSHController, results

config = yaml.load(open('log.yml', 'r'))
logging.config.dictConfig(config)
log = logging.getLogger("root")

if __name__ == '__main__':
    test="proba"
    test1="second"
    log.info("Test message")
    log.error("Error test %s - %s" % (test, test1))
    res = results()
    ssh=SSHController("192.168.1.137", "boby", "098334057", "ping -c 10 dir.bg", res)
    ssh.start()