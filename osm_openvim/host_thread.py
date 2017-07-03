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
#
# Modifications Copyright (C) 2017 Paolo Lungaroni - CNIT
#
##

'''
This is thread that interact with the host and the libvirt to manage VM
One thread will be launched per host 
'''
__author__ = "Pablo Montes, Alfonso Tierno, Leonardo Mirabal"
__date__ = "$10-jul-2014 12:07:15$"

import json
import yaml
import threading
import time
import Queue
import paramiko
# import subprocess
# import libvirt
import imp
import random
import os
import logging
from jsonschema import validate as js_v, exceptions as js_e
from vim_schema import localinfo_schema, hostinfo_schema


class host_thread(threading.Thread):
    lvirt_module = None

    def __init__(self, name, host, user, db, db_lock, test, image_path, host_id, version, develop_mode,
                 develop_bridge_iface, task_queue_sleep_time, libvirt_conn_mode, unikernel_mode, 
                 password=None, keyfile = None, logger_name=None, debug=None): #CLICKOS MOD
        '''Init a thread.
        Arguments:
            'id' number of thead
            'name' name of thread
            'host','user':  host ip or name to manage and user
            'db', 'db_lock': database class and lock to use it in exclusion
        '''
        threading.Thread.__init__(self)
        self.name = name
        self.host = host
        self.user = user
        self.db = db
        self.db_lock = db_lock
        self.test = test
        self.password = password
        self.keyfile =  keyfile
        self.localinfo_dirty = False

        if not test and not host_thread.lvirt_module:
            try:
                module_info = imp.find_module("libvirt")
                host_thread.lvirt_module = imp.load_module("libvirt", *module_info)
            except (IOError, ImportError) as e:
                raise ImportError("Cannot import python-libvirt. Openvim not properly installed" +str(e))
        if logger_name:
            self.logger_name = logger_name
        else:
            self.logger_name = "openvim.host."+name
        self.logger = logging.getLogger(self.logger_name)
        if debug:
            self.logger.setLevel(getattr(logging, debug))


        self.develop_mode = develop_mode
        self.develop_bridge_iface = develop_bridge_iface
        self.unikernel_mode = unikernel_mode        #CLICKOS MOD
        self.image_path = image_path
        self.host_id = host_id
        self.version = version
        
        self.xml_level = 0
        #self.pending ={}
        
        self.server_status = {} #dictionary with pairs server_uuid:server_status 
        self.pending_terminate_server =[] #list  with pairs (time,server_uuid) time to send a terminate for a server being destroyed
        self.next_update_server_status = 0 #time when must be check servers status

        self.hypervisor = "kvm" #hypervisor flag: for switch from kvm to xen #CLICKOS MOD
        
        self.hostinfo = None 
        
        self.queueLock = threading.Lock()
        self.taskQueue = Queue.Queue(2000)
        self.taskQueue_sleepTime = task_queue_sleep_time  #CLICKOS MOD
        self.libvirt_connMode = libvirt_conn_mode         #CLICKOS MOD
        self.ssh_conn = None

        if self.unikernel_mode:              #CLICKOS MOD
            if self.libvirt_connMode == "tcp":         #CLICKOS MOD
                self.lvirt_conn_uri = "xen+tcp://{host}/".format(host=self.host) #CLICKOS MOD
            else:     #CLICKOS MOD
                self.lvirt_conn_uri = "xen+ssh://{user}@{host}/".format(user=self.user, host=self.host) #CLICKOS MOD
        else:         #CLICKOS MOD
            self.lvirt_conn_uri = "qemu+ssh://{user}@{host}/system?no_tty=1&no_verify=1".format(
                user=self.user, host=self.host)

        if keyfile:
            self.lvirt_conn_uri += "&keyfile=" + keyfile

    def ssh_connect(self):
        try:
            # Connect SSH
            self.ssh_conn = paramiko.SSHClient()
            self.ssh_conn.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_conn.load_system_host_keys()
            self.ssh_conn.connect(self.host, username=self.user, password=self.password, key_filename=self.keyfile,
                                  timeout=10) #, None)
        except paramiko.ssh_exception.SSHException as e:
            text = e.args[0]
            self.logger.error("ssh_connect ssh Exception: " + text)

    def load_localinfo(self):
        if not self.test:
            try:
                # Connect SSH
                self.ssh_connect()

                command = 'mkdir -p ' +  self.image_path
                # print self.name, ': command:', command
                (_, stdout, stderr) = self.ssh_conn.exec_command(command)
                content = stderr.read()
                if len(content) > 0:
                    self.logger.error("command: '%s' stderr: '%s'", command, content)

                command = 'cat ' +  self.image_path + '/.openvim.yaml'
                # print self.name, ': command:', command
                (_, stdout, stderr) = self.ssh_conn.exec_command(command)
                content = stdout.read()
                if len(content) == 0:
                    self.logger.error("command: '%s' stderr='%s'", command, stderr.read())
                    raise paramiko.ssh_exception.SSHException("Error empty file, command: '{}'".format(command))
                self.localinfo = yaml.load(content)
                js_v(self.localinfo, localinfo_schema)
                self.localinfo_dirty = False
                if 'server_files' not in self.localinfo:
                    self.localinfo['server_files'] = {}
                self.logger.debug("localinfo load from host")
                return

            except paramiko.ssh_exception.SSHException as e:
                text = e.args[0]
                self.logger.error("load_localinfo ssh Exception: " + text)
            except host_thread.lvirt_module.libvirtError as e:
                text = e.get_error_message()
                self.logger.error("load_localinfo libvirt Exception: " + text)
            except yaml.YAMLError as exc:
                text = ""
                if hasattr(exc, 'problem_mark'):
                    mark = exc.problem_mark
                    text = " at position: (%s:%s)" % (mark.line+1, mark.column+1)
                self.logger.error("load_localinfo yaml format Exception " + text)
            except js_e.ValidationError as e:
                text = ""
                if len(e.path)>0: text=" at '" + ":".join(map(str, e.path))+"'"
                self.logger.error("load_localinfo format Exception: %s %s", text, str(e))
            except Exception as e:
                text = str(e)
                self.logger.error("load_localinfo Exception: " + text)
        
        #not loaded, insert a default data and force saving by activating dirty flag
        self.localinfo = {'files':{}, 'server_files':{} } 
        #self.localinfo_dirty=True
        self.localinfo_dirty=False

    def load_hostinfo(self):
        if self.test:
            return;
        try:
            #Connect SSH
            self.ssh_connect()


            command = 'cat ' +  self.image_path + '/hostinfo.yaml'
            #print self.name, ': command:', command
            (_, stdout, stderr) = self.ssh_conn.exec_command(command)
            content = stdout.read()
            if len(content) == 0:
                self.logger.error("command: '%s' stderr: '%s'", command, stderr.read())
                raise paramiko.ssh_exception.SSHException("Error empty file ")
            self.hostinfo = yaml.load(content)
            js_v(self.hostinfo, hostinfo_schema)
            self.logger.debug("hostlinfo load from host " + str(self.hostinfo))
            return

        except paramiko.ssh_exception.SSHException as e:
            text = e.args[0]
            self.logger.error("load_hostinfo ssh Exception: " + text)
        except host_thread.lvirt_module.libvirtError as e:
            text = e.get_error_message()
            self.logger.error("load_hostinfo libvirt Exception: " + text)
        except yaml.YAMLError as exc:
            text = ""
            if hasattr(exc, 'problem_mark'):
                mark = exc.problem_mark
                text = " at position: (%s:%s)" % (mark.line+1, mark.column+1)
            self.logger.error("load_hostinfo yaml format Exception " + text)
        except js_e.ValidationError as e:
            text = ""
            if len(e.path)>0: text=" at '" + ":".join(map(str, e.path))+"'"
            self.logger.error("load_hostinfo format Exception: %s %s", text, e.message)
        except Exception as e:
            text = str(e)
            self.logger.error("load_hostinfo Exception: " + text)
        
        #not loaded, insert a default data 
        self.hostinfo = None 
        
    def save_localinfo(self, tries=3):
        if self.test:
            self.localinfo_dirty = False
            return
        
        while tries>=0:
            tries-=1
            
            try:
                command = 'cat > ' +  self.image_path + '/.openvim.yaml'
                self.logger.debug("command:" + command)
                (stdin, _, _) = self.ssh_conn.exec_command(command)
                yaml.safe_dump(self.localinfo, stdin, explicit_start=True, indent=4, default_flow_style=False, tags=False, encoding='utf-8', allow_unicode=True)
                self.localinfo_dirty = False
                break #while tries
    
            except paramiko.ssh_exception.SSHException as e:
                text = e.args[0]
                self.logger.error("save_localinfo ssh Exception: " + text)
                if "SSH session not active" in text:
                    self.ssh_connect()
            except host_thread.lvirt_module.libvirtError as e:
                text = e.get_error_message()
                self.logger.error("save_localinfo libvirt Exception: " + text)
            except yaml.YAMLError as exc:
                text = ""
                if hasattr(exc, 'problem_mark'):
                    mark = exc.problem_mark
                    text = " at position: (%s:%s)" % (mark.line+1, mark.column+1)
                self.logger.error("save_localinfo yaml format Exception " + text)
            except Exception as e:
                text = str(e)
                self.logger.error("save_localinfo Exception: " + text)

    def load_servers_from_db(self):
        self.db_lock.acquire()
        r,c = self.db.get_table(SELECT=('uuid','status', 'image_id'), FROM='instances', WHERE={'host_id': self.host_id})
        self.db_lock.release()

        self.server_status = {}
        if r<0:
            self.logger.error("Error getting data from database: " + c)
            return
        for server in c:
            self.server_status[ server['uuid'] ] = server['status']
            
            #convert from old version to new one
            if 'inc_files' in self.localinfo and server['uuid'] in self.localinfo['inc_files']:
                server_files_dict = {'source file': self.localinfo['inc_files'][ server['uuid'] ] [0],  'file format':'raw' }
                if server_files_dict['source file'][-5:] == 'qcow2':
                    server_files_dict['file format'] = 'qcow2'
                    
                self.localinfo['server_files'][ server['uuid'] ] = { server['image_id'] : server_files_dict }
        if 'inc_files' in self.localinfo:
            del self.localinfo['inc_files']
            self.localinfo_dirty = True
    
    def delete_unused_files(self):
        '''Compares self.localinfo['server_files'] content with real servers running self.server_status obtained from database
        Deletes unused entries at self.loacalinfo and the corresponding local files.
        The only reason for this mismatch is the manual deletion of instances (VM) at database
        ''' 
        if self.test:
            return
        for uuid,images in self.localinfo['server_files'].items():
            if uuid not in self.server_status:
                for localfile in images.values():
                    try:
                        if (self.hypervisor != "xen-unik"):   #CLICKOS MOD
                            self.logger.debug("deleting file '%s' of unused server '%s'", localfile['source file'], uuid)
                            self.delete_file(localfile['source file'])
                    except paramiko.ssh_exception.SSHException as e:
                        self.logger.error("Exception deleting file '%s': %s", localfile['source file'], str(e))
                del self.localinfo['server_files'][uuid]
                self.localinfo_dirty = True

    def delete_unsed_ovs_bridge(self):
        """
        Only for unikernel mode. search openvswitch networks
        without any port configured and remove them
        """
        # obtain data
        db_filter = {'provider': 'OVS', 'type': 'bridge_data'}
        result, content = self.db.get_table(FROM='nets', WHERE=db_filter, LIMIT=100)

        if result < 0:
            raise ovimException(str(content), -result)
        elif result == 0:
            return
            #raise ovimException("show_network network '%s' not found" % network_id, -result)
        else:
            for net in content:
                # get ports from DB
                result, ports = self.db.get_table(FROM='ports', SELECT=('uuid as port_id',),
                                                  WHERE={'net_id': net['uuid']}, LIMIT=100)
                if len(ports) == 0:
                    self.delete_ovs_bridge("ovim-" + net['name'])
   
    def insert_task(self, task, *aditional):
        try:
            self.queueLock.acquire()
            task = self.taskQueue.put( (task,) + aditional, timeout=5) 
            self.queueLock.release()
            return 1, None
        except Queue.Full:
            return -1, "timeout inserting a task over host " + self.name

    def run(self):
        while True:
            self.load_localinfo()
            self.load_hostinfo()
            self.load_servers_from_db()
            if not self.unikernel_mode:     #CLICKOS MOD
                self.delete_unused_files()
            if self.unikernel_mode:     #CLICKOS MOD
                self.delete_unsed_ovs_bridge()  #CLICKOS MOD
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
                        if self.localinfo_dirty:
                            self.save_localinfo()
                        elif self.next_update_server_status < now:
                            self.update_servers_status()
                            self.next_update_server_status = now + 5
                        elif len(self.pending_terminate_server)>0 and self.pending_terminate_server[0][0]<now:
                            self.server_forceoff()
                        else:
                            #time.sleep(1) #CLICKOS MOD
                            time.sleep(self.taskQueue_sleepTime/1000.0)   #CLICKOS MOD
                        continue

                    if task[0] == 'instance':
                        self.logger.debug("processing task instance " + str(task[1]['action']))
                        retry = 0
                        while retry < 2:
                            retry += 1
                            r = self.action_on_server(task[1], retry==2)
                            if r >= 0:
                                break
                    elif task[0] == 'image':
                        pass
                    elif task[0] == 'exit':
                        self.logger.debug("processing task exit")
                        self.terminate()
                        return 0
                    elif task[0] == 'reload':
                        self.logger.debug("processing task reload terminating and relaunching")
                        self.terminate()
                        break
                    elif task[0] == 'edit-iface':
                        self.logger.debug("processing task edit-iface port={}, old_net={}, new_net={}".format(
                                          task[1], task[2], task[3]))
                        self.edit_iface(task[1], task[2], task[3])
                    elif task[0] == 'restore-iface':
                        self.logger.debug("processing task restore-iface={} mac={}".format(task[1], task[2]))
                        self.restore_iface(task[1], task[2])
                    elif task[0] == 'new-ovsbridge':
                        self.logger.debug("Creating compute OVS bridge")
                        self.create_ovs_bridge()
                    elif task[0] == 'new-ovsbridgenet':  #CLICKOS MOD
                        print self.name, ": Creating compute OVS bridge network"  #CLICKOS MOD
                        self.create_ovs_bridge(task[1])  #CLICKOS MOD
                    elif task[0] == 'new-vxlan':
                        self.logger.debug("Creating vxlan tunnel='{}', remote ip='{}'".format(task[1], task[2]))
                        self.create_ovs_vxlan_tunnel(task[1], task[2])
                    elif task[0] == 'del-ovsbridge':
                        self.logger.debug("Deleting OVS bridge")
                        self.delete_ovs_bridge()
                    elif task[0] == 'del-ovsbridgenet':  #CLICKOS MOD
                        print self.name, ": Deleting OVS bridge network"  #CLICKOS MOD
                        self.delete_ovs_bridge(task[1])  #CLICKOS MOD
                    elif task[0] == 'del-vxlan':
                        self.logger.debug("Deleting vxlan {} tunnel".format(task[1]))
                        self.delete_ovs_vxlan_tunnel(task[1])
                    elif task[0] == 'create-ovs-bridge-port':
                        self.logger.debug("Adding port ovim-{} to OVS bridge".format(task[1]))
                        self.create_ovs_bridge_port(task[1])
                    elif task[0] == 'del-ovs-port':
                        self.logger.debug("Delete bridge attached to ovs port vlan {} net {}".format(task[1], task[2]))
                        self.delete_bridge_port_attached_to_ovs(task[1], task[2])
                    else:
                        self.logger.debug("unknown task " + str(task))

                except Exception as e:
                    self.logger.critical("Unexpected exception at run: " + str(e), exc_info=True)

    def server_forceoff(self, wait_until_finished=False):
        while len(self.pending_terminate_server)>0:
            now = time.time()
            if self.pending_terminate_server[0][0]>now:
                if wait_until_finished:
                    time.sleep(1)
                    continue
                else:
                    return
            req={'uuid':self.pending_terminate_server[0][1],
                'action':{'terminate':'force'},
                'status': None
            }
            self.action_on_server(req)
            self.pending_terminate_server.pop(0)
    
    def terminate(self):
        try:
            self.server_forceoff(True)
            if self.localinfo_dirty:
                self.save_localinfo()
            if not self.test:
                self.ssh_conn.close()
        except Exception as e:
            text = str(e)
            self.logger.error("terminate Exception: " + text)
        self.logger.debug("exit from host_thread")

    def get_local_iface_name(self, generic_name):
        if self.hostinfo != None and "iface_names" in self.hostinfo and generic_name in self.hostinfo["iface_names"]:
            return self.hostinfo["iface_names"][generic_name]
        return generic_name
        
    def create_xml_server(self, server, dev_list, server_metadata={}):
        """Function that implements the generation of the VM XML definition.
        Additional devices are in dev_list list
        The main disk is upon dev_list[0]"""
        
    #get if operating system is Windows        
        windows_os = False
        os_type = server_metadata.get('os_type', None)
        if os_type == None and 'metadata' in dev_list[0]:
            os_type = dev_list[0]['metadata'].get('os_type', None)
        if os_type != None and os_type.lower() == "windows":
            windows_os = True
    #get type of hard disk bus  
        bus_ide = True if windows_os else False   
        bus = server_metadata.get('bus', None)
        if bus == None and 'metadata' in dev_list[0]:
            bus = dev_list[0]['metadata'].get('bus', None)
        if bus != None:
            bus_ide = True if bus=='ide' else False
            
        self.xml_level = 0

        text = "<domain type='kvm'>"
    #get topology
        topo = server_metadata.get('topology', None)
        if topo == None and 'metadata' in dev_list[0]:
            topo = dev_list[0]['metadata'].get('topology', None)
    #name
        name = server.get('name', '')[:28] + "_" + server['uuid'][:28] #qemu impose a length  limit of 59 chars or not start. Using 58
        text += self.inc_tab() + "<name>" + name+ "</name>"
    #uuid
        text += self.tab() + "<uuid>" + server['uuid'] + "</uuid>" 
        
        numa={}
        if 'extended' in server and server['extended']!=None and 'numas' in server['extended']:
            numa = server['extended']['numas'][0]
    #memory
        use_huge = False
        memory = int(numa.get('memory',0))*1024*1024 #in KiB
        if memory==0:
            memory = int(server['ram'])*1024;
        else:
            if not self.develop_mode:
                use_huge = True
        if memory==0:
            return -1, 'No memory assigned to instance'
        memory = str(memory)
        text += self.tab() + "<memory unit='KiB'>" +memory+"</memory>" 
        text += self.tab() + "<currentMemory unit='KiB'>" +memory+ "</currentMemory>"
        if use_huge:
            text += self.tab()+'<memoryBacking>'+ \
                self.inc_tab() + '<hugepages/>'+ \
                self.dec_tab()+ '</memoryBacking>'

    #cpu
        use_cpu_pinning=False
        vcpus = int(server.get("vcpus",0))
        cpu_pinning = []
        if 'cores-source' in numa:
            use_cpu_pinning=True
            for index in range(0, len(numa['cores-source'])):
                cpu_pinning.append( [ numa['cores-id'][index], numa['cores-source'][index] ] )
                vcpus += 1
        if 'threads-source' in numa:
            use_cpu_pinning=True
            for index in range(0, len(numa['threads-source'])):
                cpu_pinning.append( [ numa['threads-id'][index], numa['threads-source'][index] ] )
                vcpus += 1
        if 'paired-threads-source' in numa:
            use_cpu_pinning=True
            for index in range(0, len(numa['paired-threads-source'])):
                cpu_pinning.append( [numa['paired-threads-id'][index][0], numa['paired-threads-source'][index][0] ] )
                cpu_pinning.append( [numa['paired-threads-id'][index][1], numa['paired-threads-source'][index][1] ] )
                vcpus += 2
        
        if use_cpu_pinning and not self.develop_mode:
            text += self.tab()+"<vcpu placement='static'>" +str(len(cpu_pinning)) +"</vcpu>" + \
                self.tab()+'<cputune>'
            self.xml_level += 1
            for i in range(0, len(cpu_pinning)):
                text += self.tab() + "<vcpupin vcpu='" +str(cpu_pinning[i][0])+ "' cpuset='" +str(cpu_pinning[i][1]) +"'/>"
            text += self.dec_tab()+'</cputune>'+ \
                self.tab() + '<numatune>' +\
                self.inc_tab() + "<memory mode='strict' nodeset='" +str(numa['source'])+ "'/>" +\
                self.dec_tab() + '</numatune>'
        else:
            if vcpus==0:
                return -1, "Instance without number of cpus"
            text += self.tab()+"<vcpu>" + str(vcpus)  + "</vcpu>"

    #boot
        boot_cdrom = False
        for dev in dev_list:
            if dev['type']=='cdrom' :
                boot_cdrom = True
                break
        text += self.tab()+ '<os>' + \
            self.inc_tab() + "<type arch='x86_64' machine='pc'>hvm</type>"
        if boot_cdrom:
            text +=  self.tab() + "<boot dev='cdrom'/>" 
        text +=  self.tab() + "<boot dev='hd'/>" + \
            self.dec_tab()+'</os>'
    #features
        text += self.tab()+'<features>'+\
            self.inc_tab()+'<acpi/>' +\
            self.tab()+'<apic/>' +\
            self.tab()+'<pae/>'+ \
            self.dec_tab() +'</features>'
        if topo == "oneSocket:hyperthreading":
            if vcpus % 2 != 0:
                return -1, 'Cannot expose hyperthreading with an odd number of vcpus'
            text += self.tab() + "<cpu mode='host-model'> <topology sockets='1' cores='%d' threads='2' /> </cpu>" % vcpus/2
        elif windows_os or topo == "oneSocket":
            text += self.tab() + "<cpu mode='host-model'> <topology sockets='1' cores='%d' threads='1' /> </cpu>" % vcpus
        else:
            text += self.tab() + "<cpu mode='host-model'></cpu>"
        text += self.tab() + "<clock offset='utc'/>" +\
            self.tab() + "<on_poweroff>preserve</on_poweroff>" + \
            self.tab() + "<on_reboot>restart</on_reboot>" + \
            self.tab() + "<on_crash>restart</on_crash>"
        text += self.tab() + "<devices>" + \
            self.inc_tab() + "<emulator>/usr/libexec/qemu-kvm</emulator>" + \
            self.tab() + "<serial type='pty'>" +\
            self.inc_tab() + "<target port='0'/>" + \
            self.dec_tab() + "</serial>" +\
            self.tab() + "<console type='pty'>" + \
            self.inc_tab()+ "<target type='serial' port='0'/>" + \
            self.dec_tab()+'</console>'
        if windows_os:
            text += self.tab() + "<controller type='usb' index='0'/>" + \
                self.tab() + "<controller type='ide' index='0'/>" + \
                self.tab() + "<input type='mouse' bus='ps2'/>" + \
                self.tab() + "<sound model='ich6'/>" + \
                self.tab() + "<video>" + \
                self.inc_tab() + "<model type='cirrus' vram='9216' heads='1'/>" + \
                self.dec_tab() + "</video>" + \
                self.tab() + "<memballoon model='virtio'/>" + \
                self.tab() + "<input type='tablet' bus='usb'/>" #TODO revisar

#>             self.tab()+'<alias name=\'hostdev0\'/>\n' +\
#>             self.dec_tab()+'</hostdev>\n' +\
#>             self.tab()+'<input type=\'tablet\' bus=\'usb\'/>\n'
        if windows_os:
            text += self.tab() + "<graphics type='vnc' port='-1' autoport='yes'/>"
        else:
            #If image contains 'GRAPH' include graphics
            #if 'GRAPH' in image:
            text += self.tab() + "<graphics type='vnc' port='-1' autoport='yes' listen='0.0.0.0'>" +\
                self.inc_tab() + "<listen type='address' address='0.0.0.0'/>" +\
                self.dec_tab() + "</graphics>"

        vd_index = 'a'
        for dev in dev_list:
            bus_ide_dev = bus_ide
            if dev['type']=='cdrom' or dev['type']=='disk':
                if dev['type']=='cdrom':
                    bus_ide_dev = True
                text += self.tab() + "<disk type='file' device='"+dev['type']+"'>"
                if 'file format' in dev:
                    text += self.inc_tab() + "<driver name='qemu' type='"  +dev['file format']+ "' cache='writethrough'/>"
                if 'source file' in dev:
                    text += self.tab() + "<source file='" +dev['source file']+ "'/>"
                #elif v['type'] == 'block':
                #    text += self.tab() + "<source dev='" + v['source'] + "'/>"
                #else:
                #    return -1, 'Unknown disk type ' + v['type']
                vpci = dev.get('vpci',None)
                if vpci == None:
                    vpci = dev['metadata'].get('vpci',None)
                text += self.pci2xml(vpci)
               
                if bus_ide_dev:
                    text += self.tab() + "<target dev='hd" +vd_index+ "' bus='ide'/>"   #TODO allows several type of disks
                else:
                    text += self.tab() + "<target dev='vd" +vd_index+ "' bus='virtio'/>" 
                text += self.dec_tab() + '</disk>'
                vd_index = chr(ord(vd_index)+1)
            elif dev['type']=='xml':
                dev_text = dev['xml']
                if 'vpci' in dev:
                    dev_text = dev_text.replace('__vpci__', dev['vpci'])
                if 'source file' in dev:
                    dev_text = dev_text.replace('__file__', dev['source file'])
                if 'file format' in dev:
                    dev_text = dev_text.replace('__format__', dev['source file'])
                if '__dev__' in dev_text:
                    dev_text = dev_text.replace('__dev__', vd_index)
                    vd_index = chr(ord(vd_index)+1)
                text += dev_text
            else:
                return -1, 'Unknown device type ' + dev['type']

        net_nb=0
        bridge_interfaces = server.get('networks', [])
        for v in bridge_interfaces:
            #Get the brifge name
            self.db_lock.acquire()
            result, content = self.db.get_table(FROM='nets', SELECT=('provider',),WHERE={'uuid':v['net_id']} )
            self.db_lock.release()
            if result <= 0:
                self.logger.error("create_xml_server ERROR %d getting nets %s", result, content)
                return -1, content
            #ALF: Allow by the moment the 'default' bridge net because is confortable for provide internet to VM
            #I know it is not secure    
            #for v in sorted(desc['network interfaces'].itervalues()):
            model = v.get("model", None)
            if content[0]['provider']=='default':
                text += self.tab() + "<interface type='network'>" + \
                    self.inc_tab() + "<source network='" +content[0]['provider']+ "'/>"
            elif content[0]['provider'][0:7]=='macvtap':
                text += self.tab()+"<interface type='direct'>" + \
                    self.inc_tab() + "<source dev='" + self.get_local_iface_name(content[0]['provider'][8:]) + "' mode='bridge'/>" + \
                    self.tab() + "<target dev='macvtap0'/>"
                if windows_os:
                    text += self.tab() + "<alias name='net" + str(net_nb) + "'/>"
                elif model==None:
                    model = "virtio"
            elif content[0]['provider'][0:6]=='bridge':
                text += self.tab() + "<interface type='bridge'>" +  \
                    self.inc_tab()+"<source bridge='" +self.get_local_iface_name(content[0]['provider'][7:])+ "'/>"
                if windows_os:
                    text += self.tab() + "<target dev='vnet" + str(net_nb)+ "'/>" +\
                        self.tab() + "<alias name='net" + str(net_nb)+ "'/>"
                elif model==None:
                    model = "virtio"
            elif content[0]['provider'][0:3] == "OVS":
                vlan = content[0]['provider'].replace('OVS:', '')
                text += self.tab() + "<interface type='bridge'>" + \
                        self.inc_tab() + "<source bridge='ovim-" + str(vlan) + "'/>"
            else:
                return -1, 'Unknown Bridge net provider ' + content[0]['provider']
            if model!=None:
                text += self.tab() + "<model type='" +model+ "'/>"
            if v.get('mac_address', None) != None:
                text+= self.tab() +"<mac address='" +v['mac_address']+ "'/>"
            text += self.pci2xml(v.get('vpci',None))
            text += self.dec_tab()+'</interface>'
            
            net_nb += 1

        interfaces = numa.get('interfaces', [])

        net_nb=0
        for v in interfaces:
            if self.develop_mode: #map these interfaces to bridges
                text += self.tab() + "<interface type='bridge'>" +  \
                    self.inc_tab()+"<source bridge='" +self.develop_bridge_iface+ "'/>"
                if windows_os:
                    text += self.tab() + "<target dev='vnet" + str(net_nb)+ "'/>" +\
                        self.tab() + "<alias name='net" + str(net_nb)+ "'/>"
                else:
                    text += self.tab() + "<model type='e1000'/>" #e1000 is more probable to be supported than 'virtio'
                if v.get('mac_address', None) != None:
                    text+= self.tab() +"<mac address='" +v['mac_address']+ "'/>"
                text += self.pci2xml(v.get('vpci',None))
                text += self.dec_tab()+'</interface>'
                continue
                
            if v['dedicated'] == 'yes':  #passthrought
                text += self.tab() + "<hostdev mode='subsystem' type='pci' managed='yes'>" + \
                    self.inc_tab() + "<source>"
                self.inc_tab()
                text += self.pci2xml(v['source'])
                text += self.dec_tab()+'</source>'
                text += self.pci2xml(v.get('vpci',None))
                if windows_os:
                    text += self.tab() + "<alias name='hostdev" + str(net_nb) + "'/>"
                text += self.dec_tab()+'</hostdev>'
                net_nb += 1
            else:        #sriov_interfaces
                #skip not connected interfaces
                if v.get("net_id") == None:
                    continue
                text += self.tab() + "<interface type='hostdev' managed='yes'>"
                self.inc_tab()
                if v.get('mac_address', None) != None:
                    text+= self.tab() + "<mac address='" +v['mac_address']+ "'/>"
                text+= self.tab()+'<source>'
                self.inc_tab()
                text += self.pci2xml(v['source'])
                text += self.dec_tab()+'</source>'
                if v.get('vlan',None) != None:
                    text += self.tab() + "<vlan>   <tag id='" + str(v['vlan']) + "'/>   </vlan>"
                text += self.pci2xml(v.get('vpci',None))
                if windows_os:
                    text += self.tab() + "<alias name='hostdev" + str(net_nb) + "'/>"
                text += self.dec_tab()+'</interface>'

            
        text += self.dec_tab()+'</devices>'+\
        self.dec_tab()+'</domain>'
        return 0, text

    def create_xml_xen_server(self, server, dev_list, server_metadata={}):  #CLICKOS MOD
        """Function that implements the generation of the VM XML definition.
        Additional devices are in dev_list list
        The main disk is upon dev_list[0]"""

    #get if operating system is Windows
        windows_os = False
        os_type = server_metadata.get('os_type', None)
        if os_type == None and 'metadata' in dev_list[0]:
            os_type = dev_list[0]['metadata'].get('os_type', None)
        if os_type != None and os_type.lower() == "windows":
            windows_os = True
    #get type of hard disk bus
        bus_ide = True if windows_os else False
        bus = server_metadata.get('bus', None)
        if bus == None and 'metadata' in dev_list[0]:
            bus = dev_list[0]['metadata'].get('bus', None)
        if bus != None:
            bus_ide = True if bus=='ide' else False

        self.xml_level = 0

        text = "<domain type='xen'>"
    #get topology
        topo = server_metadata.get('topology', None)
        if topo == None and 'metadata' in dev_list[0]:
            topo = dev_list[0]['metadata'].get('topology', None)
    #name
        name = server.get('name','') + "_" + server['uuid']
        name = name[:58]  #qemu impose a length  limit of 59 chars or not start. Using 58
        text += self.inc_tab() + "<name>" + name+ "</name>"
    #uuid
        text += self.tab() + "<uuid>" + server['uuid'] + "</uuid>"

        numa={}
        if 'extended' in server and server['extended']!=None and 'numas' in server['extended']:
            numa = server['extended']['numas'][0]
    #memory
        use_huge = False
        memory = int(numa.get('memory',0))*1024*1024 #in KiB
        if memory==0:
            memory = int(server['ram'])*1024;
        else:
            if not self.develop_mode:
                use_huge = True
        if memory==0:
            return -1, 'No memory assigned to instance'
        memory = str(memory)
        text += self.tab() + "<memory unit='KiB'>" +memory+"</memory>"
        text += self.tab() + "<currentMemory unit='KiB'>" +memory+ "</currentMemory>"
        if use_huge:
            text += self.tab()+'<memoryBacking>'+ \
                self.inc_tab() + '<hugepages/>'+ \
                self.dec_tab()+ '</memoryBacking>'

    #cpu
        use_cpu_pinning=False
        vcpus = int(server.get("vcpus",0))
        cpu_pinning = []
        if 'cores-source' in numa:
            use_cpu_pinning=True
            for index in range(0, len(numa['cores-source'])):
                cpu_pinning.append( [ numa['cores-id'][index], numa['cores-source'][index] ] )
                vcpus += 1
        if 'threads-source' in numa:
            use_cpu_pinning=True
            for index in range(0, len(numa['threads-source'])):
                cpu_pinning.append( [ numa['threads-id'][index], numa['threads-source'][index] ] )
                vcpus += 1
        if 'paired-threads-source' in numa:
            use_cpu_pinning=True
            for index in range(0, len(numa['paired-threads-source'])):
                cpu_pinning.append( [numa['paired-threads-id'][index][0], numa['paired-threads-source'][index][0] ] )
                cpu_pinning.append( [numa['paired-threads-id'][index][1], numa['paired-threads-source'][index][1] ] )
                vcpus += 2

        if use_cpu_pinning and not self.develop_mode:
            text += self.tab()+"<vcpu placement='static'>" +str(len(cpu_pinning)) +"</vcpu>" + \
                self.tab()+'<cputune>'
            self.xml_level += 1
            for i in range(0, len(cpu_pinning)):
                text += self.tab() + "<vcpupin vcpu='" +str(cpu_pinning[i][0])+ "' cpuset='" +str(cpu_pinning[i][1]) +"'/>"
            text += self.dec_tab()+'</cputune>'+ \
                self.tab() + '<numatune>' +\
                self.inc_tab() + "<memory mode='strict' nodeset='" +str(numa['source'])+ "'/>" +\
                self.dec_tab() + '</numatune>'
        else:
            if vcpus==0:
                return -1, "Instance without number of cpus"
            text += self.tab()+"<vcpu>" + str(vcpus)  + "</vcpu>"

    #boot
        boot_cdrom = False
        for dev in dev_list:
            if dev['type']=='cdrom' :
                boot_cdrom = True
                break
        text += self.tab()+ '<os>' + \
            self.inc_tab() + "<type arch='x86_64' machine='xenfv'>hvm</type>"
        text +=  self.tab() + "<loader type='rom'>/usr/lib/xen/boot/hvmloader</loader>"
        if boot_cdrom:
            text +=  self.tab() + "<boot dev='cdrom'/>"
        text +=  self.tab() + "<boot dev='hd'/>" + \
            self.dec_tab()+'</os>'
    #features
        text += self.tab()+'<features>'+\
            self.inc_tab()+'<acpi/>' +\
            self.tab()+'<apic/>' +\
            self.tab()+'<pae/>'+ \
            self.dec_tab() +'</features>'
        if topo == "oneSocket:hyperthreading":
            if vcpus % 2 != 0:
                return -1, 'Cannot expose hyperthreading with an odd number of vcpus'
            text += self.tab() + "<cpu mode='host-model'> <topology sockets='1' cores='%d' threads='2' /> </cpu>" % vcpus/2
        elif windows_os or topo == "oneSocket":
            text += self.tab() + "<cpu mode='host-model'> <topology sockets='1' cores='%d' threads='1' /> </cpu>" % vcpus
        else:
            text += self.tab() + "<cpu mode='host-model'></cpu>"
        text += self.tab() + "<clock offset='utc'/>" +\
            self.tab() + "<on_poweroff>destroy</on_poweroff>" + \
            self.tab() + "<on_reboot>restart</on_reboot>" + \
            self.tab() + "<on_crash>preserve</on_crash>"
        text += self.tab() + "<devices>" + \
            self.inc_tab() + "<emulator>/usr/lib64/xen/bin/qemu-dm</emulator>" + \
            self.tab() + "<serial type='pty'>" +\
            self.inc_tab() + "<target port='0'/>" + \
            self.dec_tab() + "</serial>" +\
            self.tab() + "<console type='pty'>" + \
            self.inc_tab()+ "<target type='serial' port='0'/>" + \
            self.dec_tab()+'</console>'
        if windows_os:
            text += self.tab() + "<controller type='usb' index='0'/>" + \
                self.tab() + "<controller type='ide' index='0'/>" + \
                self.tab() + "<input type='mouse' bus='ps2'/>" + \
                self.tab() + "<sound model='ich6'/>" + \
                self.tab() + "<video>" + \
                self.inc_tab() + "<model type='cirrus' vram='9216' heads='1'/>" + \
                self.dec_tab() + "</video>" + \
                self.tab() + "<memballoon model='virtio'/>" + \
                self.tab() + "<input type='tablet' bus='usb'/>" #TODO revisar
        else:
            text += self.tab() + "<controller type='ide' index='0'/>" + \
                self.tab() + "<input type='mouse' bus='ps2'/>" + \
                self.tab() + "<input type='keyboard' bus='ps2'/>" + \
                self.tab() + "<video>" + \
                self.inc_tab() + "<model type='cirrus' vram='9216' heads='1'/>" + \
                self.dec_tab() + "</video>"

#>             self.tab()+'<alias name=\'hostdev0\'/>\n' +\
#>             self.dec_tab()+'</hostdev>\n' +\
#>             self.tab()+'<input type=\'tablet\' bus=\'usb\'/>\n'
        if windows_os:
            text += self.tab() + "<graphics type='vnc' port='5900' autoport='yes'/>"
        else:
            #If image contains 'GRAPH' include graphics
            #if 'GRAPH' in image:
            text += self.tab() + "<graphics type='vnc' port='5900' autoport='yes' listen='0.0.0.0'>" +\
                 self.inc_tab() + "<listen type='address' address='0.0.0.0'/>" +\
                 self.dec_tab() + "</graphics>"

        vd_index = 'a'
        for dev in dev_list:
            bus_ide_dev = bus_ide
            if dev['type']=='cdrom' or dev['type']=='disk':
                if dev['type']=='cdrom':
                    bus_ide_dev = True
                text += self.tab() + "<disk type='file' device='"+dev['type']+"'>"
                if 'source file' in dev:
                    text += self.tab() + "<source file='" +dev['source file']+ "'/>"
                #elif v['type'] == 'block':
                #    text += self.tab() + "<source dev='" + v['source'] + "'/>"
                #else:
                #    return -1, 'Unknown disk type ' + v['type']
                vpci = dev.get('vpci',None)
                if vpci == None:
                    vpci = dev['metadata'].get('vpci',None)
                text += self.pci2xml(vpci)

                if bus_ide_dev:
                    text += self.tab() + "<target dev='hd" +vd_index+ "' bus='ide'/>"   #TODO allows several type of disks
                else:
                    text += self.tab() + "<target dev='vd" +vd_index+ "' bus='virtio'/>"
                text += self.dec_tab() + '</disk>'
                vd_index = chr(ord(vd_index)+1)
            elif dev['type']=='xml':
                dev_text = dev['xml']
                if 'vpci' in dev:
                    dev_text = dev_text.replace('__vpci__', dev['vpci'])
                if 'source file' in dev:
                    dev_text = dev_text.replace('__file__', dev['source file'])
                if 'file format' in dev:
                    dev_text = dev_text.replace('__format__', dev['source file'])
                if '__dev__' in dev_text:
                    dev_text = dev_text.replace('__dev__', vd_index)
                    vd_index = chr(ord(vd_index)+1)
                text += dev_text
            else:
                return -1, 'Unknown device type ' + dev['type']

    #networking: ManagementPlane network
        net_nb=0
        bridge_interfaces = server.get('networks', [])
        for v in bridge_interfaces:
            #Get the brifge name
            self.db_lock.acquire()
            result, content = self.db.get_table(FROM='nets', SELECT=('name', 'provider',),WHERE={'uuid':v['net_id']} ) #CLICKOS MOD
            self.db_lock.release()
            if result <= 0:
                print "create_xml_server ERROR getting nets",result, content
                return -1, content
            #ALF: Allow by the moment the 'default' bridge net because is confortable for provide internet to VM
            #I know it is not secure
            #for v in sorted(desc['network interfaces'].itervalues()):
            model = v.get("model", None)
            if content[0]['provider']=='default':
                text += self.tab() + "<interface type='network'>" + \
                    self.inc_tab() + "<source network='" +content[0]['provider']+ "'/>"
            elif content[0]['provider'][0:7]=='macvtap':
                text += self.tab()+"<interface type='direct'>" + \
                    self.inc_tab() + "<source dev='" + self.get_local_iface_name(content[0]['provider'][8:]) + "' mode='bridge'/>" + \
                    self.tab() + "<target dev='macvtap0'/>"
                if windows_os:
                    text += self.tab() + "<alias name='net" + str(net_nb) + "'/>"
                elif model==None:
                    model = "virtio"
            elif content[0]['provider'][0:6]=='bridge':
                text += self.tab() + "<interface type='bridge'>" +  \
                    self.inc_tab()+"<source bridge='" +self.get_local_iface_name(content[0]['provider'][7:])+ "'/>"
                if windows_os:
                    text += self.tab() + "<target dev='vnet" + str(net_nb)+ "'/>" +\
                        self.tab() + "<alias name='net" + str(net_nb)+ "'/>"
                elif model==None:
                    model = "virtio"
            elif content[0]['provider'][0:3] == "OVS":
                vlan = content[0]['provider'].replace('OVS:', '')
                netname = content[0]['name']
                text += self.tab() + "<interface type='bridge'>" + \
                        self.inc_tab() + "<source bridge='ovim-" + netname + "'/>"
                text += self.tab() + "<script path='vif-openvswitch'/>"
            else:
                return -1, 'Unknown Bridge net provider ' + content[0]['provider']
            if model!=None:
                text += self.tab() + "<model type='" +model+ "'/>"
            if v.get('mac_address', None) != None:
                text+= self.tab() +"<mac address='" +v['mac_address']+ "'/>"
            text += self.pci2xml(v.get('vpci',None))
            text += self.dec_tab()+'</interface>'

            net_nb += 1

        interfaces = numa.get('interfaces', [])

        net_nb=0
        for v in interfaces:
            if self.develop_mode: #map these interfaces to bridges
                text += self.tab() + "<interface type='bridge'>" +  \
                    self.inc_tab()+"<source bridge='" +self.develop_bridge_iface+ "'/>"
                if windows_os:
                    text += self.tab() + "<target dev='vnet" + str(net_nb)+ "'/>" +\
                        self.tab() + "<alias name='net" + str(net_nb)+ "'/>"
                else:
                    text += self.tab() + "<model type='e1000'/>" #e1000 is more probable to be supported than 'virtio'
                if v.get('mac_address', None) != None:
                    text+= self.tab() +"<mac address='" +v['mac_address']+ "'/>"
                text += self.pci2xml(v.get('vpci',None))
                text += self.dec_tab()+'</interface>'
                continue

            if v['dedicated'] == 'yes':  #passthrought
                text += self.tab() + "<hostdev mode='subsystem' type='pci' managed='yes'>" + \
                    self.inc_tab() + "<source>"
                self.inc_tab()
                text += self.pci2xml(v['source'])
                text += self.dec_tab()+'</source>'
                text += self.pci2xml(v.get('vpci',None))
                if windows_os:
                    text += self.tab() + "<alias name='hostdev" + str(net_nb) + "'/>"
                text += self.dec_tab()+'</hostdev>'
                net_nb += 1
            else:        #sriov_interfaces
                #skip not connected interfaces
                if v.get("net_id") == None:
                    continue
                text += self.tab() + "<interface type='hostdev' managed='yes'>"
                self.inc_tab()
                if v.get('mac_address', None) != None:
                    text+= self.tab() + "<mac address='" +v['mac_address']+ "'/>"
                text+= self.tab()+'<source>'
                self.inc_tab()
                text += self.pci2xml(v['source'])
                text += self.dec_tab()+'</source>'
                if v.get('vlan',None) != None:
                    text += self.tab() + "<vlan>   <tag id='" + str(v['vlan']) + "'/>   </vlan>"
                text += self.pci2xml(v.get('vpci',None))
                if windows_os:
                    text += self.tab() + "<alias name='hostdev" + str(net_nb) + "'/>"
                text += self.dec_tab()+'</interface>'


        text += self.dec_tab()+'</devices>'+\
        self.dec_tab()+'</domain>'
        return 0, text

    def create_xml_srv_clickos(self, server, dev_list, server_metadata={}):   #CLICKOS MOD
        """Function that implements the generation of the VM XML definition.
        This function is designed for specific boot of ClickOS image with Xen.
        Additional devices are in dev_list list
        The main disk is upon dev_list[0]"""

    #get if operating system is Windows
        windows_os = False
    #get type of hard disk bus
        bus_ide = False

        self.xml_level = 0

        text = "<domain type='xen'>"
    #name
        name = server.get('name','') + "_" + server['uuid']
        name = name[:58]  #qemu impose a length  limit of 59 chars or not start. Using 58
        text += self.inc_tab() + "<name>" + name+ "</name>"
    #uuid
        text += self.tab() + "<uuid>" + server['uuid'] + "</uuid>"

        ### FOR DEBUG ONLY
        #print "Server Variable:\n----------------\n" + str(server) + "\n----------------\n"  # CLICKOS MOD
        #print "Dev List Variable:\n------------------\n" + str(dev_list) + "\n------------------\n"  # CLICKOS MOD
        #print "Server Metadata Variable:\n-------------------------\n" + str(server) + "\n-------------------------\n"  # CLICKOS MOD

        numa={}
        if 'extended' in server and server['extended']!=None and 'numas' in server['extended']:
            numa = server['extended']['numas'][0]
    #memory
        use_huge = False
        memory = int(numa.get('memory',0))*1024*1024 #in KiB
        if memory==0:
            memory = int(server['ram'])*1024;
        else:
            if not self.develop_mode and not self.unikernel_mode:  #CLICKOS MOD
                use_huge = True
        if memory==0:
            return -1, 'No memory assigned to instance'
        memory = str(memory)
        text += self.tab() + "<memory unit='KiB'>" +memory+"</memory>"
        text += self.tab() + "<currentMemory unit='KiB'>" +memory+ "</currentMemory>"
        if use_huge:
            text += self.tab()+'<memoryBacking>'+ \
                self.inc_tab() + '<hugepages/>'+ \
                self.dec_tab()+ '</memoryBacking>'

    #cpu
        use_cpu_pinning=False
        vcpus = int(server.get("vcpus",0))
        cpu_pinning = []
        if 'cores-source' in numa:
            use_cpu_pinning=True
            for index in range(0, len(numa['cores-source'])):
                cpu_pinning.append( [ numa['cores-id'][index], numa['cores-source'][index] ] )
                vcpus += 1
        if 'threads-source' in numa:
            use_cpu_pinning=True
            for index in range(0, len(numa['threads-source'])):
                cpu_pinning.append( [ numa['threads-id'][index], numa['threads-source'][index] ] )
                vcpus += 1
        if 'paired-threads-source' in numa:
            use_cpu_pinning=True
            for index in range(0, len(numa['paired-threads-source'])):
                cpu_pinning.append( [numa['paired-threads-id'][index][0], numa['paired-threads-source'][index][0] ] )
                cpu_pinning.append( [numa['paired-threads-id'][index][1], numa['paired-threads-source'][index][1] ] )
                vcpus += 2

        if use_cpu_pinning and not self.develop_mode and not self.unikernel_mode:
            text += self.tab()+"<vcpu placement='static'>" +str(len(cpu_pinning)) +"</vcpu>" + \
                self.tab()+'<cputune>'
            self.xml_level += 1
            for i in range(0, len(cpu_pinning)):
                text += self.tab() + "<vcpupin vcpu='" +str(cpu_pinning[i][0])+ "' cpuset='" +str(cpu_pinning[i][1]) +"'/>"
            text += self.dec_tab()+'</cputune>'+ \
                self.tab() + '<numatune>' +\
                self.inc_tab() + "<memory mode='strict' nodeset='" +str(numa['source'])+ "'/>" +\
                self.dec_tab() + '</numatune>'
        else:
            if vcpus==0:
                return -1, "Instance without number of cpus"
            text += self.tab()+"<vcpu>" + str(vcpus)  + "</vcpu>"

    #boot
        text += self.tab()+ '<os>' + \
            self.inc_tab() + "<type arch='x86_64' machine='xenpv'>xen</type>"
        text +=  self.tab() + "<kernel>" + str(dev_list[0]['source file']) + "</kernel>" + \
            self.dec_tab()+'</os>'
    #features
        text += self.tab()+'<features>'+\
            self.inc_tab()+'<acpi/>' +\
            self.tab()+'<apic/>' +\
            self.tab()+'<pae/>'+ \
            self.dec_tab() +'</features>'
        #if windows_os:
        #    text += self.tab() + "<cpu mode='host-model'> <topology sockets='1' cores='%d' threads='1' /> </cpu>"% vcpus
        #else:
        text += self.tab() + "<cpu mode='host-model'></cpu>"
        text += self.tab() + "<clock offset='utc'/>" +\
            self.tab() + "<on_poweroff>destroy</on_poweroff>" + \
            self.tab() + "<on_reboot>restart</on_reboot>" + \
            self.tab() + "<on_crash>destroy</on_crash>"
        text += self.tab() + "<devices>" + \
            self.tab() + "<console type='pty'>" + \
            self.inc_tab()+ "<target type='xen' port='0'/>" + \
            self.dec_tab()+'</console>'

    #networking: ManagementPlane network
        net_nb=0
        bridge_interfaces = server.get('networks', [])
        for v in bridge_interfaces:
            #Get the brifge name
            self.db_lock.acquire()
            result, content = self.db.get_table(FROM='nets', SELECT=('name', 'provider',),WHERE={'uuid':v['net_id']} ) #CLICKOS MOD
            self.db_lock.release()
            if result <= 0:
                print "create_xml_server ERROR getting nets",result, content
                return -1, content
            print str(content), "\n\n"
            #ALF: Allow by the moment the 'default' bridge net because is confortable for provide internet to VM
            #I know it is not secure
            #for v in sorted(desc['network interfaces'].itervalues()):
            model = v.get("model", None)
            if content[0]['provider']=='default':
                text += self.tab() + "<interface type='network'>" + \
                    self.inc_tab() + "<source network='" +content[0]['provider']+ "'/>"
            elif content[0]['provider'][0:7]=='macvtap':
                text += self.tab()+"<interface type='direct'>" + \
                    self.inc_tab() + "<source dev='" + self.get_local_iface_name(content[0]['provider'][8:]) + "' mode='bridge'/>" + \
                    self.tab() + "<target dev='macvtap0'/>"
            elif content[0]['provider'][0:6]=='bridge':
                text += self.tab() + "<interface type='bridge'>" + \
                    self.inc_tab()+"<source bridge='" +self.get_local_iface_name(content[0]['provider'][7:])+ "'/>"
            elif content[0]['provider'][0:3] == "OVS":
                vlan = content[0]['provider'].replace('OVS:', '')
                netname = content[0]['name']
                text += self.tab() + "<interface type='bridge'>" + \
                        self.inc_tab() + "<source bridge='ovim-" + netname + "'/>"
                text += self.tab() + "<script path='vif-openvswitch'/>"
            else:
                return -1, 'Unknown Bridge net provider ' + content[0]['provider']
            if model!=None:
                text += self.tab() + "<model type='" +model+ "'/>"
            if v.get('mac_address', None) != None:
                text+= self.tab() +"<mac address='" +v['mac_address']+ "'/>"
            text += self.pci2xml(v.get('vpci',None))
            text += self.dec_tab()+'</interface>'

            net_nb += 1

        interfaces = numa.get('interfaces', [])

        net_nb=0
        for v in interfaces:
            if self.develop_mode: #map these interfaces to bridges
                text += self.tab() + "<interface type='bridge'>" +  \
                    self.inc_tab()+"<source bridge='" +self.develop_bridge_iface+ "'/>"
                if windows_os:
                    text += self.tab() + "<target dev='vnet" + str(net_nb)+ "'/>" +\
                        self.tab() + "<alias name='net" + str(net_nb)+ "'/>"
                else:
                    text += self.tab() + "<model type='e1000'/>" #e1000 is more probable to be supported than 'virtio'
                if v.get('mac_address', None) != None:
                    text+= self.tab() +"<mac address='" +v['mac_address']+ "'/>"
                text += self.pci2xml(v.get('vpci',None))
                text += self.dec_tab()+'</interface>'
                continue

            if v['dedicated'] == 'yes':  #passthrought
                text += self.tab() + "<hostdev mode='subsystem' type='pci' managed='yes'>" + \
                    self.inc_tab() + "<source>"
                self.inc_tab()
                text += self.pci2xml(v['source'])
                text += self.dec_tab()+'</source>'
                text += self.pci2xml(v.get('vpci',None))
                if windows_os:
                    text += self.tab() + "<alias name='hostdev" + str(net_nb) + "'/>"
                text += self.dec_tab()+'</hostdev>'
                net_nb += 1
            else:        #sriov_interfaces
                #skip not connected interfaces
                if v.get("net_id") == None:
                    continue
                text += self.tab() + "<interface type='hostdev' managed='yes'>"
                self.inc_tab()
                if v.get('mac_address', None) != None:
                    text+= self.tab() + "<mac address='" +v['mac_address']+ "'/>"
                text+= self.tab()+'<source>'
                self.inc_tab()
                text += self.pci2xml(v['source'])
                text += self.dec_tab()+'</source>'
                if v.get('vlan',None) != None:
                    text += self.tab() + "<vlan>   <tag id='" + str(v['vlan']) + "'/>   </vlan>"
                text += self.pci2xml(v.get('vpci',None))
                if windows_os:
                    text += self.tab() + "<alias name='hostdev" + str(net_nb) + "'/>"
                text += self.dec_tab()+'</interface>'

        text += self.dec_tab()+'</devices>'+\
        self.dec_tab()+'</domain>'
        return 0, text
    
    def pci2xml(self, pci):
        '''from a pci format text XXXX:XX:XX.X generates the xml content of <address>
        alows an empty pci text'''
        if pci is None:
            return ""
        first_part = pci.split(':')
        second_part = first_part[2].split('.')
        return self.tab() + "<address type='pci' domain='0x" + first_part[0] + \
                    "' bus='0x" + first_part[1] + "' slot='0x" + second_part[0] + \
                    "' function='0x" + second_part[1] + "'/>" 
    
    def tab(self):
        """Return indentation according to xml_level"""
        return "\n" + ('  '*self.xml_level)
    
    def inc_tab(self):
        """Increment and return indentation according to xml_level"""
        self.xml_level += 1
        return self.tab()
    
    def dec_tab(self):
        """Decrement and return indentation according to xml_level"""
        self.xml_level -= 1
        return self.tab()

    def create_ovs_bridge(self, brname="br-int"): #CLICKOS MOD
        """
        Create a bridge in compute OVS to allocate VMs
        :return: True if success
        """
        if self.test:
            return True
        try:
            command = 'sudo ovs-vsctl --may-exist add-br ' + brname + ' -- set Bridge ' + brname + ' stp_enable=true' #CLICKOS MOD
            #command = 'sudo ovs-vsctl --may-exist add-br br-int -- set Bridge br-int stp_enable=true'
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()
            if len(content) == 0:
                return True
            else:
                return False
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("create_ovs_bridge ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False

    def delete_port_to_ovs_bridge(self, vlan, net_uuid):
        """
        Delete linux bridge port attched to a OVS bridge, if port is not free the port is not removed
        :param vlan: vlan port id
        :param net_uuid: network id
        :return:
        """

        if self.test:
            return True
        try:
            port_name = 'ovim-' + str(vlan)
            command = 'sudo ovs-vsctl del-port br-int ' + port_name
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()
            if len(content) == 0:
                return True
            else:
                return False
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("delete_port_to_ovs_bridge ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False

    def delete_dhcp_server(self, vlan, net_uuid, dhcp_path):
        """
        Delete dhcp server process lining in namespace
        :param vlan: segmentation id
        :param net_uuid: network uuid
        :param dhcp_path: conf fiel path that live in namespace side
        :return:
        """
        if self.test:
            return True
        if not self.is_dhcp_port_free(vlan, net_uuid):
            return True
        try:
            net_namespace = 'ovim-' + str(vlan)
            dhcp_path = os.path.join(dhcp_path, net_namespace)
            pid_file = os.path.join(dhcp_path, 'dnsmasq.pid')

            command = 'sudo ip netns exec ' + net_namespace + ' cat ' + pid_file
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            command = 'sudo ip netns exec ' + net_namespace + ' kill -9 ' + content
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            # if len(content) == 0:
            #     return True
            # else:
            #     return False
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("delete_dhcp_server ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False

    def is_dhcp_port_free(self, host_id, net_uuid):
        """
        Check if any port attached to the a net in a vxlan mesh across computes nodes
        :param host_id: host id
        :param net_uuid: network id
        :return: True if is not free
        """
        self.db_lock.acquire()
        result, content = self.db.get_table(
            FROM='ports',
            WHERE={'type': 'instance:ovs', 'net_id': net_uuid}
        )
        self.db_lock.release()

        if len(content) > 0:
            return False
        else:
            return True

    def is_port_free(self, host_id, net_uuid):
        """
        Check if there not ovs ports of a network in a compute host.
        :param host_id:  host id
        :param net_uuid: network id
        :return: True if is not free
        """

        self.db_lock.acquire()
        result, content = self.db.get_table(
            FROM='ports as p join instances as i on p.instance_id=i.uuid',
            WHERE={"i.host_id": self.host_id, 'p.type': 'instance:ovs', 'p.net_id': net_uuid}
        )
        self.db_lock.release()

        if len(content) > 0:
            return False
        else:
            return True

    def add_port_to_ovs_bridge(self, vlan):
        """
        Add a bridge linux as a port to a OVS bridge and set a vlan for an specific linux bridge
        :param vlan: vlan port id
        :return: True if success
        """

        if self.test:
            return True
        try:
            port_name = 'ovim-' + str(vlan)
            command = 'sudo ovs-vsctl add-port br-int ' + port_name + ' tag=' + str(vlan)
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()
            if len(content) == 0:
                return True
            else:
                return False
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("add_port_to_ovs_bridge ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False

    def delete_dhcp_port(self, vlan, net_uuid):
        """
        Delete from an existing OVS bridge a linux bridge port attached and the linux bridge itself.
        :param vlan: segmentation id
        :param net_uuid: network id
        :return: True if success
        """

        if self.test:
            return True

        if not self.is_dhcp_port_free(vlan, net_uuid):
            return True
        self.delete_dhcp_interfaces(vlan)
        return True

    def delete_bridge_port_attached_to_ovs(self, vlan, net_uuid):
        """
        Delete from an existing OVS bridge a linux bridge port attached and the linux bridge itself.
        :param vlan:
        :param net_uuid:
        :return: True if success
        """
        if self.test:
            return

        if not self.is_port_free(vlan, net_uuid):
            return True
        self.delete_port_to_ovs_bridge(vlan, net_uuid)
        self.delete_linux_bridge(vlan)
        return True

    def delete_linux_bridge(self, vlan):
        """
        Delete a linux bridge in a scpecific compute.
        :param vlan: vlan port id
        :return: True if success
        """

        if self.test:
            return True
        try:
            port_name = 'ovim-' + str(vlan)
            command = 'sudo ip link set dev veth0-' + str(vlan) + ' down'
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            # content = stdout.read()
            #
            # if len(content) != 0:
            #     return False
            command = 'sudo ifconfig ' + port_name + ' down &&  sudo brctl delbr ' + port_name
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()
            if len(content) == 0:
                return True
            else:
                return False
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("delete_linux_bridge ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False

    def create_ovs_bridge_port(self, vlan):
        """
        Generate a linux bridge and attache the port to a OVS bridge
        :param vlan: vlan port id
        :return:
        """
        if self.test:
            return
        self.create_linux_bridge(vlan)
        self.add_port_to_ovs_bridge(vlan)

    def create_linux_bridge(self, vlan):
        """
        Create a linux bridge with STP active
        :param vlan: netowrk vlan id
        :return:
        """

        if self.test:
            return True
        try:
            port_name = 'ovim-' + str(vlan)
            command = 'sudo brctl show | grep ' + port_name
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            # if exist nothing to create
            # if len(content) == 0:
            #     return False

            command = 'sudo brctl addbr ' + port_name
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            # if len(content) == 0:
            #     return True
            # else:
            #     return False

            command = 'sudo brctl stp ' + port_name + ' on'
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            # if len(content) == 0:
            #     return True
            # else:
            #     return False
            command = 'sudo ip link set dev ' + port_name + ' up'
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            if len(content) == 0:
                return True
            else:
                return False
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("create_linux_bridge ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False

    def set_mac_dhcp_server(self, ip, mac, vlan, netmask, dhcp_path):
        """
        Write into dhcp conf file a rule to assigned a fixed ip given to an specific MAC address
        :param ip: IP address asigned to a VM
        :param mac: VM vnic mac to be macthed with the IP received
        :param vlan: Segmentation id
        :param netmask: netmask value
        :param path: dhcp conf file path that live in namespace side
        :return: True if success
        """

        if self.test:
            return True

        net_namespace = 'ovim-' + str(vlan)
        dhcp_path = os.path.join(dhcp_path, net_namespace)
        dhcp_hostsdir = os.path.join(dhcp_path, net_namespace)

        if not ip:
            return False
        try:
            ip_data = mac.upper() + ',' + ip

            command = 'sudo  ip netns exec ' + net_namespace + ' touch ' + dhcp_hostsdir
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            command = 'sudo  ip netns exec ' + net_namespace + ' sudo bash -ec "echo ' + ip_data + ' >> ' + dhcp_hostsdir + '"'

            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            if len(content) == 0:
                return True
            else:
                return False
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("set_mac_dhcp_server ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False

    def delete_mac_dhcp_server(self, ip, mac, vlan, dhcp_path):
        """
        Delete into dhcp conf file the ip  assigned to a specific MAC address

        :param ip: IP address asigned to a VM
        :param mac:  VM vnic mac to be macthed with the IP received
        :param vlan:  Segmentation id
        :param dhcp_path: dhcp conf file path that live in namespace side
        :return:
        """

        if self.test:
            return False
        try:
            net_namespace = 'ovim-' + str(vlan)
            dhcp_path = os.path.join(dhcp_path, net_namespace)
            dhcp_hostsdir = os.path.join(dhcp_path, net_namespace)

            if not ip:
                return False

            ip_data = mac.upper() + ',' + ip

            command = 'sudo  ip netns exec ' + net_namespace + ' sudo sed -i \'/' + ip_data + '/d\' ' + dhcp_hostsdir
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            if len(content) == 0:
                return True
            else:
                return False

        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("set_mac_dhcp_server ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False

    def launch_dhcp_server(self, vlan, ip_range, netmask, dhcp_path, gateway):
        """
        Generate a linux bridge and attache the port to a OVS bridge
        :param self:
        :param vlan: Segmentation id
        :param ip_range: IP dhcp range
        :param netmask: network netmask
        :param dhcp_path: dhcp conf file path that live in namespace side
        :param gateway: Gateway address for dhcp net
        :return: True if success
        """

        if self.test:
            return True
        try:
            interface = 'tap-' + str(vlan)
            net_namespace = 'ovim-' + str(vlan)
            dhcp_path = os.path.join(dhcp_path, net_namespace)
            leases_path = os.path.join(dhcp_path, "dnsmasq.leases")
            pid_file = os.path.join(dhcp_path, 'dnsmasq.pid')

            dhcp_range = ip_range[0] + ',' + ip_range[1] + ',' + netmask

            command = 'sudo ip netns exec ' + net_namespace + ' mkdir -p ' + dhcp_path
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            pid_path = os.path.join(dhcp_path, 'dnsmasq.pid')
            command = 'sudo  ip netns exec ' + net_namespace + ' cat ' + pid_path
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()
            # check if pid is runing
            pid_status_path = content
            if content:
                command = "ps aux | awk '{print $2 }' | grep " + pid_status_path
                self.logger.debug("command: " + command)
                (_, stdout, _) = self.ssh_conn.exec_command(command)
                content = stdout.read()
            if not content:
                command = 'sudo  ip netns exec ' + net_namespace + ' /usr/sbin/dnsmasq --strict-order --except-interface=lo ' \
                  '--interface=' + interface + ' --bind-interfaces --dhcp-hostsdir=' + dhcp_path + \
                  ' --dhcp-range ' + dhcp_range + ' --pid-file=' + pid_file + ' --dhcp-leasefile=' + leases_path + \
                  '  --listen-address ' + gateway

            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.readline()

            if len(content) == 0:
                return True
            else:
                return False
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("launch_dhcp_server ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False

    def delete_dhcp_interfaces(self, vlan):
        """
        Create a linux bridge with STP active
        :param vlan: netowrk vlan id
        :return:
        """

        if self.test:
            return True
        try:
            net_namespace = 'ovim-' + str(vlan)
            command = 'sudo ovs-vsctl del-port br-int ovs-tap-' + str(vlan)
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            command = 'sudo ip netns exec ' + net_namespace + ' ip link set dev tap-' + str(vlan) + ' down'
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            command = 'sudo ip link set dev ovs-tap-' + str(vlan) + ' down'
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("delete_dhcp_interfaces ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False

    def create_dhcp_interfaces(self, vlan, ip_listen_address, netmask):
        """
        Create a linux bridge with STP active
        :param vlan: segmentation id
        :param ip_listen_address: Listen Ip address for the dhcp service, the tap interface living in namesapce side
        :param netmask: dhcp net CIDR
        :return: True if success
        """

        if self.test:
            return True
        try:
            net_namespace = 'ovim-' + str(vlan)
            namespace_interface = 'tap-' + str(vlan)

            command = 'sudo ip netns add ' + net_namespace
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            command = 'sudo ip link add tap-' + str(vlan) + ' type veth peer name ovs-tap-' + str(vlan)
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            command = 'sudo ovs-vsctl add-port br-int ovs-tap-' + str(vlan) + ' tag=' + str(vlan)
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            command = 'sudo ip link set tap-' + str(vlan) + ' netns ' + net_namespace
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            command = 'sudo ip netns exec ' + net_namespace + ' ip link set dev tap-' + str(vlan) + ' up'
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            command = 'sudo ip link set dev ovs-tap-' + str(vlan) + ' up'
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            command = 'sudo ip netns exec ' + net_namespace + ' ip link set dev lo up'
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            command = 'sudo  ip netns exec ' + net_namespace + ' ' + ' ifconfig  ' + namespace_interface \
                      + ' ' + ip_listen_address + ' netmask ' + netmask
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()

            if len(content) == 0:
                return True
            else:
                return False
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("create_dhcp_interfaces ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False


    def create_ovs_vxlan_tunnel(self, vxlan_interface, remote_ip):
        """
        Create a vlxn tunnel between to computes with an OVS installed. STP is also active at port level
        :param vxlan_interface: vlxan inteface name.
        :param remote_ip: tunnel endpoint remote compute ip.
        :return:
        """
        if self.test:
            return True
        try:
            command = 'sudo ovs-vsctl add-port br-int ' + vxlan_interface + \
                      ' -- set Interface ' + vxlan_interface + '  type=vxlan options:remote_ip=' + remote_ip + \
                      ' -- set Port ' + vxlan_interface + ' other_config:stp-path-cost=10'
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()
            # print content
            if len(content) == 0:
                return True
            else:
                return False
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("create_ovs_vxlan_tunnel ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False

    def delete_ovs_vxlan_tunnel(self, vxlan_interface):
        """
        Delete a vlxan tunnel  port from a OVS brdige.
        :param vxlan_interface: vlxan name to be delete it.
        :return: True if success.
        """
        if self.test:
            return True
        try:
            command = 'sudo ovs-vsctl del-port br-int ' + vxlan_interface
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()
            # print content
            if len(content) == 0:
                return True
            else:
                return False
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("delete_ovs_vxlan_tunnel ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False

    def delete_ovs_bridge(self, brname="br-int"): #CLICKOS MOD
        """
        Delete a OVS bridge from  a compute.
        :return: True if success
        """
        if self.test:
            return True
        try:
            command = 'sudo ovs-vsctl --if-exists del-br ' + brname #CLICKOS MOD
            #command = 'sudo ovs-vsctl del-br br-int'
            self.logger.debug("command: " + command)
            (_, stdout, _) = self.ssh_conn.exec_command(command)
            content = stdout.read()
            if len(content) == 0:
                return True
            else:
                return False
        except paramiko.ssh_exception.SSHException as e:
            self.logger.error("delete_ovs_bridge ssh Exception: " + str(e))
            if "SSH session not active" in str(e):
                self.ssh_connect()
            return False

    def get_file_info(self, path):
        command = 'ls -lL --time-style=+%Y-%m-%dT%H:%M:%S ' + path
        self.logger.debug("command: " + command)
        (_, stdout, _) = self.ssh_conn.exec_command(command)
        content = stdout.read()
        if len(content) == 0:
            return None  # file does not exist
        else:
            return content.split(" ")  # (permission, 1, owner, group, size, date, file)

    def qemu_get_info(self, path):
        command = 'qemu-img info ' + path
        self.logger.debug("command: " + command)
        (_, stdout, stderr) = self.ssh_conn.exec_command(command)
        content = stdout.read()
        if len(content) == 0:
            error = stderr.read()
            self.logger.error("get_qemu_info error " + error)
            raise paramiko.ssh_exception.SSHException("Error getting qemu_info: " + error)
        else:
            try: 
                return yaml.load(content)
            except yaml.YAMLError as exc:
                text = ""
                if hasattr(exc, 'problem_mark'):
                    mark = exc.problem_mark
                    text = " at position: (%s:%s)" % (mark.line+1, mark.column+1)
                self.logger.error("get_qemu_info yaml format Exception " + text)
                raise paramiko.ssh_exception.SSHException("Error getting qemu_info yaml format" + text)

    def qemu_change_backing(self, inc_file, new_backing_file):
        command = 'qemu-img rebase -u -b ' + new_backing_file + ' ' + inc_file 
        self.logger.debug("command: " + command)
        (_, _, stderr) = self.ssh_conn.exec_command(command)
        content = stderr.read()
        if len(content) == 0:
            return 0
        else:
            self.logger.error("qemu_change_backing error: " + content)
            return -1
    
    def get_notused_filename(self, proposed_name, suffix=''):
        '''Look for a non existing file_name in the host
            proposed_name: proposed file name, includes path
            suffix: suffix to be added to the name, before the extention
        '''
        extension = proposed_name.rfind(".")
        slash = proposed_name.rfind("/")
        if extension < 0 or extension < slash: # no extension
            extension = len(proposed_name)
        target_name = proposed_name[:extension] + suffix + proposed_name[extension:]
        info = self.get_file_info(target_name)
        if info is None:
            return target_name
        
        index=0
        while info is not None:
            target_name = proposed_name[:extension] + suffix +  "-" + str(index) + proposed_name[extension:]
            index+=1
            info = self.get_file_info(target_name) 
        return target_name
    
    def get_notused_path(self, proposed_path, suffix=''):
        '''Look for a non existing path at database for images
            proposed_path: proposed file name, includes path
            suffix: suffix to be added to the name, before the extention
        '''
        extension = proposed_path.rfind(".")
        if extension < 0:
            extension = len(proposed_path)
        if suffix != None:
            target_path = proposed_path[:extension] + suffix + proposed_path[extension:]
        index=0
        while True:
            r,_=self.db.get_table(FROM="images",WHERE={"path":target_path})
            if r<=0:
                return target_path
            target_path = proposed_path[:extension] + suffix +  "-" + str(index) + proposed_path[extension:]
            index+=1

    
    def delete_file(self, file_name):
        command = 'rm -f '+file_name
        self.logger.debug("command: " + command)
        (_, _, stderr) = self.ssh_conn.exec_command(command)
        error_msg = stderr.read()
        if len(error_msg) > 0:
            raise paramiko.ssh_exception.SSHException("Error deleting file: " + error_msg)

    def copy_file(self, source, destination, perserve_time=True):
        if source[0:4]=="http":
            command = "wget --no-verbose -O '{dst}' '{src}' 2>'{dst_result}' || cat '{dst_result}' >&2 && rm '{dst_result}'".format(
                dst=destination, src=source, dst_result=destination + ".result" )
        else:
            command = 'cp --no-preserve=mode'
            if perserve_time:
                command += ' --preserve=timestamps'
            command +=  " '{}' '{}'".format(source, destination)
        self.logger.debug("command: " + command)
        (_, _, stderr) = self.ssh_conn.exec_command(command)
        error_msg = stderr.read()
        if len(error_msg) > 0:
            raise paramiko.ssh_exception.SSHException("Error copying image to local host: " + error_msg)

    def copy_remote_file(self, remote_file, use_incremental):
        ''' Copy a file from the repository to local folder and recursively 
            copy the backing files in case the remote file is incremental
            Read and/or modified self.localinfo['files'] that contain the
            unmodified copies of images in the local path
            params:
                remote_file: path of remote file
                use_incremental: None (leave the decision to this function), True, False
            return:
                local_file: name of local file
                qemu_info: dict with quemu information of local file
                use_incremental_out: True, False; same as use_incremental, but if None a decision is taken
        '''
        
        use_incremental_out = use_incremental
        new_backing_file = None
        local_file = None
        file_from_local = True

        #in case incremental use is not decided, take the decision depending on the image
        #avoid the use of incremental if this image is already incremental
        if remote_file[0:4] == "http":
            file_from_local = False
        if file_from_local:
            qemu_remote_info = self.qemu_get_info(remote_file)
        if use_incremental_out==None:
            use_incremental_out = not ( file_from_local and 'backing file' in qemu_remote_info)
        #copy recursivelly the backing files
        if  file_from_local and 'backing file' in qemu_remote_info:
            new_backing_file, _, _ = self.copy_remote_file(qemu_remote_info['backing file'], True)
        
        #check if remote file is present locally
        if use_incremental_out and remote_file in self.localinfo['files']:
            local_file = self.localinfo['files'][remote_file]
            local_file_info =  self.get_file_info(local_file)
            if file_from_local:
                remote_file_info = self.get_file_info(remote_file)
            if local_file_info == None:
                local_file = None
            elif file_from_local and (local_file_info[4]!=remote_file_info[4] or local_file_info[5]!=remote_file_info[5]):
                #local copy of file not valid because date or size are different. 
                #TODO DELETE local file if this file is not used by any active virtual machine
                try:
                    self.delete_file(local_file)
                    del self.localinfo['files'][remote_file]
                except Exception:
                    pass
                local_file = None
            else: #check that the local file has the same backing file, or there are not backing at all
                qemu_info = self.qemu_get_info(local_file)
                if new_backing_file != qemu_info.get('backing file'):
                    local_file = None
                

        if local_file == None: #copy the file 
            img_name= remote_file.split('/') [-1]
            img_local = self.image_path + '/' + img_name
            local_file = self.get_notused_filename(img_local)
            self.copy_file(remote_file, local_file, use_incremental_out)

            if use_incremental_out:
                self.localinfo['files'][remote_file] = local_file
            if new_backing_file:
                self.qemu_change_backing(local_file, new_backing_file)
            qemu_info = self.qemu_get_info(local_file)
            
        return local_file, qemu_info, use_incremental_out
            
    def launch_server(self, conn, server, rebuild=False, domain=None):
        if self.test:
            time.sleep(random.randint(20,150)) #sleep random timeto be make it a bit more real
            return 0, 'Success'

        server_id = server['uuid']
        paused = server.get('paused','no')
        try:
            if domain!=None and rebuild==False:
                domain.resume()
                #self.server_status[server_id] = 'ACTIVE'
                return 0, 'Success'

            self.db_lock.acquire()
            result, server_data = self.db.get_instance(server_id)
            self.db_lock.release()
            if result <= 0:
                self.logger.error("launch_server ERROR getting server from DB %d %s", result, server_data)
                return result, server_data

            self.hypervisor = str(server_data['hypervisor'])        #CLICKOS MOD
 
        #0: get image metadata
            server_metadata = server.get('metadata', {})
            use_incremental = None
             
            if "use_incremental" in server_metadata:
                use_incremental = False if server_metadata["use_incremental"] == "no" else True
            if self.unikernel_mode == True:   #CLICKOS MOD
                use_incremental = False #CLICKOS MOD

            server_host_files = self.localinfo['server_files'].get( server['uuid'], {})
            if not self.unikernel_mode or (self.hypervisor != "xen-unik" and str(server_data['os_image_type']) != "clickos"):   #CLICKOS MOD
                if rebuild:
                    #delete previous incremental files
                    for file_ in server_host_files.values():
                        self.delete_file(file_['source file'] )
                    server_host_files={}
    
        #1: obtain aditional devices (disks)
            #Put as first device the main disk
            devices = [  {"type":"disk", "image_id":server['image_id'], "vpci":server_metadata.get('vpci', None) } ] 
            if 'extended' in server_data and server_data['extended']!=None and "devices" in server_data['extended']:
                devices += server_data['extended']['devices']

            for dev in devices:
                if dev['image_id'] == None:
                    continue
                
                self.db_lock.acquire()
                result, content = self.db.get_table(FROM='images', SELECT=('path', 'metadata'),
                                                    WHERE={'uuid': dev['image_id']})
                self.db_lock.release()
                if result <= 0:
                    error_text = "ERROR", result, content, "when getting image", dev['image_id']
                    self.logger.error("launch_server " + error_text)
                    return -1, error_text
                if content[0]['metadata'] is not None:
                    dev['metadata'] = json.loads(content[0]['metadata'])
                else:
                    dev['metadata'] = {}
                
                if dev['image_id'] in server_host_files:
                    dev['source file'] = server_host_files[ dev['image_id'] ] ['source file'] #local path
                    dev['file format'] = server_host_files[ dev['image_id'] ] ['file format'] # raw or qcow2
                    continue
                
            #2: copy image to host
                remote_file = content[0]['path']
                use_incremental_image = use_incremental
                if dev['metadata'].get("use_incremental") == "no":
                    use_incremental_image = False
                if not self.unikernel_mode or (self.hypervisor != "xen-unik" and self.hypervisor != "xenhvm"):   #CLICKOS MOD
                    local_file, qemu_info, use_incremental_image = self.copy_remote_file(remote_file, use_incremental_image)
                else:    #CLICKOS MOD
                    local_file = remote_file   #CLICKOS MOD
                    qemu_info = {'file format':'raw'}   #CLICKOS MOD
                    use_incremental_image = False  #CLICKOS MOD
                
                #create incremental image
                if use_incremental_image:
                    local_file_inc = self.get_notused_filename(local_file, '.inc')
                    command = 'qemu-img create -f qcow2 '+local_file_inc+ ' -o backing_file='+ local_file
                    self.logger.debug("command: " + command)
                    (_, _, stderr) = self.ssh_conn.exec_command(command)
                    error_msg = stderr.read()
                    if len(error_msg) > 0:
                        raise paramiko.ssh_exception.SSHException("Error creating incremental file: " + error_msg)
                    local_file = local_file_inc
                    qemu_info = {'file format':'qcow2'}
                
                server_host_files[ dev['image_id'] ] = {'source file': local_file, 'file format': qemu_info['file format']}

                dev['source file'] = local_file 
                dev['file format'] = qemu_info['file format']

            self.localinfo['server_files'][ server['uuid'] ] = server_host_files
            self.localinfo_dirty = True

        #2.5 Open vSwitch Networking Provisioning (unikernel mode only) #CLICKOS MOD
            if self.unikernel_mode:
                bridge_interfaces = server_data.get('networks', [])
                for v in bridge_interfaces:
                    #Get the brifge name
                    self.db_lock.acquire()
                    result, content = self.db.get_table(FROM='nets', SELECT=('name', 'provider',),WHERE={'uuid':v['net_id']} )
                    self.db_lock.release()
                    if result <= 0:
                        print "launch_server ERROR getting nets",result, content
                        return -1, content
                    print content
                    if content[0]['provider'][0:3] == "OVS":
                        self.create_ovs_bridge("ovim-" + content[0]['name'])

        #3 Create XML
            if self.unikernel_mode: #CLICKOS MOD
                print self.name, ": Openvim is unikernel mode\n"   #CLICKOS MOD
                print self.name, "   - Hypervisor: ", self.hypervisor, "\n   - Image Type: ", str(server_data['os_image_type'])  #CLICKOS MOD
                if self.hypervisor == "xen-unik" and str(server_data['os_image_type']) == "clickos":     #CLICKOS MOD
                    # Generate XML string for Xen/ClickOS uses.
                    result, xml = self.create_xml_srv_clickos(server_data, devices, server_metadata)         #CLICKOS MOD
                else:   #CLICKOS MOD
                    # Generate XML string for Xen/hvm machine uses.
                    result, xml = self.create_xml_xen_server(server_data, devices, server_metadata)          #CLICKOS MOD
            else:                                                                                            #CLICKOS MOD
                # Generate default XML string for KVM/QEMU uses.
                result, xml = self.create_xml_server(server_data, devices, server_metadata)  #local_file

            if result <0:
                self.logger.error("create xml server error: " + xml)
                return -2, xml
            self.logger.debug("create xml: " + xml)
            atribute = host_thread.lvirt_module.VIR_DOMAIN_START_PAUSED if paused == "yes" else 0
        #4 Start the domain
            if not rebuild: #ensures that any pending destroying server is done
                self.server_forceoff(True)
            #self.logger.debug("launching instance " + xml)
            conn.createXML(xml, atribute)
            #self.server_status[server_id] = 'PAUSED' if paused == "yes" else 'ACTIVE'

            return 0, 'Success'

        except paramiko.ssh_exception.SSHException as e:
            text = e.args[0]
            self.logger.error("launch_server id='%s' ssh Exception: %s", server_id, text)
            if "SSH session not active" in text:
                self.ssh_connect()
        except host_thread.lvirt_module.libvirtError as e:
            text = e.get_error_message()
            self.logger.error("launch_server id='%s' libvirt Exception: %s", server_id, text)
        except Exception as e:
            text = str(e)
            self.logger.error("launch_server id='%s' Exception: %s", server_id, text)
        return -1, text
    
    def update_servers_status(self):
                            # # virDomainState
                            # VIR_DOMAIN_NOSTATE = 0
                            # VIR_DOMAIN_RUNNING = 1
                            # VIR_DOMAIN_BLOCKED = 2
                            # VIR_DOMAIN_PAUSED = 3
                            # VIR_DOMAIN_SHUTDOWN = 4
                            # VIR_DOMAIN_SHUTOFF = 5
                            # VIR_DOMAIN_CRASHED = 6
                            # VIR_DOMAIN_PMSUSPENDED = 7   #TODO suspended

        if self.test or len(self.server_status)==0:
            return

        try:
            conn = host_thread.lvirt_module.open(self.lvirt_conn_uri)
            domains=  conn.listAllDomains() 
            domain_dict={}
            for domain in domains:
                uuid = domain.UUIDString() ;
                libvirt_status = domain.state()
                #print libvirt_status
                if libvirt_status[0] == host_thread.lvirt_module.VIR_DOMAIN_RUNNING or libvirt_status[0] == host_thread.lvirt_module.VIR_DOMAIN_SHUTDOWN:
                    new_status = "ACTIVE"
                elif libvirt_status[0] == host_thread.lvirt_module.VIR_DOMAIN_PAUSED:
                    new_status = "PAUSED"
                elif libvirt_status[0] == host_thread.lvirt_module.VIR_DOMAIN_SHUTOFF:
                    new_status = "INACTIVE"
                elif libvirt_status[0] == host_thread.lvirt_module.VIR_DOMAIN_CRASHED:
                    new_status = "ERROR"
                else:
                    new_status = None
                domain_dict[uuid] = new_status
            conn.close()
        except host_thread.lvirt_module.libvirtError as e:
            self.logger.error("get_state() Exception " + e.get_error_message())
            return

        for server_id, current_status in self.server_status.iteritems():
            new_status = None
            if server_id in domain_dict:
                new_status = domain_dict[server_id]
            else:
                new_status = "INACTIVE"
                            
            if new_status == None or new_status == current_status:
                continue
            if new_status == 'INACTIVE' and current_status == 'ERROR':
                continue #keep ERROR status, because obviously this machine is not running
            #change status
            self.logger.debug("server id='%s' status change from '%s' to '%s'", server_id, current_status, new_status)
            STATUS={'progress':100, 'status':new_status}
            if new_status == 'ERROR':
                STATUS['last_error'] = 'machine has crashed'
            self.db_lock.acquire()
            r,_ = self.db.update_rows('instances', STATUS, {'uuid':server_id}, log=False)
            self.db_lock.release()
            if r>=0:
                self.server_status[server_id] = new_status
                        
    def action_on_server(self, req, last_retry=True):
        '''Perform an action on a req
        Attributes:
            req: dictionary that contain:
                server properties: 'uuid','name','tenant_id','status'
                action: 'action'
                host properties: 'user', 'ip_name'
        return (error, text)  
             0: No error. VM is updated to new state,  
            -1: Invalid action, as trying to pause a PAUSED VM
            -2: Error accessing host
            -3: VM nor present
            -4: Error at DB access
            -5: Error while trying to perform action. VM is updated to ERROR
        '''
        server_id = req['uuid']
        conn = None
        new_status = None
        old_status = req['status']
        last_error = None
        
        if self.test:
            if 'terminate' in req['action']:
                new_status = 'deleted'
            elif 'shutoff' in req['action'] or 'shutdown' in req['action'] or 'forceOff' in req['action']:
                if req['status']!='ERROR':
                    time.sleep(5)
                    new_status = 'INACTIVE'
            elif 'start' in req['action']  and req['status']!='ERROR':
                new_status = 'ACTIVE'
            elif 'resume' in req['action'] and req['status']!='ERROR' and req['status']!='INACTIVE':
                new_status = 'ACTIVE'
            elif 'pause' in req['action']  and req['status']!='ERROR':
                new_status = 'PAUSED'
            elif 'reboot' in req['action'] and req['status']!='ERROR':
                new_status = 'ACTIVE'
            elif 'rebuild' in req['action']:
                time.sleep(random.randint(20,150))
                new_status = 'ACTIVE'
            elif 'createImage' in req['action']:
                time.sleep(5)
                self.create_image(None, req)
        else:
            try:
                conn = host_thread.lvirt_module.open(self.lvirt_conn_uri)
                try:
                    dom = conn.lookupByUUIDString(server_id)
                except host_thread.lvirt_module.libvirtError as e:
                    text = e.get_error_message()
                    if 'LookupByUUIDString' in text or 'Domain not found' in text or 'No existe un dominio coincidente' in text:
                        dom = None
                    else:
                        self.logger.error("action_on_server id='%s' libvirt exception: %s", server_id, text)
                        raise e
                
                if 'forceOff' in req['action']:
                    if dom == None:
                        self.logger.debug("action_on_server id='%s' domain not running", server_id)
                    else:
                        try:
                            self.logger.debug("sending DESTROY to server id='%s'", server_id)
                            dom.destroy()
                        except Exception as e:
                            if "domain is not running" not in e.get_error_message():
                                self.logger.error("action_on_server id='%s' Exception while sending force off: %s",
                                                  server_id, e.get_error_message())
                                last_error =  'action_on_server Exception while destroy: ' + e.get_error_message()
                                new_status = 'ERROR'
                
                elif 'terminate' in req['action']:
                    if dom == None:
                        self.logger.debug("action_on_server id='%s' domain not running", server_id)
                        new_status = 'deleted'
                    else:
                        try:
                            if req['action']['terminate'] == 'force':
                                self.logger.debug("sending DESTROY to server id='%s'", server_id)
                                dom.destroy()
                                new_status = 'deleted'
                            else:
                                self.logger.debug("sending SHUTDOWN to server id='%s'", server_id)
                                dom.shutdown()
                                self.pending_terminate_server.append( (time.time()+10,server_id) )
                        except Exception as e:
                            self.logger.error("action_on_server id='%s' Exception while destroy: %s",
                                              server_id, e.get_error_message())
                            last_error =  'action_on_server Exception while destroy: ' + e.get_error_message()
                            new_status = 'ERROR'
                            if "domain is not running" in e.get_error_message():
                                try:
                                    dom.undefine()
                                    new_status = 'deleted'
                                except Exception:
                                    self.logger.error("action_on_server id='%s' Exception while undefine: %s",
                                                      server_id, e.get_error_message())
                                    last_error =  'action_on_server Exception2 while undefine:', e.get_error_message()
                            #Exception: 'virDomainDetachDevice() failed'
                    if new_status=='deleted':
                        if server_id in self.server_status:
                            del self.server_status[server_id]
                        if req['uuid'] in self.localinfo['server_files']:
                            for file_ in self.localinfo['server_files'][ req['uuid'] ].values():
                                try:
                                    if self.unikernel or (self.hypervisor != "xen-unik") and (str(server_data['os_image_type']) != "clickos"):   #CLICKOS MOD
                                        self.delete_file(file_['source file'])
                                except Exception:
                                    pass
                            del self.localinfo['server_files'][ req['uuid'] ]
                            self.localinfo_dirty = True

                elif 'shutoff' in req['action'] or 'shutdown' in req['action']:
                    try:
                        if dom == None:
                            self.logger.debug("action_on_server id='%s' domain not running", server_id)
                        else: 
                            dom.shutdown()
#                        new_status = 'INACTIVE'
                        #TODO: check status for changing at database
                    except Exception as e:
                        new_status = 'ERROR'
                        self.logger.error("action_on_server id='%s' Exception while shutdown: %s",
                                          server_id, e.get_error_message())
                        last_error =  'action_on_server Exception while shutdown: ' + e.get_error_message()
    
                elif 'rebuild' in req['action']:
                    if dom != None:
                        dom.destroy()
                    r = self.launch_server(conn, req, True, None)
                    if r[0] <0:
                        new_status = 'ERROR'
                        last_error = r[1]
                    else:
                        new_status = 'ACTIVE'
                elif 'start' in req['action']:
                    # The instance is only create in DB but not yet at libvirt domain, needs to be create
                    rebuild = True if req['action']['start'] == 'rebuild'  else False
                    r = self.launch_server(conn, req, rebuild, dom)
                    if r[0] <0:
                        new_status = 'ERROR'
                        last_error = r[1]
                    else:
                        new_status = 'ACTIVE'
                
                elif 'resume' in req['action']:
                    try:
                        if dom == None:
                            pass
                        else:
                            dom.resume()
#                            new_status = 'ACTIVE'
                    except Exception as e:
                        self.logger.error("action_on_server id='%s' Exception while resume: %s",
                                          server_id, e.get_error_message())
                    
                elif 'pause' in req['action']:
                    try: 
                        if dom == None:
                            pass
                        else:
                            dom.suspend()
#                            new_status = 'PAUSED'
                    except Exception as e:
                        self.logger.error("action_on_server id='%s' Exception while pause: %s",
                                          server_id, e.get_error_message())
    
                elif 'reboot' in req['action']:
                    try: 
                        if dom == None:
                            pass
                        else:
                            dom.reboot()
                        self.logger.debug("action_on_server id='%s' reboot:", server_id)
                        #new_status = 'ACTIVE'
                    except Exception as e:
                        self.logger.error("action_on_server id='%s' Exception while reboot: %s",
                                          server_id, e.get_error_message())
                elif 'createImage' in req['action']:
                    self.create_image(dom, req)
                        
        
                conn.close()    
            except host_thread.lvirt_module.libvirtError as e:
                if conn is not None: conn.close()
                text = e.get_error_message()
                new_status = "ERROR"
                last_error = text
                if 'LookupByUUIDString' in text or 'Domain not found' in text or 'No existe un dominio coincidente' in text:
                    self.logger.debug("action_on_server id='%s' Exception removed from host", server_id)
                else:
                    self.logger.error("action_on_server id='%s' Exception %s", server_id, text)
        #end of if self.test
        if new_status ==  None:
            return 1

        self.logger.debug("action_on_server id='%s' new status=%s %s",server_id, new_status, last_error)
        UPDATE = {'progress':100, 'status':new_status}
        
        if new_status=='ERROR':
            if not last_retry:  #if there will be another retry do not update database 
                return -1 
            elif 'terminate' in req['action']:
                #PUT a log in the database
                self.logger.error("PANIC deleting server id='%s' %s", server_id, last_error)
                self.db_lock.acquire()
                self.db.new_row('logs', 
                            {'uuid':server_id, 'tenant_id':req['tenant_id'], 'related':'instances','level':'panic',
                             'description':'PANIC deleting server from host '+self.name+': '+last_error}
                        )
                self.db_lock.release()
                if server_id in self.server_status:
                    del self.server_status[server_id]
                return -1
            else:
                UPDATE['last_error'] = last_error
        if new_status != 'deleted' and (new_status != old_status or new_status == 'ERROR') :
            self.db_lock.acquire()
            self.db.update_rows('instances', UPDATE, {'uuid':server_id}, log=True)
            self.server_status[server_id] = new_status
            self.db_lock.release()
        if new_status == 'ERROR':
            return -1
        return 1
     
    
    def restore_iface(self, name, mac, lib_conn=None):
        ''' make an ifdown, ifup to restore default parameter of na interface
            Params:
                mac: mac address of the interface
                lib_conn: connection to the libvirt, if None a new connection is created
            Return 0,None if ok, -1,text if fails
        ''' 
        conn=None
        ret = 0
        error_text=None
        if self.test:
            self.logger.debug("restore_iface '%s' %s", name, mac)
            return 0, None
        try:
            if not lib_conn:
                conn = host_thread.lvirt_module.open(self.lvirt_conn_uri)
            else:
                conn = lib_conn
                
            #wait to the pending VM deletion
            #TODO.Revise  self.server_forceoff(True)

            iface = conn.interfaceLookupByMACString(mac)
            if iface.isActive():
                iface.destroy()
            iface.create()
            self.logger.debug("restore_iface '%s' %s", name, mac)
        except host_thread.lvirt_module.libvirtError as e:
            error_text = e.get_error_message()
            self.logger.error("restore_iface '%s' '%s' libvirt exception: %s", name, mac, error_text)
            ret=-1
        finally:
            if lib_conn is None and conn is not None:
                conn.close()
        return ret, error_text

        
    def create_image(self,dom, req):
        if self.test:
            if 'path' in req['action']['createImage']:
                file_dst = req['action']['createImage']['path']
            else:
                createImage=req['action']['createImage']
                img_name= createImage['source']['path']
                index=img_name.rfind('/')
                file_dst = self.get_notused_path(img_name[:index+1] + createImage['name'] + '.qcow2')
            image_status='ACTIVE'
        else:
            for retry in (0,1):
                try:
                    server_id = req['uuid']
                    createImage=req['action']['createImage']
                    file_orig = self.localinfo['server_files'][server_id] [ createImage['source']['image_id'] ] ['source file']
                    if 'path' in req['action']['createImage']:
                        file_dst = req['action']['createImage']['path']
                    else:
                        img_name= createImage['source']['path']
                        index=img_name.rfind('/')
                        file_dst = self.get_notused_filename(img_name[:index+1] + createImage['name'] + '.qcow2')
                          
                    self.copy_file(file_orig, file_dst)
                    qemu_info = self.qemu_get_info(file_orig)
                    if 'backing file' in qemu_info:
                        for k,v in self.localinfo['files'].items():
                            if v==qemu_info['backing file']:
                                self.qemu_change_backing(file_dst, k)
                                break
                    image_status='ACTIVE'
                    break
                except paramiko.ssh_exception.SSHException as e:
                    image_status='ERROR'
                    error_text = e.args[0]
                    self.logger.error("create_image id='%s' ssh Exception: %s", server_id, error_text)
                    if "SSH session not active" in error_text and retry==0:
                        self.ssh_connect()
                except Exception as e:
                    image_status='ERROR'
                    error_text = str(e)
                    self.logger.error("create_image id='%s' Exception: %s", server_id, error_text)

                #TODO insert a last_error at database
        self.db_lock.acquire()
        self.db.update_rows('images', {'status':image_status, 'progress': 100, 'path':file_dst}, 
                {'uuid':req['new_image']['uuid']}, log=True)
        self.db_lock.release()
  
    def edit_iface(self, port_id, old_net, new_net):
        #This action imply remove and insert interface to put proper parameters
        if self.test:
            time.sleep(1)
        else:
        #get iface details
            self.db_lock.acquire()
            r,c = self.db.get_table(FROM='ports as p join resources_port as rp on p.uuid=rp.port_id',
                                    WHERE={'port_id': port_id})
            self.db_lock.release()
            if r<0:
                self.logger.error("edit_iface %s DDBB error: %s", port_id, c)
                return
            elif r==0:
                self.logger.error("edit_iface %s port not found", port_id)
                return
            port=c[0]
            if port["model"]!="VF":
                self.logger.error("edit_iface %s ERROR model must be VF", port_id)
                return
            #create xml detach file
            xml=[]
            self.xml_level = 2
            xml.append("<interface type='hostdev' managed='yes'>")
            xml.append("  <mac address='" +port['mac']+ "'/>")
            xml.append("  <source>"+ self.pci2xml(port['pci'])+"\n  </source>")
            xml.append('</interface>')

            
            try:
                conn=None
                conn = host_thread.lvirt_module.open(self.lvirt_conn_uri)
                dom = conn.lookupByUUIDString(port["instance_id"])
                if old_net:
                    text="\n".join(xml)
                    self.logger.debug("edit_iface detaching SRIOV interface " + text)
                    dom.detachDeviceFlags(text, flags=host_thread.lvirt_module.VIR_DOMAIN_AFFECT_LIVE)
                if new_net:
                    xml[-1] ="  <vlan>   <tag id='" + str(port['vlan']) + "'/>   </vlan>"
                    self.xml_level = 1
                    xml.append(self.pci2xml(port.get('vpci',None)) )
                    xml.append('</interface>')                
                    text="\n".join(xml)
                    self.logger.debug("edit_iface attaching SRIOV interface " + text)
                    dom.attachDeviceFlags(text, flags=host_thread.lvirt_module.VIR_DOMAIN_AFFECT_LIVE)
                    
            except host_thread.lvirt_module.libvirtError as e:
                text = e.get_error_message()
                self.logger.error("edit_iface %s libvirt exception: %s", port["instance_id"], text)
                
            finally:
                if conn is not None: conn.close()


def create_server(server, db, db_lock, only_of_ports):
    extended = server.get('extended', None)
    requirements={}
    requirements['numa']={'memory':0, 'proc_req_type': 'threads', 'proc_req_nb':0, 'port_list':[], 'sriov_list':[]}
    requirements['ram'] = server['flavor'].get('ram', 0)
    if requirements['ram']== None:
        requirements['ram'] = 0
    requirements['vcpus'] = server['flavor'].get('vcpus', 0)
    if requirements['vcpus']== None:
        requirements['vcpus'] = 0
    #If extended is not defined get requirements from flavor
    if extended is None:
        #If extended is defined in flavor convert to dictionary and use it
        if 'extended' in server['flavor'] and  server['flavor']['extended'] != None:
            json_acceptable_string = server['flavor']['extended'].replace("'", "\"")
            extended = json.loads(json_acceptable_string)
        else:
            extended = None
    #print json.dumps(extended, indent=4)
    
    #For simplicity only one numa VM are supported in the initial implementation
    if extended != None:
        numas = extended.get('numas', [])
        if len(numas)>1:
            return (-2, "Multi-NUMA VMs are not supported yet")
        #elif len(numas)<1:
        #    return (-1, "At least one numa must be specified")
    
        #a for loop is used in order to be ready to multi-NUMA VMs
        request = []
        for numa in numas:
            numa_req = {}
            numa_req['memory'] = numa.get('memory', 0)
            if 'cores' in numa: 
                numa_req['proc_req_nb'] = numa['cores']                     #number of cores or threads to be reserved
                numa_req['proc_req_type'] = 'cores'                         #indicates whether cores or threads must be reserved
                numa_req['proc_req_list'] = numa.get('cores-id', None)      #list of ids to be assigned to the cores or threads
            elif 'paired-threads' in numa:
                numa_req['proc_req_nb'] = numa['paired-threads']
                numa_req['proc_req_type'] = 'paired-threads'
                numa_req['proc_req_list'] = numa.get('paired-threads-id', None)
            elif 'threads' in numa:
                numa_req['proc_req_nb'] = numa['threads']
                numa_req['proc_req_type'] = 'threads'
                numa_req['proc_req_list'] = numa.get('threads-id', None)
            else:
                numa_req['proc_req_nb'] = 0 # by default
                numa_req['proc_req_type'] = 'threads'

            
            
            #Generate a list of sriov and another for physical interfaces 
            interfaces = numa.get('interfaces', [])
            sriov_list = []
            port_list = []
            for iface in interfaces:
                iface['bandwidth'] = int(iface['bandwidth'])
                if iface['dedicated'][:3]=='yes':
                    port_list.append(iface)
                else:
                    sriov_list.append(iface)
                    
            #Save lists ordered from more restrictive to less bw requirements
            numa_req['sriov_list'] = sorted(sriov_list, key=lambda k: k['bandwidth'], reverse=True)
            numa_req['port_list'] = sorted(port_list, key=lambda k: k['bandwidth'], reverse=True)
            
            
            request.append(numa_req)
                
    #                 print "----------\n"+json.dumps(request[0], indent=4)
    #                 print '----------\n\n'
            
        #Search in db for an appropriate numa for each requested numa
        #at the moment multi-NUMA VMs are not supported
        if len(request)>0:
            requirements['numa'].update(request[0])
    if requirements['numa']['memory']>0:
        requirements['ram']=0  #By the moment I make incompatible ask for both Huge and non huge pages memory
    elif requirements['ram']==0:
        return (-1, "Memory information not set neither at extended field not at ram")
    if requirements['numa']['proc_req_nb']>0:
        requirements['vcpus']=0 #By the moment I make incompatible ask for both Isolated and non isolated cpus
    elif requirements['vcpus']==0:
        return (-1, "Processor information not set neither at extended field not at vcpus")    


    db_lock.acquire()
    result, content = db.get_numas(requirements, server.get('host_id', None), only_of_ports)
    db_lock.release()
    
    if result == -1:
        return (-1, content)
    
    numa_id = content['numa_id']
    host_id = content['host_id']

    #obtain threads_id and calculate pinning
    cpu_pinning = []
    reserved_threads=[]
    if requirements['numa']['proc_req_nb']>0:
        db_lock.acquire()
        result, content = db.get_table(FROM='resources_core', 
                                       SELECT=('id','core_id','thread_id'),
                                       WHERE={'numa_id':numa_id,'instance_id': None, 'status':'ok'} )
        db_lock.release()
        if result <= 0:
            #print content
            return -1, content
    
        #convert rows to a dictionary indexed by core_id
        cores_dict = {}
        for row in content:
            if not row['core_id'] in cores_dict:
                cores_dict[row['core_id']] = []
            cores_dict[row['core_id']].append([row['thread_id'],row['id']]) 
           
        #In case full cores are requested 
        paired = 'N'
        if requirements['numa']['proc_req_type'] == 'cores':
            #Get/create the list of the vcpu_ids
            vcpu_id_list = requirements['numa']['proc_req_list']
            if vcpu_id_list == None:
                vcpu_id_list = range(0,int(requirements['numa']['proc_req_nb']))
            
            for threads in cores_dict.itervalues():
                #we need full cores
                if len(threads) != 2:
                    continue
                
                #set pinning for the first thread
                cpu_pinning.append( [ vcpu_id_list.pop(0), threads[0][0], threads[0][1] ] )
                
                #reserve so it is not used the second thread
                reserved_threads.append(threads[1][1])
                
                if len(vcpu_id_list) == 0:
                    break
                
        #In case paired threads are requested
        elif requirements['numa']['proc_req_type'] == 'paired-threads':
            paired = 'Y'
            #Get/create the list of the vcpu_ids
            if requirements['numa']['proc_req_list'] != None:
                vcpu_id_list = []
                for pair in requirements['numa']['proc_req_list']:
                    if len(pair)!=2:
                        return -1, "Field paired-threads-id not properly specified"
                        return
                    vcpu_id_list.append(pair[0])
                    vcpu_id_list.append(pair[1])
            else:
                vcpu_id_list = range(0,2*int(requirements['numa']['proc_req_nb']))
                
            for threads in cores_dict.itervalues():
                #we need full cores
                if len(threads) != 2:
                    continue
                #set pinning for the first thread
                cpu_pinning.append([vcpu_id_list.pop(0), threads[0][0], threads[0][1]])
                
                #set pinning for the second thread
                cpu_pinning.append([vcpu_id_list.pop(0), threads[1][0], threads[1][1]])
                
                if len(vcpu_id_list) == 0:
                    break    
        
        #In case normal threads are requested
        elif requirements['numa']['proc_req_type'] == 'threads':
            #Get/create the list of the vcpu_ids
            vcpu_id_list = requirements['numa']['proc_req_list']
            if vcpu_id_list == None:
                vcpu_id_list = range(0,int(requirements['numa']['proc_req_nb']))
                                
            for threads_index in sorted(cores_dict, key=lambda k: len(cores_dict[k])):
                threads = cores_dict[threads_index]
                #set pinning for the first thread
                cpu_pinning.append([vcpu_id_list.pop(0), threads[0][0], threads[0][1]])
                
                #if exists, set pinning for the second thread
                if len(threads) == 2 and len(vcpu_id_list) != 0:
                    cpu_pinning.append([vcpu_id_list.pop(0), threads[1][0], threads[1][1]])
                
                if len(vcpu_id_list) == 0:
                    break    
    
        #Get the source pci addresses for the selected numa
        used_sriov_ports = []
        for port in requirements['numa']['sriov_list']:
            db_lock.acquire()
            result, content = db.get_table(FROM='resources_port', SELECT=('id', 'pci', 'mac'),WHERE={'numa_id':numa_id,'root_id': port['port_id'], 'port_id': None, 'Mbps_used': 0} )
            db_lock.release()
            if result <= 0:
                #print content
                return -1, content
            for row in content:
                if row['id'] in used_sriov_ports or row['id']==port['port_id']:
                    continue
                port['pci'] = row['pci']
                if 'mac_address' not in port: 
                    port['mac_address'] = row['mac']
                del port['mac']
                port['port_id']=row['id']
                port['Mbps_used'] = port['bandwidth']
                used_sriov_ports.append(row['id'])
                break
        
        for port in requirements['numa']['port_list']:
            port['Mbps_used'] = None
            if port['dedicated'] != "yes:sriov":
                port['mac_address'] = port['mac']
                del port['mac']
                continue
            db_lock.acquire()
            result, content = db.get_table(FROM='resources_port', SELECT=('id', 'pci', 'mac', 'Mbps'),WHERE={'numa_id':numa_id,'root_id': port['port_id'], 'port_id': None, 'Mbps_used': 0} )
            db_lock.release()
            if result <= 0:
                #print content
                return -1, content
            port['Mbps_used'] = content[0]['Mbps']
            for row in content:
                if row['id'] in used_sriov_ports or row['id']==port['port_id']:
                    continue
                port['pci'] = row['pci']
                if 'mac_address' not in port: 
                    port['mac_address'] = row['mac']  # mac cannot be set to passthrough ports 
                del port['mac']
                port['port_id']=row['id']
                used_sriov_ports.append(row['id'])
                break
    
    #             print '2. Physical ports assignation:'+json.dumps(requirements['port_list'], indent=4)
    #             print '2. SR-IOV assignation:'+json.dumps(requirements['sriov_list'], indent=4)
        
    server['host_id'] = host_id

    #Generate dictionary for saving in db the instance resources
    resources = {}
    resources['bridged-ifaces'] = []
    
    numa_dict = {}
    numa_dict['interfaces'] = []
    
    numa_dict['interfaces'] += requirements['numa']['port_list']
    numa_dict['interfaces'] += requirements['numa']['sriov_list']
  
    #Check bridge information
    unified_dataplane_iface=[]
    unified_dataplane_iface += requirements['numa']['port_list']
    unified_dataplane_iface += requirements['numa']['sriov_list']
    
    for control_iface in server.get('networks', []):
        control_iface['net_id']=control_iface.pop('uuid')
        #Get the brifge name
        db_lock.acquire()
        result, content = db.get_table(FROM='nets',
                                       SELECT=('name', 'type', 'vlan', 'provider', 'enable_dhcp',
                                                 'dhcp_first_ip', 'dhcp_last_ip', 'cidr'),
                                       WHERE={'uuid': control_iface['net_id']})
        db_lock.release()
        if result < 0: 
            pass
        elif result==0:
            return -1, "Error at field netwoks: Not found any network wit uuid %s" % control_iface['net_id']
        else:
            network=content[0]
            if control_iface.get("type", 'virtual') == 'virtual':
                if network['type']!='bridge_data' and network['type']!='bridge_man':
                    return -1, "Error at field netwoks: network uuid %s for control interface is not of type bridge_man or bridge_data" % control_iface['net_id']
                resources['bridged-ifaces'].append(control_iface)
                if network.get("provider") and network["provider"][0:3] == "OVS":
                    control_iface["type"] = "instance:ovs"
                else:
                    control_iface["type"] = "instance:bridge"
                if network.get("vlan"):
                    control_iface["vlan"] = network["vlan"]

                if network.get("enable_dhcp") == 'true':
                    control_iface["enable_dhcp"] = network.get("enable_dhcp")
                    control_iface["dhcp_first_ip"] = network["dhcp_first_ip"]
                    control_iface["dhcp_last_ip"] = network["dhcp_last_ip"]
                    control_iface["cidr"] = network["cidr"]
            else:
                if network['type']!='data' and network['type']!='ptp':
                    return -1, "Error at field netwoks: network uuid %s for dataplane interface is not of type data or ptp" % control_iface['net_id']
                #dataplane interface, look for it in the numa tree and asign this network
                iface_found=False
                for dataplane_iface in numa_dict['interfaces']:
                    if dataplane_iface['name'] == control_iface.get("name"):
                        if (dataplane_iface['dedicated'] == "yes" and control_iface["type"] != "PF") or \
                            (dataplane_iface['dedicated'] == "no" and control_iface["type"] != "VF") or \
                            (dataplane_iface['dedicated'] == "yes:sriov" and control_iface["type"] != "VFnotShared") :
                                return -1, "Error at field netwoks: mismatch at interface '%s' from flavor 'dedicated=%s' and networks 'type=%s'" % \
                                    (control_iface.get("name"), dataplane_iface['dedicated'], control_iface["type"])
                        dataplane_iface['uuid'] = control_iface['net_id']
                        if dataplane_iface['dedicated'] == "no":
                            dataplane_iface['vlan'] = network['vlan']
                        if dataplane_iface['dedicated'] != "yes" and control_iface.get("mac_address"):
                            dataplane_iface['mac_address'] = control_iface.get("mac_address")
                        if control_iface.get("vpci"):
                            dataplane_iface['vpci'] = control_iface.get("vpci")
                        iface_found=True
                        break
                if not iface_found:
                    return -1, "Error at field netwoks: interface name %s from network not found at flavor" % control_iface.get("name")
        
    resources['host_id'] = host_id
    resources['image_id'] = server['image_id']
    resources['flavor_id'] = server['flavor_id']
    resources['tenant_id'] = server['tenant_id']
    resources['ram'] = requirements['ram']
    resources['vcpus'] = requirements['vcpus']
    resources['status'] = 'CREATING'
    
    if 'description' in server: resources['description'] = server['description']
    if 'name' in server: resources['name'] = server['name']
    if 'hypervisor' in server: resources['hypervisor'] = server['hypervisor']             # CLICKOS MOD
    if 'os_image_type' in server: resources['os_image_type'] = server['os_image_type']    # CLICKOS MOD
    
    resources['extended'] = {}                          #optional
    resources['extended']['numas'] = []
    numa_dict['numa_id'] = numa_id
    numa_dict['memory'] = requirements['numa']['memory']
    numa_dict['cores'] = []

    for core in cpu_pinning:
        numa_dict['cores'].append({'id': core[2], 'vthread': core[0], 'paired': paired})
    for core in reserved_threads:
        numa_dict['cores'].append({'id': core})
    resources['extended']['numas'].append(numa_dict)
    if extended!=None and 'devices' in extended:   #TODO allow extra devices without numa
        resources['extended']['devices'] = extended['devices']
    

    # '===================================={'
    #print json.dumps(resources, indent=4)
    #print '====================================}'
    
    return 0, resources

