![yee](https://github.com/blaykareyano/WAM/blob/master/yeet.JPG "YEET") ![yee](https://github.com/blaykareyano/WAM/blob/master/yeet.JPG "YEET") ![yee](https://github.com/blaykareyano/WAM/blob/master/yeet.JPG "YEET") ![yee](https://github.com/blaykareyano/WAM/blob/master/yeet.JPG "YEET") ![yee](https://github.com/blaykareyano/WAM/blob/master/yeet.JPG "YEET") 
# Workload Allocation Manager

## Summary
WAM centralizes job submission queues for multiple independent computational machines. A host computer (WAM Server) manages the queue, distribution of work to remote computational machines, and license management.

## Components
### WAMserver.py
Only install onto control machine 

This script contains:
- Definition of command arguments
- Loading of server configuration files
- Collection of client machine information including core count, memory, and status
- Collection of license availability
- User interface for selections of client machine using gathered information
- User interface for job submission paramenters included cores, memory, time delay/schedule, license server, optional completion email
- Transfer of input files and output files to and from the server and client machines
- Monitor job status file during job (.msg, .dat, .sta, .log) 
- Managment of job queues on each client machine (counter.p, jobList.p)
- Job controls including kill and submit commands
- Email generation at end of job (optional)
- [Pyro4](https://pyro4.readthedocs.io/en/stable/index.html "Pyro4 Documentation") Daemon definition
- Initialization of [Pyro4](https://pyro4.readthedocs.io/en/stable/index.html "Pyro4 Documentation") name server (uri (universal resource identifier) serialization)

### WAMclient.py
Install onto all computational machines

This script contains:
- Monitoring of job to determine when calls to WAMserver scripts should be made
- Execution of post job clean-up script

### Pickle Files
- counter.p - keeps a counter going for job IDs
- WAM_uri.p - allows for client to load the uri (universal resource identifier) rather than querying the name server
---
