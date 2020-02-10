# Futures
from __future__ import absolute_import
from __future__ import print_function

# Standard Libraries
import sys
import os
import platform
import getpass
import subprocess
import threading
import socket
import time
import datetime
import multiprocessing
import logging
import copy
from subprocess import CalledProcessError, check_output

# 3rd Party Packages
import Pyro4 # https://pypi.org/project/Pyro4/
import serpent # https://pypi.org/project/serpent/1.28/
from psutil import virtual_memory # https://pypi.org/project/psutil/

# Local Source Packages
from utils.parseJSONFile import parseJSONFile

class jobTesting(object):
	def __init__(self):

		self.jobID = 5734

		self.serverScriptDirectory = os.path.dirname(os.path.realpath(__file__))

		self.opSystem = platform.system()

		self.jobListLock = threading.Lock()
		self.CPULock = threading.Lock()

		self.serializeJobListLock = threading.Lock()
		self.loadSerializedJobList()

	def loadSerializedJobList(self):
		jobListPath = os.path.join(self.serverScriptDirectory,"jobList.serpent")
		with self.serializeJobListLock:
			if os.path.isfile(jobListPath):
				self.jobs = serpent.load(open(jobListPath,"rb"))
			else:
				self.jobs = []

	def serializeJobList(self):
		jobListPath = os.path.join(self.serverScriptDirectory,"jobList.serpent")
		with self.serializeJobListLock:
			try:
				serpent.dump(self.jobs, open(jobListPath,"wb"))
			except:
				# logging.error("unable to serializeJobList")
				print("unable to serializeJobList")

	## jobDefinition Method
	# Gathers all necessary information for job submission
	def jobDefinition(self):
		jsonFile = os.path.join(self.serverScriptDirectory,str(self.jobID),"abaqusSubmit.json") # \TODO make proper run directory
		jobData = parseJSONFile(jsonFile)

		# update job status
		jobData["InternalUse"]["status"] = "loaded"
		logging.info("Job {0} submission JSON loaded".format(self.jobID))

		subTime = datetime.datetime.now().strftime("%B %d - %H:%M %p")
		jobData["InternalUse"]["submissionTime"] = subTime

		# Separate all job files and create indivual dictionaries for each
		for i,jobFile in enumerate(jobData["jobFiles"]):
			singleJob = copy.deepcopy(jobData)
			singleJob.pop("jobFiles",None)
			singleJob["jobName"] = os.path.splitext(os.path.basename(jobFile))[0]
			singleJob["InternalUse"]["singleJobID"] = str(self.jobID)+":"+singleJob["jobName"]
			singleJob["InternalUse"]["jobFile"] = os.path.join(self.serverScriptDirectory,str(self.jobID),singleJob["jobName"]+".inp") # \TODO proper directory

			logging.info("created job {0} from submission {1}".format(singleJob["InternalUse"]["singleJobID"],self.jobID))

			self.addJobToQueue(singleJob)



	## addJobToQueue Method
	# adds jobs from job list into queue
	# calls _runJob from created queue
	def addJobToQueue(self, job):
		with self.jobListLock:

			# set job status
			job["InternalUse"]["status"] = "queue"
			logging.info("Job {0} added to queue".format(self.jobID))

			self.jobs.append(job)
			self.serializeJobList()

		threading.Thread(target=self.__runJob, args=(job, )).start()

	## __runJob Private Method
	# submits each job individually
	def __runJob(self, job):
		with self.CPULock:
			# preliminary job submission stuff	
			if "killed" in job["InternalUse"]["status"]: # check if job has been killed
				return
			self.start = datetime.datetime.now() # start a clock
			with self.jobListLock: # update job status
				job["InternalUse"]["status"] = "running"
			jobDirectory = os.path.join(self.serverScriptDirectory,str(self.jobID)) # change working directory \TODO change to ID directory
			os.chdir(jobDirectory)
			cwd = jobDirectory

			# create log files
			stdErrorFile = os.path.join(jobDirectory, "error.log")
			stdOutFile = os.path.join(jobDirectory, "out.log")

			# gather job information
			clientName = job["InternalUse"]["clientName"]
			cpus = job["solverFlags"]["cpus"]
			gpus = job["solverFlags"]["gpus"]
			jobName = job["jobName"]
			singleJobID = job["InternalUse"]["singleJobID"]
			solver = job["InternalUse"]["jsonFileType"]

			# compile command line options
			cmd = []
			cmd.append(solver)
			cmd.append("job={0}".format(jobName))
			for key in job["solverFlags"].keys():
				if job["solverFlags"][key] is None:
					cmd.append(key)
				else:
					cmd.append("{0}={1}".format(key,job["solverFlags"][key]))

			if self.opSystem == "Linux":
				import pwd
				# define user id, environment variables, etc.
				currentUserID = pwd.getpwnam(getpass.getuser()).pw_uid 
				pw_record = pwd.getpwnam(getpass.getuser())
				user_name      = pw_record.pw_name
				user_home_dir  = pw_record.pw_dir
				user_uid       = pw_record.pw_uid
				user_gid       = pw_record.pw_gid
				env = os.environ.copy()
				env[ 'HOME'     ]  = user_home_dir
				env[ 'LOGNAME'  ]  = user_name
				env[ 'PWD'      ]  = jobDirectory
				env[ 'USER'     ]  = user_name

				# spawn subprocess as a given user
				def demote(user_uid, user_gid):
					def result():
						os.setgid(user_gid)
						os.setuid(user_uid)
						os.setsid()
					return result

				# Run the job
				with open(stdOutFile,"a+") as out, open(stdErrorFile,"a+") as err:
					os.chown(stdOutFile, currentUserID, -1)
					os.chown(stdErrorFile, currentUserID, -1)
					try:
						print(cmd)
						self.currentSubProcess = subprocess.Popen(cmd, stdout=out, stderr=err, preexec_fn=demote(user_uid,user_gid), cwd=cwd, env=env)
						self.currentSubProcess.wait()
						self.currentSubProcess = None
						logging.info("Job {0} has completed".format(singleJobID))
					except Exception as e:
						cmd = " ".join(cmd)
						err.write("*** ERROR: command line error\n")
						err.write(str(e)+"\n")
						err.write("Error encountered while executing: {0} \n".format(cmd))
						err.write("\n")

						logging.error("Error running Abaqus: {0}".format(singleJobID))
						logging.error("Error encountered while executing: {0} \n".format(cmd))

			elif self.opSystem == "Windows":
				with open(stdOutFile,"a+") as out, open(stdErrorFile,"a+") as err:
					try:
						cmd[0] = "C:\\SIMULIA\\Commands\\abaqus.bat"
						self.currentSubProcess = subprocess.Popen(cmd, stdout=out, stderr=err, cwd=cwd)
						self.currentSubProcess.wait()
						logging.info("Job {0} has completed".format(singleJobID))					
						self.currentSubProcess = None
					except:
						cmd = " ".join(cmd)
						err.write("*** ERROR: command line error\n")
						err.write(str(e)+"\n")
						err.write("Error encountered while executing: {0} \n".format(cmd))
						err.write("\n")

						logging.error("Error running Abaqus: {0}".format(singleJobID))
						logging.error("Error encountered while executing: {0} \n".format(cmd))


def main():
	jobTesties = jobTesting()
	jobTesties.jobDefinition()

if __name__ == '__main__':
	main()
