#!/usr/bin/python

from __future__ import absolute_import
from __future__ import print_function
import Pyro4
import time
import threading
import sys
import os
from utils.parseJSONFile import parseJSONFile
from utils.emailMisc import sendEmailMsg
import logging
import smtplib
import base64
import subprocess
from tabulate import tabulate
import random
import copy
import datetime
import signal
import pwd
import ntpath
import pickle
import socket
import atexit
from subprocess import CalledProcessError, check_output

Pyro4.config.HMAC_KEY = '4uest#Integri3yAEBoulder!'
Pyro4.config.COMMTIMEOUT = 10.0
version = 0.31

class JSSServer(object):
    """Class for the Job Submission System server"""
    def __init__(self):
        self.serverScriptDirectory = os.path.dirname(os.path.realpath(__file__)) # directory where this file is located
        self.confFileLock = threading.Lock()               # configuration file lock
        self.loadServerConfFile()                          # load server configuration file
        self.jobs = []
        self.serializeJobListLock = threading.Lock()       # thread lock used to safely serialize self.jobs list 
        self.serializeCounterLock = threading.Lock()       # thread lock used to safely serialize the JobID counter
        self.loadSerializedCounter()                       # job id counter 
        self.loadSerializedJobList()                       # load self.jobs

        runFailSafe = False

        # are we restarting jobs after the server has crashed?
        if ("failsafe" in self.serverConf.keys()):
            if ((len(self.jobs) > 0) and (self.serverConf["failsafe"] is True)):
                runFailSafe = True
                for job in self.jobs:
                    job["InternalUse"]["failsafe"] = True               
        else:
            self.jobs = [] # fail safe is not present in config file: set default to disabled

        self.currentJobID = None       # the job id for the current job that is running
        self.currentSubProcess = None  # holds the subprocess currently running one our solvers 
                                       # in case we want to kill it 

        self.start = datetime.datetime.now() # init stop watch with dummy value
        self.jobsCompleted = []
        self.CPULock = threading.Lock()      # thread lock used to restrict CPU access while running an analysis
        self.jobListLock = threading.Lock()  # thread lock used to restict access to our jobs list while it is being used
        self.jobsCompletedListLock = threading.Lock() # thread lock used to restict access to our jobsCompleted list
                                                      # while it is being used

        self.logFile = os.path.join(self.serverScriptDirectory,r"logs",self.serverConf["localhost"]["logFileFile"])  # log file path
        
        # see if the log file exists:
        if not os.path.isfile(self.logFile):
            open(self.logFile, 'a').close()  # if it doesn't, just create an empty one

        logging.basicConfig(filename=self.logFile,level=logging.DEBUG, format='%(asctime)s - %(levelname)s: %(message)s', 
            datefmt='%m/%d/%Y %I:%M:%S %p')
        logging.info("JSS server is up and running...")

        if runFailSafe:
            logging.info("Running %i failsafe jobs..."%(len(self.jobs)))
            for job in self.jobs:
                threading.Thread(target=self.__runJob, 
                    args=(job,)).start()

        self.nsThread = None  #name server connection/reconnection thread

    def connectToNameServer(self, jss_uri):
        """Function spawnes a thread that keeps connecting/reconnecting to the name
        server after every N seconds.
        """

        registerWithNameServer = self.serverConf["nameServer"]["registerWithNameServer"]

        if registerWithNameServer:
            # check to see if we should use the name server:
            def nsReregister(jss_uri):
                while 1:
                    self.loadServerConfFile() 
                    reconnectTime_sec = self.serverConf["nameServer"]["reconnectToNameServer_minutes"]*60.0 
                    try:
                        Pyro4.config.NS_HOST  = self.serverConf["nameServer"]["nameServerIP"]
                        Pyro4.config.NS_PORT  = self.serverConf["nameServer"]["nameServerPort"]
                        ns = Pyro4.locateNS()
                        ns.register("jssServer-%s.server"%(socket.gethostname()), jss_uri)
                    except Exception as e:
                        logging.error(str(e))
                        if self.serverConf["nameServer"]["quitJSSOnNameServerConnectionError"]:
                            logging.info("Stopping JSS server since quitJSSOnNameServerConnectionError was set to true in the JSS server configuration file")
                            sys.exit(1)
                        logging.error("Will attempt to reconnect to the name server (%s) in %.2f minutes"%(self.serverConf["nameServer"]["nameServerIP"],
                            self.serverConf["nameServer"]["reconnectToNameServer_minutes"]))
                    time.sleep(reconnectTime_sec)

            self.nsThread = threading.Thread(target=nsReregister, 
                args=(jss_uri,))

            self.nsThread.setDaemon(True)

            self.nsThread.start()


    def about(self):
        """Returns license and version information"""
        return """
JSS - Job Submission System - Version %s
Copyright (C) 2014 - Bruno R. Fletcher - brunofletcher@gmail.com

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
MA  02110-1301, USA.
        """%(version)


    def loadSerializedCounter(self,filePath = "/opt/JSS/server/counter.p"):
        """Loads the JobID counter from a pickle file; used to init the persistent 
           counter. If the file does not exist it will initialize self.jobID to 0.
        """
        with self.serializeCounterLock:
            if os.path.isfile(filePath):
                self.jobID = pickle.load(open(filePath,"rb"))
            else:
                self.jobID = 0

    def loadSerializedJobList(self,filePath = "/opt/JSS/server/jobList.p"):
        """Loads self.jobs list from a pickle file; used to init jobs 
           in case the server crashes or is killed while have jobs are in the queue.
        If the file does not exist it will return an empty list.
        """
        with self.serializeJobListLock:
            if os.path.isfile(filePath):
                self.jobs = pickle.load(open(filePath,"rb"))
            else:
                self.jobs = []

    def serializeCounter(self,filePath = "/opt/JSS/server/counter.p"):
        """Serialized the JobID counter using a pickle file; used to init the persistent 
           counter.
        """
        with self.serializeCounterLock:        
            try:
                pickle.dump(self.jobID, open(filePath,"wb"))
            except:
                logging.error("Unable to serialize (i.e., pickle) counter")

    def serializeJobList(self,filePath = "/opt/JSS/server/jobList.p"):
        """Serialize our job list so we can restart a given job in the queue in case
        the server application is killed.
        """
        with self.serializeJobListLock:
            try:
                pickle.dump(self.jobs, open(filePath,"wb"))
            except:
                logging.error("Unable to serialize (i.e., pickle) self.jobs")


    def getQueue(self):
        """Returns a table with the queue status of the jobs"""
        with self.jobListLock:
            if len(self.jobs[:]) == 0:
                return "The queue is empty."
            else:
                headers = ["Job ID", "User", "Job name", "Type", "Description" ,"Status"]
                table = []
                for job in self.jobs:
                    tmp = []
                    tmp.append(job["InternalUse"]["jobID"])
                    tmp.append(job["InternalUse"]["clientName"])

                    # include job name
                    if ((job["InternalUse"]["jsonFileType"] == "abaqus") or
                        (job["InternalUse"]["jsonFileType"] == "generic")):
                        tmp.append(job["jobName"])
                    elif (job["InternalUse"]["jsonFileType"] == "starccm"):
                        tmp.append(os.path.basename(job["simFile"]))
                    else:
                        tmp.append("---")

                    tmp.append(job["InternalUse"]["jsonFileType"])

                    # include description 
                    if ("about" in job.keys()):
                        if (len(job["about"]) > 0):
                            if (len(job["about"]) > 30): # description too long
                                description = job["about"][0:30]
                                description = description + "..."
                            else: # description right size
                                description = job["about"]
                        else:  # description not present
                            description = "---"
                    else:  # description not present  
                        description = "---"

                    tmp.append(description)

                    # show status and run time:
                    if ("running" in job["InternalUse"]["status"]):
                        now = datetime.datetime.now()
                        deltaTime = now - self.start
                        hours, remainder = divmod(deltaTime.seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        deltaTime = '(dt: %d:%02d:%02d)' % (hours, minutes, seconds)
                        tmp.append("%s %s"%(job["InternalUse"]["status"], deltaTime))
                    else:
                        tmp.append(job["InternalUse"]["status"])

                    table.append(tmp[:])
                return tabulate(table, headers, tablefmt="rst", numalign="center", stralign = "center")

    def removeAbqLockFile(self, job):
        """Scans the directory for an Abaqus lock file (*.lck) and deletes if it exists"""
        if (job["InternalUse"]["jsonFileType"] == "abaqus"):
            lckFile = "%s%s"%(job["jobName"],".lck")
            clientWorkingDir = job["InternalUse"]["clientWorkingDir"]   
            lckFile = os.path.join(clientWorkingDir,lckFile)  
            if os.path.isfile(lckFile):
                os.remove(lckFile)



    def addJobToQueue(self, job):
        with self.jobListLock:

            # set job status:
            job["InternalUse"]["status"] = "queue"
            
            # set the id of the run for our
            self.jobID = self.jobID + 1
            self.serializeCounter()
            job["InternalUse"]["jobID"] =  self.jobID

            job["InternalUse"]["failsafe"] = False

            self.jobs.append(job)
            self.serializeJobList()  # serialize the self.jobs list

        threading.Thread(target=self.__runJob, args=(job,)).start()

    def __runJob(self, job):
        """Places a job in the queue and attempts to run it"""
        with self.CPULock:     # lock the CPU while we run the current job  
            if "killed" in job["InternalUse"]["status"]: # make sure we have not signalled to kill this job
                return   
            self.start = datetime.datetime.now() 
            with self.jobListLock:
                job["InternalUse"]["status"] = "running"

            jobID = job["InternalUse"]["jobID"]
            self.currentJobID = jobID   

            # get the user id, get environment vars, etc (source: http://stackoverflow.com/questions/1770209/run-child-processes-as-different-user-from-a-long-running-process/6037494#6037494):
            currentUserID = pwd.getpwnam(job["InternalUse"]["clientName"]).pw_uid 

            pw_record = pwd.getpwnam(job["InternalUse"]["clientName"])
            user_name      = pw_record.pw_name
            user_home_dir  = pw_record.pw_dir
            user_uid       = pw_record.pw_uid
            user_gid       = pw_record.pw_gid
            env = os.environ.copy()
            env[ 'HOME'     ]  = user_home_dir
            env[ 'LOGNAME'  ]  = user_name
            env[ 'PWD'      ]  = job["InternalUse"]["clientWorkingDir"] 
            env[ 'USER'     ]  = user_name  

            cwd = job["InternalUse"]["clientWorkingDir"]

            def demote(user_uid, user_gid):
                """Function used to spawn as subprocess as a given user"""
                def result():
                    os.setgid(user_gid)
                    os.setuid(user_uid)
                    os.setsid()
                return result

            if (job["InternalUse"]["jsonFileType"] == "starccm"): # we are dealing with a star-ccm+ job

                # now run the job:
                simFile =   job["simFile"]
                clientName = job["InternalUse"]["clientName"]
                solver = job["solver"]

                clientWorkingDir = job["InternalUse"]["clientWorkingDir"]

                stdErrorFile = os.path.join(clientWorkingDir,"error.log")
                stdOutFile   = os.path.join(clientWorkingDir, "out.log")

                if solver.lower().strip() == "default":
                    solver = self.serverConf["solverPaths"]["starccm"]

                # create the command list:
                cmd = []
                cmd.append(solver)
                # now add the remaining flags:
                for key in job["solverFlags"].keys():
                    if job["solverFlags"][key] is None: # flag takes no values (like the 'interactive' arg)
                        cmd.append(key)
                    else:
                        cmd.append(key)
                        cmd.append(str(job["solverFlags"][key]))
   

                cmd.append(simFile) 
                logging.info("Command issued: %s"%(" ".join(cmd)))

                with open(stdOutFile,"a+") as out, open(stdErrorFile,"a+") as err:
                    os.chown(stdOutFile, currentUserID, -1)
                    os.chown(stdErrorFile, currentUserID, -1)                    
                    try:
                        self.currentSubProcess = subprocess.Popen(cmd,stdout=out,stderr=err, preexec_fn=demote(user_uid, user_gid), cwd=cwd, env=env) # using wait so the program does not move forward
                        self.currentSubProcess.wait() 
                        self.currentSubProcess = None
                        logging.info("Done running starccm: %s (user: %s, jobID: %i)"%(simFile, clientName, jobID))

                    except Exception as e:
                        cmd = " ".join(cmd)
                        err.write("Error: Something wrong with the command line arguments.\n")
                        err.write(str(e) + "\n")
                        err.write("Error encountered while executing: %s \n"%(cmd))
                        err.write("\n")
                        logging.error("Error running starccm: %s (user: %s, jobID: %i)"%(simFile, clientName, jobID))
                        logging.error("Error encountered while executing: %s \n"%(cmd))

                # change file owernership:
                basename = ntpath.basename(job["simFile"])
                basename = basename.split(".")[0].strip()
                runDir = job["InternalUse"]["clientWorkingDir"]
                chownExt = [".sim",".sim~"] 
                self.changeFilesOwernship(currentUserID, runDir,
                 basename, chownExt)

                #email logic:
                if "sendEmailTo" in job["advanced"].keys():
                    # client wants to recieve email:
                    with open(stdOutFile,"r") as out:

                        # get server data:
                        SMTPServer = self.serverConf["emailServer"]["SMTPServer"]
                        SMTPPort   = self.serverConf["emailServer"]["SMTPPort"]
                        username   = self.serverConf["emailServer"]["username"]
                        password   = self.serverConf["emailServer"]["password"]
                        emailInfoEncrypted = self.serverConf["emailServer"]["emailInfoEncrypted"]
                        useStarttls   = self.serverConf["emailServer"]["useStarttls"]

                        if emailInfoEncrypted:
                            SMTPServer = base64.b64decode(SMTPServer)
                            SMTPPort   = base64.b64decode(SMTPPort)
                            username   = base64.b64decode(username)
                            password   = base64.b64decode(password)


                        data  = out.readlines()
                        logFileLines = data[-100::]
                        message = []
                        message.append("Finished running: %s. \r\n The end of your out.log reads: \r\n\r\n"%(simFile))
                        for line in logFileLines:
                            message.append(line.strip() + "\r\n")

                        message = "".join(message)

                        recipient = job["advanced"]["sendEmailTo"]
                        subject = "JSS run complete..."
                        sendEmailMsg(message, subject, recipient, username, password, SMTPServer, SMTPPort, useStarttls,logging)

            elif (job["InternalUse"]["jsonFileType"] == "abaqus"):
 
                solver = job["solver"]
                clientName = job["InternalUse"]["clientName"]
                cpus = job["solverFlags"]["cpus"]
                gpus = job["solverFlags"]["gpus"]
                jobName = job["jobName"]
                jobDirectory =  job["InternalUse"]["jobDirectory"]
                clientWorkingDir = job["InternalUse"]["clientWorkingDir"]


                # change current working dir:
                os.chdir(jobDirectory)

                env['PWD']  = jobDirectory
                cwd = jobDirectory

                # log files
                stdErrorFile = os.path.join(clientWorkingDir,"error.log")
                stdOutFile   = os.path.join(clientWorkingDir, "out.log")

                # are we using the default solver?
                if solver.lower().strip() == "default":
                    solver = self.serverConf["solverPaths"]["abaqus"]

                # create the command list:
                cmd = []
                cmd.append(solver)
                cmd.append("job=%s"%(jobName))
                # now add the remaining flags:
                for key in job["solverFlags"].keys():
                    if job["solverFlags"][key] is None: # flag takes no values (like the 'interactive' arg)
                        cmd.append(key)
                    else:
                        cmd.append("%s=%s"%(key,job["solverFlags"][key]))

                # make sure a lock file is not present:
                self.removeAbqLockFile(job)

                # now run the job:

                with open(stdOutFile,"a+") as out, open(stdErrorFile,"a+") as err:
                    os.chown(stdOutFile, currentUserID, -1)
                    os.chown(stdErrorFile, currentUserID, -1)   
                    try:
                        self.currentSubProcess = subprocess.Popen(cmd,stdout=out,stderr=err, preexec_fn=demote(user_uid, user_gid), cwd=cwd, env=env)  # using wait so the program does not move forward
                        self.currentSubProcess.wait()
                        self.currentSubProcess = None
                        logging.info("Done running abaqus: %s (user: %s, jobID: %i)"%(jobName, clientName, jobID))


                    except Exception as e:
                        cmd = " ".join(cmd)
                        err.write("Error: Something wrong with the command line arguments.\n")
                        err.write(str(e) + "\n")
                        err.write("Error encountered while executing: %s \n"%(cmd))
                        err.write("\n")

                        logging.error("Error running abaqus: %s (user: %s, jobID: %i)"%(jobName, clientName, jobID))
                        logging.error("Error encountered while executing: %s \n"%(cmd))


                # change file owernership:
                basename = jobName
                runDir = job["InternalUse"]["clientWorkingDir"]
                chownExt = [".com",".sim",".sta",".msg",".dat",".odb",".prt"] 
                self.changeFilesOwernship(currentUserID, runDir,
                 basename, chownExt)

                if "sendEmailTo" in job["advanced"].keys():
                    # client wants to recieve email

                    message = None

                    # get the msg file contents:
                    with open("%s.msg"%(jobName),"r") as out:

                        # get server data:
                        SMTPServer = self.serverConf["emailServer"]["SMTPServer"]
                        SMTPPort   = self.serverConf["emailServer"]["SMTPPort"]
                        username   = self.serverConf["emailServer"]["username"]
                        password   = self.serverConf["emailServer"]["password"]
                        emailInfoEncrypted = self.serverConf["emailServer"]["emailInfoEncrypted"]
                        useStarttls   = self.serverConf["emailServer"]["useStarttls"]


                        if emailInfoEncrypted:
                            SMTPServer = base64.b64decode(SMTPServer)
                            SMTPPort   = base64.b64decode(SMTPPort)
                            username   = base64.b64decode(username)
                            password   = base64.b64decode(password)


                        data  = out.readlines()
                        logFileLines = data[-100::]
                        message = []
                        message.append("Finished running: %s.inp \r\n *The end of %s.msg reads: \r\n\r\n"%(jobName, jobName))
                        for line in logFileLines:
                            message.append(line.strip() + "\r\n")

                    # get the status file contents if the file exists:
                    if os.path.isfile("%s.sta"%(jobName)):
                        with open("%s.sta"%(jobName),"r") as sta:
                            data  = sta.readlines()
                            staFileLines = data[-100::]
                            message.append("\r\n *The end of %s.sta reads: \r\n\r\n"%(jobName))
                            for line in staFileLines:
                                message.append(line.strip() + "\r\n")

                    if message is not None:
                        message = "".join(message)
                        recipient = job["advanced"]["sendEmailTo"]
                        subject = "JSS run complete..."
                        sendEmailMsg(message, subject, recipient, username, password, SMTPServer, SMTPPort, useStarttls, logging)

            elif (job["InternalUse"]["jsonFileType"] == "generic"):

                solver = job["commands"]["excutable"]
                clientName = job["InternalUse"]["clientName"]
                jobName = job["jobName"]
                jobFile = job["InternalUse"]["jobFile"]
                jobDirectory =  job["InternalUse"]["jobDirectory"]

                clientWorkingDir = job["InternalUse"]["clientWorkingDir"]

                # change current working dir:
                os.chdir(jobDirectory)

                env[ 'PWD'      ]  = jobDirectory
                cwd = jobDirectory

                # log files
                stdErrorFile = os.path.join(clientWorkingDir,"error.log")
                stdOutFile   = os.path.join(clientWorkingDir, "out.log")

                                # create the command list:
                cmd = []
                if len(solver.strip()) != 0:
                    cmd.append(solver)
                cmd.append(jobFile)
                # now add the remaining postfix flags:
                for c in job["commands"]["executableArguments"]:
                    cmd.append(key)


                # now run the job:

                with open(stdOutFile,"a+") as out, open(stdErrorFile,"a+") as err:
                    os.chown(stdOutFile, currentUserID, -1)
                    os.chown(stdErrorFile, currentUserID, -1)   
                    try:
                        self.currentSubProcess = subprocess.Popen(cmd,stdout=out,stderr=err, preexec_fn=demote(user_uid, user_gid), cwd=cwd, env=env)  # using wait so the program does not move forward
                        self.currentSubProcess.wait()
                        self.currentSubProcess = None
                        logging.info("Done running generic: %s (user: %s, jobID: %i)"%(jobName, clientName, jobID))


                    except Exception as e:
                        cmd = " ".join(cmd)
                        err.write("Error: Something wrong with the command line arguments.\n")
                        err.write(str(e) + "\n")
                        err.write("Error encountered while executing: %s \n"%(cmd))
                        err.write("\n")

                        logging.error("Error running generic: %s (user: %s, jobID: %i)"%(jobName, clientName, jobID))
                        logging.error("Error encountered while executing: %s \n"%(cmd))



                #email logic:
                if "sendEmailTo" in job["advanced"].keys():
                    # client wants to recieve email:
                    with open(stdOutFile,"r") as out:

                        # get server data:
                        SMTPServer = self.serverConf["emailServer"]["SMTPServer"]
                        SMTPPort   = self.serverConf["emailServer"]["SMTPPort"]
                        username   = self.serverConf["emailServer"]["username"]
                        password   = self.serverConf["emailServer"]["password"]
                        emailInfoEncrypted = self.serverConf["emailServer"]["emailInfoEncrypted"]
                        useStarttls   = self.serverConf["emailServer"]["useStarttls"]

                        if emailInfoEncrypted:
                            SMTPServer = base64.b64decode(SMTPServer)
                            SMTPPort   = base64.b64decode(SMTPPort)
                            username   = base64.b64decode(username)
                            password   = base64.b64decode(password)


                        data  = out.readlines()
                        logFileLines = data[-100::]
                        message = []
                        message.append("Finished running: %s. \r\n The end of your out.log reads: \r\n\r\n"%(simFile))
                        for line in logFileLines:
                            message.append(line.strip() + "\r\n")

                        message = "".join(message)

                        recipient = job["advanced"]["sendEmailTo"]
                        subject = "JSS run complete..."
                        sendEmailMsg(message, subject, recipient, username, password, SMTPServer, SMTPPort, useStarttls,logging)


        self.currentJobID = None      
        self.currentSubProcess = None

        with self.jobListLock:
            job["InternalUse"]["status"] = "complete"
            if job in self.jobs: # we have to check as the job could have been killed!
                indexToRemove = self.jobs.index(job)
                removedItem = self.jobs.pop(indexToRemove)
                removedItem["InternalUse"]["failsafe"] = False
                self.serializeJobList()  # serialize the self.jobs list
                with self.jobsCompletedListLock:
                    self.jobsCompleted.append(removedItem)

            self.start = datetime.datetime.now()  # reset stop-watch
            self.currentlyRunning = False

    def shakeHands(self, clientName, clientMachine):
        """Function used to test if the client can connect to the server"""
        logging.info("Shook hands with client %s@%s"%(clientName,clientMachine))
        return True

    def jobDispatcher(self, jData):
        """
            Method used by all clients to submit and validate their JSON job input files (note: method uses 'parsed' JSON dictionary)
             - jData - dictionary - contains all of the parsed data contained in the *.json file
        """

        self.loadServerConfFile()  # reload the configuration file before we submit

        if ("InternalUse" not in jData.keys()):
            logging.error("jobDispatcher call from %s@%s: 'InternalUse' block not present the passed %s file"%(jData["InternalUse"]["clientName"],
            jData["InternalUse"]["clientMachine"],jData["InternalUse"]["jsonFileName"]))           
            return 

        if ("jsonFileType" not in jData["InternalUse"].keys()):
            logging.error("jobDispatcher call from %s@%s: 'jsonFileType' entry not present the passed %s file"%(jData["InternalUse"]["clientName"],
            jData["InternalUse"]["clientMachine"],jData["InternalUse"]["jsonFileName"]))           
            return 


        logging.info("Dispatching jobs from %s@%s (%s)"%(jData["InternalUse"]["clientName"],
            jData["InternalUse"]["clientMachine"],jData["InternalUse"]["jsonFileName"]))


        # Add submission time:
        subTime = datetime.datetime.now().strftime("%B %d - %H:%M %p")
        jData["InternalUse"]["timeSubmitted"] = subTime

        # What type of simulation are we dealing? Starccm+, Abaqus, or ...?

        if ((jData["InternalUse"]["jsonFileType"] == "abaqus") or 
            (jData["InternalUse"]["jsonFileType"] == "generic")):
            for i,jobFile in enumerate(jData["jobFiles"]):
                #logging.debug("Ready to submit %s"%(jobName))

                # create a job dictionary that we can submit (we can only submit 1 job file at a time,
                # as it gives us the flexibility killing certain runs from our list of jobs in the future
                singleJob = copy.deepcopy(jData)
                singleJob.pop("jobFiles", None)
                singleJob["jobName"] = os.path.splitext(os.path.basename(jobFile))[0]
                singleJob["InternalUse"]["jobFile"] = jobFile
                singleJob["InternalUse"]["jobDirectory"] = os.path.dirname(jobFile)

                self.addJobToQueue(singleJob)  


        elif (jData["InternalUse"]["jsonFileType"] == "starccm"):
            for simFile in jData["simFiles"]:
                #logging.debug("Ready to submit %s"%(simFile))

                singleJob = copy.deepcopy(jData)
                singleJob.pop("simFiles", None)
                singleJob["simFile"] = simFile

                self.addJobToQueue(singleJob) 
    

        else:
           logging.error("I don't know how to submit this type of job: %s. Called from %s@%s using %s file"%(jData["InternalUse"]["jsonFileType"] ,
            jData["InternalUse"]["clientName"],jData["InternalUse"]["clientMachine"] ,jData["InternalUse"]["jsonFileName"] )) 
           return   

    def changeFilesOwernship(self, newOwnerID, directory, basename, extensions):
        """
            Changes the owership for all files in the provided directory; 
            the filename is given as base name (e.g. 'test'), and with the 
            provided file extensions list (e.g., extensions = [".sim", ".sim~"]).
            newOwnerID is an integer defining the ID for the user which will
            gain owership of the provided files
        """  
        
        for ext in extensions:
            f = os.path.join(directory, basename + ext)
            if (os.path.isfile(f)):
                try:
                    os.chown(f, newOwnerID, -1)
                except:
                    pass

    def killJob(self, jobID, username):
        """
            Kill a job with ID equal to jobID. The
            only people that that have permission to kill it are:
                -job owner (i.e., the person that submitted the job)
                -root or sudo user
        """  

        with self.jobListLock:
            for job in self.jobs:
                if (job["InternalUse"]["jobID"] == jobID):
                    if ((username == job["InternalUse"]["clientName"]) or
                        username == "root"):

                        # remove from list:
                        job["InternalUse"]["status"] = "killed by %s"%(username)
                        indexToRemove = self.jobs.index(job)
                        removedItem = self.jobs.pop(indexToRemove)
                        removedItem["InternalUse"]["failsafe"] = False
                        self.serializeJobList()  # serialize the self.jobs list
                        with self.jobsCompletedListLock:
                            self.jobsCompleted.append(removedItem)
                        msg = "Job %i killed."%(jobID)

                        # are we currently running this job? If so, kill it!
                        if (jobID == self.currentJobID):  
                            if (self.currentSubProcess is not None):
                                os.killpg(self.currentSubProcess.pid, signal.SIGTERM)

                        logging.info("Job %i killed by %s"%(jobID,username))

                        return msg
                    else:
                        msg = "Error:\tPermission denied. Unable to kill Job %i."%(jobID)
                        logging.error("Permission denied: %s tried to kill a job (Job ID = %i) owned by %s"%(username,jobID, job["InternalUse"]["clientName"]))
                        return msg

            
        msg = "Error:\tInvalid job number."
        logging.error("Invalid job number: %s tried to kill Job %i"%(username,jobID))
        return msg
         
    def loadServerConfFile(self):
        """Load the server configuration file"""
        with self.confFileLock:
            self.serverConf = parseJSONFile(os.path.join(self.serverScriptDirectory,r"conf","serverConf.json"))

    def nameServerInfo(self):
        """Returns a dictionary with the name server info if it is available"""

        ns = {}
        ns["NS_HOST"]  = self.serverConf["nameServer"]["nameServerIP"]
        ns["NS_PORT"]  = self.serverConf["nameServer"]["nameServerPort"]
        return ns



def main():
    jssServer = JSSServer()
    try:  # if we are connected to the network, use netork ip
        myIP = [(s.connect(('8.8.8.8', 80)), s.getsockname()[0], s.close()) for s in [socket.socket(socket.AF_INET, socket.SOCK_DGRAM)]][0][1]
        daemon = Pyro4.Daemon(host=myIP, port=jssServer.serverConf["usePortNumber"])
    except:  # use localhost
        daemon = Pyro4.Daemon(port=jssServer.serverConf["usePortNumber"])
            
    jss_uri = daemon.register(jssServer)
    # serialize the uri so the client can load the uri directly,
    # rather than querying the name server:

    dummyLockFile = open("/opt/JSS/server/jss_uri.p.lock","w")  # jss client will not read this file while jss_uri.p.lock is present
    dummyLockFile.write(" ")
    pickle.dump(jss_uri, open("/opt/JSS/server/jss_uri.p","wb"))
    dummyLockFile.close()
    os.remove("/opt/JSS/server/jss_uri.p.lock")

    jssServer.connectToNameServer(jss_uri)

    print("Running...")
    daemon.requestLoop()

if __name__=="__main__":
    main()
