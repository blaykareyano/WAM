
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


class serpentTest(object):
	def __init__(self):
		# define this directory
		self.serverScriptDirectory = os.path.dirname(os.path.realpath(__file__))

		# lock and load serialized objects
		self.jobIDLock = threading.Lock()
		self.loadSerializedJobID()


	## loadSerializedJobID Method
	# load the job ID counter or create serpent file if none exists
	def loadSerializedJobID(self):
		jobIDPath = os.path.join(self.serverScriptDirectory,"jobIDCounter.serpent")
		if os.path.isfile(jobIDPath):
			self.jobID = serpent.load(open(jobIDPath, "rb"))
			print("opened serpent file")
			print(self.jobID)
		else:
			self.jobID = 0
			serpent.dump(self.jobID, open(jobIDPath, "wb"))
			print("created serpent file")
			print(self.jobID)

	## serializeJobID Method
	# serialize the job ID counter using Serpent
	def serializeJobID(self):
		jobIDPath = os.path.join(self.serverScriptDirectory,"jobIDCounter.serpent")
		with self.jobIDLock:        
			try:
				serpent.dump(self.jobID, open(jobIDPath,"wb"))
				print("serialized job ID")
				print(self.jobID)
			except:
				# logging.error("Unable to serialize (i.e., pickle) counter")
				pass

	def createJobID(self):
		while self.jobID<50:
			self.jobID = self.jobID+1
			print(self.jobID)
			self.serializeJobID()

def main():
	testies = serpentTest()
	testies.createJobID()


if __name__=="__main__":
	main()