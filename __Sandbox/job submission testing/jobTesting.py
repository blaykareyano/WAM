# Futures
from __future__ import absolute_import
from __future__ import print_function

# Standard Libraries
import sys
import os
import threading
import socket
import time
import multiprocessing
import logging

# 3rd Party Packages
import Pyro4 # https://pypi.org/project/Pyro4/
import serpent # https://pypi.org/project/serpent/1.28/
from psutil import virtual_memory # https://pypi.org/project/psutil/

class jobTesting(object):
	def __init__(self):

		self.serverScriptDirectory = os.path.dirname(os.path.realpath(__file__))

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
				pass

	def addJobToQueue(self, job):
		with self.jobListLock:

			# set job status
			job["InternalUse"]["status"] = "queue"

			self.jobs.append(job)
			self.serializeJobList()

		threading.Thread(target=self.__runJob, args=(job,)).start()

	def __runJob(self, job):
		with self.CPULock:
			pass

		
def main():
	jobTesties = jobTesting()

if __name__ == '__main__':
	main()
