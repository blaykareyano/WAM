# WAM - Workload Allocation Manager

## Summary
WAM centralizes job submission queues for multiple independent computational machines. A host computer (WAM Server) manages the queue, distribution of work to remote computational machines, and license management.

## Components
### WAMserver.py
Only install onto control machine 

This script contains:
- Loading of server configuration files
- Collection of client machine information including core count, memory, and status
- Collection of license availability
- User interface for selections of client machine using gathered information
- User interface for job submission paramenters included cores, memory, time delay/schedule, license server, optional completion email
- Transfer of input files and output files to and from the server and client machines
- Monitor job status file during job (.msg, .dat, .sta, .log) 
- Managment of execution of clean up script
- Managment of job queues on each client machine (pickle files)
- Job controls including kill and submit commands
- Email generation at end of job (optional)
- [Pyro4](https://pyro4.readthedocs.io/en/stable/index.html "Pyro4 Documentation") Daemon definition
- Initialization of [Pyro4](https://pyro4.readthedocs.io/en/stable/index.html "Pyro4 Documentation") name server (uri (universal resource identifier) serialization)

### WAMclient.py
Install onto all computational machines

This script contains:
- Definition of command arguments
- Calls to the WAMserver script given arguments
- Monitoring of job to determine when calls to WAMserver script should be made

### Pickle Files
counter.p - keeps a counter going for job IDs
jobList.p - list of jobs in case restart due to critical failure
WAM_uri.p - allows for client to load the uri (universal resource identifier) rather than querying the name server