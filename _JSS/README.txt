

Ubuntu install instructions:

1-) Install pyro 4 and tabulate:  

    a-) sudo apt-get install python-setuptools

    b-) sudo easy_install pyro4

    c-) sudo easy_install pip

    d-) sudo pip install tabulate

2-) Move the JSS folder into the existing /opt/ folder:
    sudo mv JSS /opt/

3-) Setup the system-wide environment variables:

    a-) sudo nano /etc/bash.bashrc   and add the following 2 lines to the bottom of the file:
          
        export PYTHONPATH="/opt/JSS/:PYTHONPATH"   # add JSS modules to the python search path
        alias jss="python /opt/JSS/client/jss.py"  # create an alias to the JSS client 


    b-) For sudoers:

        b.1-) Add the following line to the /etc/sudoers file: 
            Defaults        env_keep+= "PYTHONPATH"                        (<----Don't forget to copy the Defaults string!)

        b.2-) To run jss with sudo, add the following line to your ~/.bashrc file:
            alias sudo='sudo '


4-) Test that the jss client works. You might have to open a new terminal. Just type "jss" and hit Enter on your terminal and you should see something like this:

    fletcher@ubuntu:~/bin/SublimeText2$ jss

    Error:  Missing flags

    JSS available flags:
        -h or -help to show this menu
        -abq  or -abaqus to scan for abaqus *.inp files
        - ...

    If this works, we're now ready to setup the JSS server. 

5-) Make the pyro4 name server automatically start on boot-up:
    NOTE: Only install this on bou-hpc-02. We should have 1 name server per network!
    a-) sudo cp /opt/JSS/installScripts/ubuntu/pyro4NamingServer /etc/init.d/
    b-) sudo chmod +x /etc/init.d/pyro4NamingServer
    c-) sudo /etc/init.d/pyro4NamingServer start
    d-) sudo update-rc.d pyro4NamingServer defaults 96 02  
    e-) open the name server port: sudo ufw allow 9999 

6-) Make the JSS server run on boot-up:
    a-) sudo cp /opt/JSS/installScripts/ubuntu/jssServer /etc/init.d/
    b-) sudo chmod +x /etc/init.d/jssServer
    c-) sudo /etc/init.d/jssServer start
    d-) sudo update-rc.d jssServer defaults 99 02  
    e-) open the JSS server port to allow incoming remote client connections: sudo ufw allow 9998 

7-) For using Star-CCM+ with jss:
    a-) Install starccm+ and rsh
        - For rsh install:
            * sudo apt-get install rsh-server
            * sudo apt-get install rsh-client
    b-) edit /etc/hosts.equiv and add the following text to the bottom of the file: localhost
    c-) create the .rhosts file in /root/ with the following text: localhost
    d-) create .flexlmrc file in /root/ with the following text: CDLMD_LICENSE_FILE=2500@dopey


Notes:
    * You can stop the jssServer service with: sudo /etc/init.d/jssServer stop
    * You can start the jssServer service with: sudo /etc/init.d/jssServer start
    * You can restart the jssServer service with: sudo /etc/init.d/jssServer restart
