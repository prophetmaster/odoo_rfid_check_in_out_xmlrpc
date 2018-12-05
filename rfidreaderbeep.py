#!/usr/bin/env python
# -*- coding: utf8 -*-

from xmlrpclib import ServerProxy
import datetime
import sys
import RPi.GPIO as GPIO
import MFRC522 # Library found here : https://github.com/mxgxw/MFRC522-python
import signal
import time
import json


# Odoo configuration
dbname = "dbname"
user = "user@user.com"
password = "password"
port = "8069"
url = "http://yourserver.com"


beeperGpioPin = 11 # Gpio Pin# see : https://cdn.sparkfun.com/assets/learn_tutorials/4/2/4/header_pinout.jpg
shortBeep = 0.3
longBeep = 1


# Class to interact with Odoo
class Odoo():

    # configuration of your Odoo server
    def __init__(self):

        self.DATA = dbname # db name
        self.USER = user # email address
        self.PASS = password # password
        self.PORT = port # port
        self.URL  = url # base url
        self.URL_COMMON = "{}:{}/xmlrpc/2/common".format(
        self.URL, self.PORT)
        self.URL_OBJECT = "{}:{}/xmlrpc/2/object".format(
        self.URL, self.PORT)

    # Authentification function
    def authenticateOdoo(self):

        self.ODOO_COMMON = ServerProxy(self.URL_COMMON)
        self.ODOO_OBJECT = ServerProxy(self.URL_OBJECT)
        self.UID = self.ODOO_COMMON.authenticate(self.DATA, self.USER, self.PASS, {})

    # Search for employee in Odoo
    def employeeSearch(self, params):

        result = self.ODOO_OBJECT.execute_kw(self.DATA, self.UID, self.PASS, 'hr.employee', 'search_read', [[['barcode', '=', params]]], {'fields': ['id', 'barcode', 'name']})
        return result

    # Search for attendance entry in Odoo
    def attendanceSearch(self, params):

        result = self.ODOO_OBJECT.execute_kw(self.DATA, self.UID, self.PASS, 'hr.attendance', 'search_read', [[['employee_id', '=', params]]], {'fields': ['check_in', 'check_out', 'create_uid', 'department_id', 'display_name', 'id']})
        return result

    # Create attendance entry in Odoo
    def attendanceCreate(self, params):

        result = self.ODOO_OBJECT.execute_kw(self.DATA, self.UID, self.PASS, 'hr.attendance', 'create', params)
        return result

    # Update attendance entry in Odoo
    def attendanceWrite(self, params, elements):

        result = self.ODOO_OBJECT.execute_kw(self.DATA, self.UID, self.PASS, 'hr.attendance', 'write', [[params], elements])
        return result

#config output GPIO
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BOARD)
GPIO.setup(beeperGpioPin, GPIO.OUT)

GPIO.output(beeperGpioPin, GPIO.HIGH)
time.sleep(shortBeep)
GPIO.output(beeperGpioPin, GPIO.LOW)
time.sleep(shortBeep)
GPIO.output(beeperGpioPin, GPIO.HIGH)
time.sleep(shortBeep)
GPIO.output(beeperGpioPin, GPIO.LOW)
time.sleep(shortBeep)
GPIO.output(beeperGpioPin, GPIO.HIGH)
time.sleep(longBeep)
GPIO.output(beeperGpioPin, GPIO.LOW)



continue_reading = True
# the uid of the last recognized card
lastcarduid = None
# the time a card uid was last seen
lastcardtime = 0.0

# this long after a card has been noticed, it can be noticed again
# This works because the reader generates repeated notifications of the card
# as it is held agains the reader - faster than this interval.
# The timer is restarted every time the reader generates a uid.
# If you sometimes get repeated new card IDs when holding a card against the
# reader, increase this a little bit.
CARDTIMEOUT = 1.0

# Capture SIGINT for cleanup when the script is aborted
def end_read(signal,frame):
    global continue_reading
    continue_reading = False
    GPIO.cleanup()

# Hook the SIGINT
signal.signal(signal.SIGINT, end_read)

# Create an object of the class MFRC522
MIFAREReader = MFRC522.MFRC522()

# This loop keeps checking for chips. If one is near it will get the UID and authenticate
while continue_reading:
    # Scan for cards    
    (status,TagType) = MIFAREReader.MFRC522_Request(MIFAREReader.PICC_REQIDL)
        
    # Get the UID of the card
    (status,uid) = MIFAREReader.MFRC522_Anticoll()
    
    # If we have a good read of the UID, process it
    if status == MIFAREReader.MI_OK:

        #print "Card read UID: "+uid # debug
        newcard = False
        if lastcarduid:
            if lastcarduid != uid or (lastcardtime and time.clock() - lastcardtime >= CARDTIMEOUT):
                newcard = True
        else:
            newcard = True
        
        # when new card id read launch sequence
        if newcard:

            #beep
            GPIO.output(beeperGpioPin, GPIO.HIGH)
            time.sleep(shortBeep)
            GPIO.output(beeperGpioPin, GPIO.LOW)

            #convert to string the uid of the card
            carduid = ''.join(map(str, uid)) 
            # print info
            print('uid of the card : %s' % carduid) 
            
            # instance odoo class
            od = Odoo()
            # authenticate to odoo server
            od.authenticateOdoo()
            
            # retrieve employee info
            employee = od.employeeSearch(carduid)
            
            #print ('odoo user info\'s : %s ' % employee) # debug
            #print (json.dumps(employee,sort_keys=True, indent=4)) #debug

            employee = json.dumps(employee, indent=4)
            employee = json.loads(employee)

            #get attendance for the user on this day
            if len(employee) > 0:

                attendance = od.attendanceSearch(employee[0]['id'])

                #print (json.dumps(attendance,sort_keys=True, indent=4)) # debug
                #print (attendance) #debug
            
                id_employee = employee[0]['id']
            

                if len(attendance) > 0:
                    
                    if str(attendance[0]['check_out']) == "False":
                        #new checkout
                    
                        id = attendance[0]['id']
                        print ('%s check out at : %s' % (employee[0]['name'],time.strftime("%Y-%m-%d %H:%M:%S")))
                        #print (attendance[0]['check_out']) # debug 
                        
                        # send to odoo datetime for checkout
                        od.attendanceWrite(id, {"id":id, "check_out":time.strftime("%Y-%m-%d %H:%M:%S"), "employee_id":id_employee, })
                        
                        GPIO.output(beeperGpioPin, GPIO.HIGH)
                        time.sleep(shortBeep)
                        GPIO.output(beeperGpioPin, GPIO.LOW)
                    
                    else:
                        #new check in
                        print ('%s check in at : %s' % (employee[0]['name'],time.strftime("%Y-%m-%d %H:%M:%S")))
                        od.attendanceCreate([{"check_in":time.strftime("%Y-%m-%d %H:%M:%S")
                            , "employee_id":id_employee
                            , 
                            }])
                        GPIO.output(beeperGpioPin, GPIO.HIGH)
                        time.sleep(.1)
                        GPIO.output(beeperGpioPin, GPIO.LOW)
                else:
                    #new check in
                    print ('%s check in at : %s' % (employee[0]['name'],time.strftime("%Y-%m-%d %H:%M:%S")))
                    od.attendanceCreate([{"check_in":time.strftime("%Y-%m-%d %H:%M:%S")
                        , "employee_id":id_employee
                        , 
                        }])

                    #beep
                    GPIO.output(beeperGpioPin, GPIO.HIGH)
                    time.sleep(shortBeep)
                    GPIO.output(beeperGpioPin, GPIO.LOW)

        else:
            #print info on screen
            print ('no user for this badge id')
            
            #beep
            GPIO.output(beeperGpioPin, GPIO.HIGH)
            time.sleep(longBeep)
            GPIO.output(beeperGpioPin, GPIO.LOW)

        # remember the last card uid recognized
        lastcarduid = uid
        # remember when it was seen
        lastcardtime = time.clock()
