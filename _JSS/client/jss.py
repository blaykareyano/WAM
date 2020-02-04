from __future__ import print_function
import sys
import glob
import os
from utils.parseJSONFile import parseJSONFile
import fnmatch, re
import getpass
import json
import shutil
from string import Template
import Pyro4
import Pyro4.util
import socket
import time
import pickle
import argparse

Pyro4.config.HMAC_KEY = '4uest#Integri3yAEBoulder!'
Pyro4.config.COMMTIMEOUT = 90.0


class JSSClient(object):
    """Class for job submission system client"""
    def __init__(self, userArgs):

        self.parser = argparse.ArgumentParser(prog="jss")

        self.parser.add_argument("-abq", "-abaqus", help="to scan for abaqus *.inp files",
                    action="store", nargs='*')

        self.parser.add_argument("-star", "-starccm", help="to scan for Star-CCM+ *.sim files",
                    action="store", nargs='*')

        self.parser.add_argument("-g", "-generic", action="store", 
            help= "used to scan for files given extensions or specify multiple generic file types that we wish to run (i.e., bash scripts, python scripts, java, etc)", nargs='+')

        self.parser.add_argument("-n","-name", help="to specify the json file name created to submit the job. JSS will create a file with the default name if no name is given")


        self.parser.add_argument("-sub", "-submit", help="to scan the current directory for all *.json job files (if no files are specifed), or use the specified *.json files and submits them to the queue",
                    action="store", nargs='*')

        self.parser.add_argument("-q", "-queue", help="to check the job queue",
                    action="store_true")

        self.parser.add_argument("-qa", "-qA", "-queueAll", help="to check the job queue for all computers running JSS in the network",
                    action="store_true")

        self.parser.add_argument("-k", "-kill", help="used to kill jobs by providing job ids (ex: jss -k 23 24, to kill jobs 23 & 24)",  nargs='+')

        self.parser.add_argument("-about", help="to see version, author, and licensing information", action="store_true")

        if len(sys.argv)==1:
            self.parser.print_help()
            sys.exit(2)

        userArgs = self.parser.parse_args()

        self.jsonFileName = None


        self.clientScriptDirectory = os.path.dirname(os.path.realpath(__file__)) # directory where this file is located
        self.loadConfFile()

        # now get the serialized jss server uri:
        trials = 1
        while True:  
            if os.path.isfile("/opt/JSS/server/jss_uri.p.lock"):
                # /opt/JSS/server/jss_uri.p is being written to, and is locked.
                # try for 5 seconds
                time.sleep(0.5)
                trials = trials + 1
            else:
                assert os.path.isfile("/opt/JSS/server/jss_uri.p"), "Error:\t Problem loading uri from /opt/JSS/server/jss_uri.p"
                self.jss_uri = pickle.load(open("/opt/JSS/server/jss_uri.p","rb"))
                break
            if (trials > 10):
                print("Error:\t jss_uri.p file is locked. Please remove /opt/JSS/server/jss_uri.p.lock")
                sys.exit(1)


        #execute jss command line arguments:
        if (userArgs.about): 
            self.getAboutText()
            sys.exit(0)   

        if (userArgs.q):
            self.getQueue()
            sys.exit(0)

        if (userArgs.qa):
            self.getQueueAllComputers()
            sys.exit(0)

        if (userArgs.k):
            self.killJob(userArgs.k)
            sys.exit(0)   

        if (userArgs.n):

            if ((userArgs.star is False) and (userArgs.abq is False) and (userArgs.g is None)):
                print("Error:\t Missing argument. Please specify what type of job you wish to submit (i.e., generic, Star-CCM+, Abaqus, ...).")
                sys.exit(2)

            f = os.path.abspath(userArgs.n) 
            fileName, fileExtension = os.path.splitext(f)
            if ((fileExtension is None) or (fileExtension.strip() == "")):
                fileName = "%s%s"%(fileName,".json")

            self.jsonFileName = fileName
                

        if (isinstance(userArgs.star,list)):
            self.scanDirForSimulationFiles(starFiles = True, files = userArgs.star)

        if (isinstance(userArgs.abq,list)):
            self.scanDirForSimulationFiles(abaqusFiles = True, files = userArgs.abq)

        if (userArgs.g):
            self.scanDirForSimulationFiles(genericFiles = True, files = userArgs.g)

        if (isinstance(userArgs.sub,list)):
            if (len(userArgs.sub) == 0): # submit all files *.json files in the current directory
                self.submit()
                sys.exit(0) 
            else:
                self.submit(userArgs.sub) # submit specified json files
                sys.exit(0)                

    def findfiles(self,which, where='.'):
        '''Returns list of filenames from `where` path matched by 'which'
           shell pattern. Matching is case-insensitive.'''
        
        rule = re.compile(fnmatch.translate(which), re.IGNORECASE)
        return [name for name in os.listdir(where) if rule.match(name)]

    def loadConfFile(self):
        """Loads the clientConf.json file containing default values"""
        self.confFile = parseJSONFile(os.path.join(self.clientScriptDirectory,r"conf","clientConf.json"))

    def createBkupJSONFile(self, filepath):
        """Creates a copy of the existing file if present with and '_OLD' to its name. So
        we don't overwrite a user-generated *.json file.
        """
        if os.path.isfile(filepath):
            bkupFile = "%s_OLD"%(filepath)
            self.createBkupJSONFile(bkupFile) # make sure we don't overwrite the previous bkup file
            shutil.copyfile(filepath,bkupFile)

    def scanDirForSimulationFiles(self, starFiles = False, abaqusFiles = False, genericFiles = False, files = None):
        """Scans the current directory starccm+ or abaqus files and creates *.json file for each encountered simulation file"""
        curDir = os.getcwd()  # directory where we are calling this script from
        assert starFiles or abaqusFiles or genericFiles, "Please specify what type of file we are scanning"

        if starFiles: # we are dealing with star-ccm+ run files:

            simFiles = []

            if (len(files) == 0):

                for fileExt in self.confFile["fileExtensions"]["starccm"]:
                    simF = self.findfiles(fileExt,curDir)

                for s in simF:
                    simFiles.append(os.path.join(curDir,s))

            else:
                validatedFiles = []
                for f in files:
                    if not os.path.isfile(f):
                        print ("Error:\tUnable to locate %s file(s)"%(f))
                        print ("Exiting...")
                        sys.exit(2)
                    # validate file extension:
                    fileName, fileExtension = os.path.splitext(f)
                    if ("*%s"%(fileExtension) not in self.confFile["fileExtensions"]["starccm"]):
                        print("Error:\tValid star-ccm+ input file extensions are:")
                        for ext in self.confFile["fileExtensions"]["starccm"]:
                            print("Error:\t\t%s"%(ext))
                        print("Error: Not a valid star-ccm+ file -> %s"%(f))
                        sys.exit(2)
                    
                    validatedFiles.append(os.path.abspath(f))

                simFiles = validatedFiles[:]

            if (len(simFiles) == 0):
                print("Error:\tNo star-ccm+ files were located in this directory!")
                print("Error:\tValid star-ccm+ file extensions:")
                for ext in self.confFile["fileExtensions"]["starccm"]:
                    print("Error:\t\t%s"%(ext))

                sys.exit(2)


            simFiles.sort()

            # write the starSubmit.json file:

            with open(os.path.join(self.clientScriptDirectory,r"conf",
                self.confFile["starccmOptions"]["starccmJSONTemplateFile"]), "r") as f:
                tmpl = f.read()

            d = {}
            d["emailAddress"] = "%s@%s"%(getpass.getuser(),self.confFile["defaultEmailDomain"])
            d["nCPUs"]        = self.confFile["starccmOptions"]["defaultCPUs"]
            d["licenseType"]  = self.confFile["starccmOptions"]["defaultLicense"]
            d["simFiles"]     = json.dumps(simFiles)

            # check to see if there are any java file in the directory already:
            javaFiles = self.findfiles("*.java",curDir)
            if (len(javaFiles) > 0): # let's use the most recent java file
                javaMacroFile = max(glob.iglob('*.[Jj][Aa][Vv][Aa]'), key=os.path.getctime)
            else:  # use default macro
                javaMacroFile = self.confFile["starccmOptions"]["defaultJavaMacro"]
                #shutil.copyfile(os.path.join(self.clientScriptDirectory,r"conf",
                #self.confFile["starccmOptions"]["defaultJavaMacro"]), 
                #curDir)
                cpFrom = os.path.join(self.clientScriptDirectory,r"conf", javaMacroFile)

                cpTo = os.path.join(curDir, javaMacroFile)

                shutil.copyfile(cpFrom,cpTo)

                javaMacroFile = cpTo

            d["javaMacroFile"] = os.path.join(curDir, javaMacroFile)

            # now write starSubmit.json
            jsonOutFile = Template(tmpl).substitute(d)

            if self.jsonFileName is None:
                self.jsonFileName = os.path.join(curDir,"starSubmit.json")

            self.createBkupJSONFile(self.jsonFileName)
            with open(self.jsonFileName, "w") as f:
                f.write(jsonOutFile)   


        if abaqusFiles: # we are dealing with abaqus input files:

            jobFiles = []
            if len(files) == 0:
            
                for fileExt in self.confFile["fileExtensions"]["abaqus"]:
                    inpF = self.findfiles(fileExt,curDir)

                for s in inpF:
                    jobFiles.append(os.path.join(curDir,s))

            else:
                validatedFiles = []
                for f in files:
                    if not os.path.isfile(f):
                        print ("Error:\tUnable to locate %s file(s)"%(f))
                        print ("Exiting...")
                        sys.exit(2)
                    # validate file extension:
                    fileName, fileExtension = os.path.splitext(f)
                    if ("*%s"%(fileExtension) not in self.confFile["fileExtensions"]["abaqus"]):
                        print("Error:\tValid abaqus input file extensions are:")
                        for ext in self.confFile["fileExtensions"]["abaqus"]:
                            print("Error:\t\t%s"%(ext))
                        print("Error: Not a valid abaqus file -> %s"%(f))
                        sys.exit(2)
                    else:
                        validatedFiles.append(os.path.abspath(f))

                jobFiles = validatedFiles[:]


            if (len(jobFiles) == 0):
                print("Error:\tNo abaqus input files were located in this directory!")
                print("Error:\tValid abaqus input file extensions are:")
                for ext in self.confFile["fileExtensions"]["abaqus"]:
                    print("Error:\t\t%s"%(ext))

                sys.exit(2)

            jobFiles.sort()

            # write the abaqusSubmit.json file:
            with open(os.path.join(self.clientScriptDirectory,r"conf",
                self.confFile["abaqusOptions"]["abaqusJSONTemplateFile"]), "r") as f:
                tmpl = f.read()
            d = {}
            d["emailAddress"] = "%s@%s"%(getpass.getuser(),self.confFile["defaultEmailDomain"])
            d["nCPUs"]        = self.confFile["abaqusOptions"]["defaultCPUs"]
            d["nGPUs"]        = self.confFile["abaqusOptions"]["defaultGPUs"]

            d["jobFiles"]     = json.dumps(jobFiles)

            # now write abaqusSubmit.json
            jsonOutFile = Template(tmpl).substitute(d)

            if self.jsonFileName is None:
                self.jsonFileName = os.path.join(curDir,"abaqusSubmit.json")

            self.createBkupJSONFile(self.jsonFileName)
            with open(self.jsonFileName, "w") as f:
                f.write(jsonOutFile)   

            # now loop through all of the directories to see 
            # if we need to copy an abaqus*.env file:
            for f in jobFiles:
                directory = os.path.split(f)[0]
                if not os.path.isfile(os.path.join(directory, "custom_v6.env")):
                    abqEnvFile = self.confFile["abaqusOptions"]["defaultAbqEnvFile"]
                    cpFrom = os.path.join(self.clientScriptDirectory,r"conf", abqEnvFile)
                    cpTo = os.path.join(directory, abqEnvFile)
                    shutil.copyfile(cpFrom,cpTo)
                    print ("Note: copied custom_v6.env file to %s"%(directory))

        if genericFiles:  # client trying to specify 
            # validate all file entries:
            validatedFiles = []
            for f in files:
                if not os.path.isfile(f):
                    print ("Error:\tUnable to locate %s file"%(f))
                    print ("Exiting...")
                    sys.exit(2)
                else:
                    validatedFiles.append(os.path.abspath(f))
            # load template
            with open(os.path.join(self.clientScriptDirectory,r"conf",
                self.confFile["genericFileOptions"]["genericFileJSONTemplateFile"]), "r") as f:
                tmpl = f.read()

            # save the json file:
            d = {}
            d["jobFiles"] = json.dumps(validatedFiles)
            d["emailAddress"] = "%s@%s"%(getpass.getuser(),self.confFile["defaultEmailDomain"])

            jsonOutFile = Template(tmpl).substitute(d)

            if self.jsonFileName is None:
                self.jsonFileName = os.path.join(curDir,"genericSubmit.json")

            self.createBkupJSONFile(self.jsonFileName)
            with open(self.jsonFileName, "w") as f:
                f.write(jsonOutFile)  


        print("%s job file has been created..."%(self.jsonFileName))              

    def getAboutText(self):
        sys.excepthook = Pyro4.util.excepthook
        JSS_SERVER = Pyro4.Proxy(self.jss_uri) 
        try:
            JSS_SERVER.shakeHands(getpass.getuser(), socket.getfqdn())
        except Exception as e:
            print("Error:\tUnable to connect to the JSS server!")
            return  

        print(JSS_SERVER.about())       

    def getQueue(self):
        sys.excepthook = Pyro4.util.excepthook
        JSS_SERVER = Pyro4.Proxy(self.jss_uri)
        try:
            JSS_SERVER.shakeHands(getpass.getuser(), socket.getfqdn())
        except Exception as e:
            print("Error:\tUnable to connect to the JSS server!")
            return  

        print(JSS_SERVER.getQueue())    

    def getQueueAllComputers(self):
        """Returns the queue for all computers running JSS and registered on the name server"""
        sys.excepthook = Pyro4.util.excepthook
        JSS_SERVER = Pyro4.Proxy(self.jss_uri)

        try:
            JSS_SERVER.shakeHands(getpass.getuser(), socket.getfqdn())
        except Exception as e:
            print("Error:\tUnable to connect to the JSS server!")
            print(e)
            print(JSS_SERVER)
            print(self.jss_uri)
            print(getpass.getuser())
            print(socket.getfqdn())
            return

        nsConfig = JSS_SERVER.nameServerInfo()
        

        Pyro4.config.NS_HOST = nsConfig["NS_HOST"] 
        Pyro4.config.NS_PORT = nsConfig["NS_PORT"]   

        try:
            ns = Pyro4.locateNS()
        except:
            print("Error:\t Unable to connect to the name server: %s:%i"%(nsConfig["NS_HOST"],nsConfig["NS_PORT"]))
            sys.exit(1)

        registeredServers = ns.list()
        jssServers = {}

        for key in registeredServers.keys():
            if ("jssServer" in key):
                jssServers[key] = registeredServers[key]
        print("")
        # now output the queue for each machine:
        for key in sorted(jssServers.keys()):
            serverName = key.split("jssServer-")[-1].split(".")[-2]
            try:
                print("Queue for %s:"%serverName)
                currentJSSServer = Pyro4.Proxy(jssServers[key])
                print(currentJSSServer.getQueue())
                print("")
            except:
                print("This server is currently unreachable...")
                print("")
        # output the queue for this machine in case it was not registered with the name server:
        jssNSRegisteredName = "jssServer-%s.server"%(socket.gethostname())
        if jssNSRegisteredName not in jssServers.keys():
            serverName = socket.gethostname()
            print("Warning: The jssServer for this computer (%s) does not seem to be registered with the name server."%(serverName))
            print("")
            print("Queue for %s:"%(serverName))
            print("")
            self.getQueue()
            print("")

    def submit(self, jsonFiles = None):
        """ 
        Submits all files in specified in the jsonFiles list, or scans the current working directory for all of the *.json files
        and submits them in case jsonFiles is not specified (i.e., is None)
        """
        curDir = os.getcwd()

        if jsonFiles is None:
            jsonFiles = self.findfiles("*.json",curDir)

        sys.excepthook = Pyro4.util.excepthook
        JSS_SERVER = Pyro4.Proxy(self.jss_uri)

        try:
            JSS_SERVER.shakeHands(getpass.getuser(), socket.getfqdn())
        except Exception as e:
            print("Error:\tUnable to connect to the JSS server!")
            return

        if len(jsonFiles) == 0:
             print("Error:\tNo *.json job files were located in this directory!") 
             return

        jsonFiles.sort()  # submit jobs based on alphabetical order of all *.json files!

        for jsonFile in jsonFiles:
            jData = parseJSONFile(jsonFile)
            assert "InternalUse" in jData.keys(), "*.json file (%s) is missing the InternalUse block..."%(jsonFile)
            assert ((jData["InternalUse"]["jsonFileType"] == "starccm") or
             (jData["InternalUse"]["jsonFileType"] == "abaqus") or
             jData["InternalUse"]["jsonFileType"] == "generic"), "This job type (%s) has not been implemented yet."%(jData["InternalUse"]["jsonFileType"])
            
            jData["InternalUse"]["clientWorkingDir"] = curDir # add the current working dir as abaqus probably needs it! 
            jData["InternalUse"]["clientName"] = getpass.getuser() # add user name
            jData["InternalUse"]["jsonFileName"] = jsonFile   # add the json filename
            jData["InternalUse"]["clientMachine"] = socket.getfqdn()
            jData["InternalUse"]["status"] = "submitted"


            JSS_SERVER.jobDispatcher(jData)

    def killJob(self, jobIDs):
        """Connects to the JSS server and kills a job"""

        sys.excepthook = Pyro4.util.excepthook
        JSS_SERVER = Pyro4.Proxy(self.jss_uri)

        try:
            JSS_SERVER.shakeHands(getpass.getuser(), socket.getfqdn())
        except Exception as e:
            print("Error:\tUnable to connect to the JSS server!")
            return            

        username = getpass.getuser()
        for jID in jobIDs:
            try:
                jobID = int(jID)
            except:
                print("Error:\tInvalid job id #: %s. Exiting..."%(jID))
                sys.exit(2)

            msg = JSS_SERVER.killJob(jobID, username)
            print(msg)

def main():
    clientSession = JSSClient(sys.argv)

if __name__ == '__main__':
    main()

