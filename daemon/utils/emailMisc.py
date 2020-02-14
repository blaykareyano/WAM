from __future__ import print_function
import smtplib
import base64

## @package emailMisc
## @todo check compatibility post server scripting
## @brief 
# Sends an email message to the recipient email address using the sender's email address.

## Variable Definitions:  
# message: string - email message  
# subject: string - email subject  
# sender: string - email address of the sender  
# senderPassword: string - sender's password  
# smtpServer: string - email server address  
# smtpServerPort: int - email server port  
# useStarttls: bool - should we use starttls?  
# logging: instance of Python's builtin logging library
def sendEmailMsg(message, subject, recipient, sender, senderPassword, smtpServer, smtpServerPort, useStarttls, logging = None):

    try:
        if logging is not None:
            logging.info("sending an email to: {0}".format(recipient))

        body = "" + message + ""
        headers = ["From: "+sender, "Subject: "+subject, "To: "+recipient, "MIME-Version: 1.0", "Content-Type: text/plain"]
        headers = "\r\n".join(headers)

        session = smtplib.SMTP(smtpServer, int(smtpServerPort))
         
        session.ehlo()
        if (useStarttls):
            session.starttls()
            session.ehlo

        if (senderPassword.strip() != ""):
            session.login(sender, senderPassword)
        session.sendmail(sender, recipient, headers + "\r\n\r\n" + body)
        session.quit()

        if logging is not None:
            logging.info("done sending email to: {0}".format(recipient))
    
    except Exception as e:
        if logging is not None:
            logging.error(e)
        else:
            print(e)
