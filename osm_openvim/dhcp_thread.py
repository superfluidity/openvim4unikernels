# -*- coding: utf-8 -*-

##
# Copyright 2015 Telefónica Investigación y Desarrollo, S.A.U.
# This file is part of openvim
# All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# For those usages not covered by the Apache License, Version 2.0 please
# contact with: nfvlabs@tid.es
##

'''
This is thread that interact with the dhcp server to get the IP addresses 
'''
__author__="Pablo Montes, Alfonso Tierno"
__date__ ="$4-Jan-2016 12:07:15$"



import threading
import time
import Queue
import paramiko
import random
import subprocess
import logging

#TODO: insert a logging system

class dhcp_thread(threading.Thread):
    def __init__(self, dhcp_params, db, db_lock, test, dhcp_nets, logger_name=None, debug=None):
        '''Init a thread.
        Arguments: thread_info must be a dictionary with:
            'dhcp_params' dhcp server parameters with the following keys:
                mandatory : user, host, port, key, ifaces(interface name list of the one managed by the dhcp)
                optional:  password, key, port(22)
            'db' 'db_lock': database class and lock for accessing it
            'test': in test mode no acces to a server is done, and ip is invented
        '''
        threading.Thread.__init__(self)
        self.dhcp_params = dhcp_params
        self.db = db
        self.db_lock = db_lock
        self.test = test
        self.dhcp_nets = dhcp_nets
        self.ssh_conn = None
        if logger_name:
            self.logger_name = logger_name
        else:
            self.logger_name = "openvim.dhcp"
        self.logger = logging.getLogger(self.logger_name)
        if debug:
            self.logger.setLevel(getattr(logging, debug))

        self.mac_status ={} #dictionary of mac_address to retrieve information
            #ip: None
            #retries: 
            #next_reading: time for the next trying to check ACTIVE status or IP
            #created: time when it was added 
            #active: time when the VM becomes into ACTIVE status
            
        
        self.queueLock = threading.Lock()
        self.taskQueue = Queue.Queue(2000)
        
    def ssh_connect(self):
        try:
            #Connect SSH
            self.ssh_conn = paramiko.SSHClient()
            self.ssh_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_conn.load_system_host_keys()
            self.ssh_conn.connect(self.dhcp_params["host"], port=self.dhcp_params.get("port", 22),
                                  username=self.dhcp_params["user"], password=self.dhcp_params.get("password"),
                                  key_filename=self.dhcp_params.get("keyfile"), timeout=2)
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("ssh_connect ssh Exception " + str(e))
        
    def load_mac_from_db(self):
        #TODO get macs to follow from the database
        self.logger.debug("load macs from db")
        self.db_lock.acquire()
        r,c = self.db.get_table(SELECT=('mac','ip_address','nets.uuid as net_id', ),
                                FROM='ports join nets on ports.net_id=nets.uuid', 
                                WHERE_NOT={'ports.instance_id': None, 'nets.provider': None})
        self.db_lock.release()
        now = time.time()
        self.mac_status ={}
        if r<0:
            self.logger.error("Error getting data from database: " + c)
            return
        for port in c:
            if port["net_id"] in self.dhcp_nets:
                self.mac_status[ port["mac"] ] = {"ip": port["ip_address"], "next_reading": now, "created": now, "retries":0}
    
    def insert_task(self, task, *aditional):
        try:
            self.queueLock.acquire()
            task = self.taskQueue.put( (task,) + aditional, timeout=5) 
            self.queueLock.release()
            return 1, None
        except Queue.Full:
            return -1, "timeout inserting a task over dhcp_thread"

    def run(self):
        self.logger.debug("starting, nets: " + str(self.dhcp_nets))
        next_iteration = time.time() + 10
        while True:
            self.load_mac_from_db()
            while True:
                try:
                    self.queueLock.acquire()
                    if not self.taskQueue.empty():
                        task = self.taskQueue.get()
                    else:
                        task = None
                    self.queueLock.release()

                    if task is None:
                        now=time.time()
                        if now >= next_iteration:
                            next_iteration = self.get_ip_from_dhcp()
                        else:
                            time.sleep(1)
                        continue

                    if task[0] == 'add':
                        self.logger.debug("processing task add mac " + str(task[1]))
                        now=time.time()
                        self.mac_status[task[1] ] = {"ip": None, "next_reading": now, "created": now, "retries":0}
                        next_iteration = now
                    elif task[0] == 'del':
                        self.logger.debug("processing task del mac " + str(task[1]))
                        if task[1] in self.mac_status:
                            del self.mac_status[task[1] ]
                    elif task[0] == 'exit':
                        self.logger.debug("processing task exit")
                        self.terminate()
                        return 0
                    else:
                        self.logger.error("unknown task: " + str(task))
                except Exception as e:
                    self.logger.critical("Unexpected exception at run: " + str(e), exc_info=True)
          
    def terminate(self):
        try:
            if self.ssh_conn:
                self.ssh_conn.close()
        except Exception as e:
            self.logger.error("terminate Exception: " + str(e))
        self.logger.debug("exit from dhcp_thread")

    def get_ip_from_dhcp(self):
        
        now = time.time()
        next_iteration= now + 40000 # >10 hores
        
        #print self.name, "Iteration" 
        for mac_address in self.mac_status:
            if now < self.mac_status[mac_address]["next_reading"]:
                if self.mac_status[mac_address]["next_reading"] < next_iteration:
                    next_iteration = self.mac_status[mac_address]["next_reading"]
                continue
            
            if self.mac_status[mac_address].get("active") == None:
                #check from db if already active
                self.db_lock.acquire()
                r,c = self.db.get_table(FROM="ports as p join instances as i on p.instance_id=i.uuid",
                                        WHERE={"p.mac": mac_address, "i.status": "ACTIVE"})
                self.db_lock.release()
                if r>0:
                    self.mac_status[mac_address]["active"] = now
                    self.mac_status[mac_address]["next_reading"] = (int(now)/2 +1)* 2
                    self.logger.debug("mac %s VM ACTIVE", mac_address)
                    self.mac_status[mac_address]["retries"] = 0
                else:
                    #print self.name, "mac %s  VM INACTIVE" % (mac_address)
                    if now - self.mac_status[mac_address]["created"] > 300:
                        #modify Database to tell openmano that we can not get dhcp from the machine
                        if not self.mac_status[mac_address].get("ip"):
                            self.db_lock.acquire()
                            r,c = self.db.update_rows("ports", {"ip_address": "0.0.0.0"}, {"mac": mac_address})
                            self.db_lock.release()
                            self.mac_status[mac_address]["ip"] = "0.0.0.0"
                            self.logger.debug("mac %s >> set to 0.0.0.0 because of timeout", mac_address)
                        self.mac_status[mac_address]["next_reading"] = (int(now)/60 +1)* 60
                    else:
                        self.mac_status[mac_address]["next_reading"] = (int(now)/6 +1)* 6
                if self.mac_status[mac_address]["next_reading"] < next_iteration:
                    next_iteration = self.mac_status[mac_address]["next_reading"]
                continue
            

            if self.test:
                if self.mac_status[mac_address]["retries"]>random.randint(10,100): #wait between 10 and 100 seconds to produce a fake IP
                    content = self.get_fake_ip()
                else:
                    content = None
            elif self.dhcp_params["host"]=="localhost":
                try:
                    command = ['get_dhcp_lease.sh',  mac_address]
                    content = subprocess.check_output(command)
                except Exception as e:
                    self.logger.error("get_ip_from_dhcp subprocess Exception " + str(e))
                    content = None
            else:
                try:
                    if not self.ssh_conn:
                        self.ssh_connect()
                    command = 'get_dhcp_lease.sh ' +  mac_address
                    (_, stdout, _) = self.ssh_conn.exec_command(command)
                    content = stdout.read()
                except paramiko.ssh_exception.SSHException as e:
                    self.logger.error("get_ip_from_dhcp: ssh_Exception: " + str(e))
                    content = None
                    self.ssh_conn = None
                except Exception as e:
                    self.logger.error("get_ip_from_dhcp: Exception: " + str(e))
                    content = None
                    self.ssh_conn = None

            if content:
                self.mac_status[mac_address]["ip"] = content
                #modify Database
                self.db_lock.acquire()
                r,c = self.db.update_rows("ports", {"ip_address": content}, {"mac": mac_address})
                self.db_lock.release()
                if r<0:
                    self.logger.error("Database update error: " + c)
                else:
                    self.mac_status[mac_address]["retries"] = 0
                    self.mac_status[mac_address]["next_reading"] = (int(now)/3600 +1)* 36000 # 10 hores
                    if self.mac_status[mac_address]["next_reading"] < next_iteration:
                        next_iteration = self.mac_status[mac_address]["next_reading"]
                    self.logger.debug("mac %s >> %s", mac_address, content)
                    continue
            #a fail has happen
            self.mac_status[mac_address]["retries"] +=1
            #next iteration is every 2sec at the beginning; every 5sec after a minute, every 1min after a 5min
            if now - self.mac_status[mac_address]["active"] > 120:
                #modify Database to tell openmano that we can not get dhcp from the machine
                if not self.mac_status[mac_address].get("ip"):
                    self.db_lock.acquire()
                    r,c = self.db.update_rows("ports", {"ip_address": "0.0.0.0"}, {"mac": mac_address})
                    self.db_lock.release()
                    self.mac_status[mac_address]["ip"] = "0.0.0.0"
                    self.logger.debug("mac %s >> set to 0.0.0.0 because of timeout", mac_address)
            
            if now - self.mac_status[mac_address]["active"] > 60:
                self.mac_status[mac_address]["next_reading"] = (int(now)/6 +1)* 6
            elif now - self.mac_status[mac_address]["active"] > 300:
                self.mac_status[mac_address]["next_reading"] = (int(now)/60 +1)* 60
            else:
                self.mac_status[mac_address]["next_reading"] = (int(now)/2 +1)* 2
                
            if self.mac_status[mac_address]["next_reading"] < next_iteration:
                next_iteration = self.mac_status[mac_address]["next_reading"]
        return next_iteration    
    
    def get_fake_ip(self):
        fake_ip = "192.168.{}.{}".format(random.randint(1,254), random.randint(1,254) )
        while True:
            #check not already provided
            already_used = False
            for mac_address in self.mac_status:
                if self.mac_status[mac_address]["ip"] == fake_ip:
                    already_used = True
                    break
            if not already_used:
                return fake_ip


#EXAMPLE of bash script that must be available at the DHCP server for "isc-dhcp-server" type
#     $ cat ./get_dhcp_lease.sh
#     #!/bin/bash
#     awk '
#     ($1=="lease" && $3=="{"){ lease=$2; active="no"; found="no" }
#     ($1=="binding" && $2=="state" && $3=="active;"){ active="yes" }
#     ($1=="hardware" && $2=="ethernet" && $3==tolower("'$1';")){ found="yes" }
#     ($1=="client-hostname"){ name=$2 }
#     ($1=="}"){ if (active=="yes" && found=="yes"){ target_lease=lease; target_name=name}}
#     END{printf("%s", target_lease)} #print target_name
#     ' /var/lib/dhcp/dhcpd.leases

 
