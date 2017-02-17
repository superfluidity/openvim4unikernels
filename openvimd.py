#!/usr/bin/env python
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
This is the main program of openvim, it reads the configuration 
and launches the rest of threads: http clients, openflow controller
and host controllers  
'''

__author__ = "Alfonso Tierno"
__date__ = "$10-jul-2014 12:07:15$"
__version__ = "0.5.5-r522"
version_date = "Feb 2017"
database_version = "0.12"      #expected database schema version

import httpserver
import auxiliary_functions as af
import sys
import getopt
import time
import yaml
import os
from jsonschema import validate as js_v, exceptions as js_e
from vim_schema import config_schema
import logging
import logging.handlers as log_handlers
import socket
import ovim

global config_dic
global logger
logger = logging.getLogger('vim')

class LoadConfigurationException(Exception):
    pass

def load_configuration(configuration_file):
    default_tokens ={'http_port':9080, 'http_host':'localhost', 
                     'of_controller_nets_with_same_vlan':True,
                     'image_path':'/opt/VNF/images',
                     'network_vlan_range_start':1000,
                     'network_vlan_range_end': 4096,
                     'log_level': "DEBUG",
                     'log_level_db': "ERROR",
                     'log_level_of': 'ERROR',
                     'bridge_ifaces': {},
                     'network_type': 'ovs',
                     'ovs_controller_user': 'osm_dhcp',
                     'ovs_controller_file_path': '/var/lib/',
            }
    try:
        #First load configuration from configuration file
        #Check config file exists
        if not os.path.isfile(configuration_file):
            return (False, "Configuration file '"+configuration_file+"' does not exists")
            
        #Read and parse file
        (return_status, code) = af.read_file(configuration_file)
        if not return_status:
            return (return_status, "Error loading configuration file '"+configuration_file+"': "+code)
        try:
            config = yaml.load(code)
        except yaml.YAMLError, exc:
            error_pos = ""
            if hasattr(exc, 'problem_mark'):
                mark = exc.problem_mark
                error_pos = " at position: (%s:%s)" % (mark.line+1, mark.column+1)
            return (False, "Error loading configuration file '"+configuration_file+"'"+error_pos+": content format error: Failed to parse yaml format")
        
        
        try:
            js_v(config, config_schema)
        except js_e.ValidationError, exc:
            error_pos = ""
            if len(exc.path)>0: error_pos=" at '" + ":".join(map(str, exc.path))+"'"
            return False, "Error loading configuration file '"+configuration_file+"'"+error_pos+": "+exc.message 
        
        
        #Check default values tokens
        for k,v in default_tokens.items():
            if k not in config: config[k]=v
        #Check vlan ranges
        if config["network_vlan_range_start"]+10 >= config["network_vlan_range_end"]:
            return False, "Error invalid network_vlan_range less than 10 elements"
    
    except Exception,e:
        return (False, "Error loading configuration file '"+configuration_file+"': "+str(e))
    return (True, config)

def usage():
    print "Usage: ", sys.argv[0], "[options]"
    print "      -v|--version: prints current version"
    print "      -c|--config FILE: loads the configuration file (default: openvimd.cfg)"
    print "      -h|--help: shows this help"
    print "      -p|--port PORT: changes port number and overrides the port number in the configuration file (default: 908)"
    print "      -P|--adminport PORT: changes admin port number and overrides the port number in the configuration file (default: not listen)"
    print "      --dbname NAME: changes db_name and overrides the db_name in the configuration file"
    #print( "      --log-socket-host HOST: send logs to this host")
    #print( "      --log-socket-port PORT: send logs using this port (default: 9022)")
    print( "      --log-file FILE: send logs to this file")
    return


if __name__=="__main__":
    hostname = socket.gethostname()
    #streamformat = "%(levelname)s (%(module)s:%(lineno)d) %(message)s"
    log_formatter_complete = logging.Formatter(
        '%(asctime)s.%(msecs)03d00Z[{host}@openmanod] %(filename)s:%(lineno)s severity:%(levelname)s logger:%(name)s log:%(message)s'.format(host=hostname),
        datefmt='%Y-%m-%dT%H:%M:%S',
    )
    log_format_simple =  "%(asctime)s %(levelname)s  %(name)s %(filename)s:%(lineno)s %(message)s"
    log_formatter_simple = logging.Formatter(log_format_simple, datefmt='%Y-%m-%dT%H:%M:%S')
    logging.basicConfig(format=log_format_simple, level= logging.DEBUG)
    logger = logging.getLogger('openvim')
    logger.setLevel(logging.DEBUG)
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hvc:p:P:", ["config=", "help", "version", "port=", "adminport=", "log-file=", "dbname="])
    except getopt.GetoptError, err:
        # print help information and exit:
        logger.error("%s. Type -h for help", err) # will print something like "option -a not recognized"
        #usage()
        sys.exit(-2)

    port=None
    port_admin = None
    config_file = 'openvimd.cfg'
    log_file = None
    db_name = None

    for o, a in opts:
        if o in ("-v", "--version"):
            print "openvimd version", __version__, version_date
            print "(c) Copyright Telefonica"
            sys.exit(0)
        elif o in ("-h", "--help"):
            usage()
            sys.exit(0)
        elif o in ("-c", "--config"):
            config_file = a
        elif o in ("-p", "--port"):
            port = a
        elif o in ("-P", "--adminport"):
            port_admin = a
        elif o in ("-P", "--dbname"):
            db_name = a
        elif o == "--log-file":
            log_file = a
        else:
            assert False, "Unhandled option"

    
    engine = None
    http_thread = None
    http_thread_admin = None

    try:
        #Load configuration file
        r, config_dic = load_configuration(config_file)
        #print config_dic
        if not r:
            logger.error(config_dic)
            config_dic={}
            exit(-1)
        if log_file:
            try:
                file_handler= logging.handlers.RotatingFileHandler(log_file, maxBytes=100e6, backupCount=9, delay=0)
                file_handler.setFormatter(log_formatter_simple)
                logger.addHandler(file_handler)
                #logger.debug("moving logs to '%s'", global_config["log_file"])
                #remove initial stream handler
                logging.root.removeHandler(logging.root.handlers[0])
                print ("logging on '{}'".format(log_file))
            except IOError as e:
                raise LoadConfigurationException("Cannot open logging file '{}': {}. Check folder exist and permissions".format(log_file, str(e)) ) 

        logger.setLevel(getattr(logging, config_dic['log_level']))
        logger.critical("Starting openvim server command: '%s'", sys.argv[0])
        #override parameters obtained by command line
        if port: 
            config_dic['http_port'] = port
        if port_admin:
            config_dic['http_admin_port'] = port_admin
        if db_name: 
            config_dic['db_name'] = db_name
        
        #check mode
        if 'mode' not in config_dic:
            config_dic['mode'] = 'normal'
            #allow backward compatibility of test_mode option
            if 'test_mode' in config_dic and config_dic['test_mode']==True:
                config_dic['mode'] = 'test' 
        if config_dic['mode'] == 'development' and config_dic['network_type'] == 'bridge' and \
                ( 'development_bridge' not in config_dic or config_dic['development_bridge'] not in config_dic.get("bridge_ifaces",None) ):
            logger.error("'%s' is not a valid 'development_bridge', not one of the 'bridge_ifaces'", config_file)
            exit(-1)

        if config_dic['mode'] != 'normal':
            print '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
            print "!! Warning, openvimd in TEST mode '%s'" % config_dic['mode']
            print '!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!'
        config_dic['version'] = __version__

        config_dic["database_version"] = database_version
        config_dic["logger_name"] = "openvim"

        engine = ovim.ovim(config_dic)
        engine.start_service()

        
    #Create thread to listen to web requests
        http_thread = httpserver.httpserver(engine, 'http', config_dic['http_host'], config_dic['http_port'], False, config_dic)
        http_thread.start()
        
        if 'http_admin_port' in config_dic:
            engine2 = ovim.ovim(config_dic)
            http_thread_admin = httpserver.httpserver(engine2, 'http-admin', config_dic['http_host'], config_dic['http_admin_port'], True)
            http_thread_admin.start()
        else:
            http_thread_admin = None
        time.sleep(1)      
        logger.info('Waiting for http clients')
        print ('openvimd ready')
        print ('====================')
        sys.stdout.flush()
        
        #TODO: Interactive console would be nice here instead of join or sleep
        
        r="help" #force print help at the beginning
        while True:
            if r=='exit':
                break      
            elif r!='':
                print "type 'exit' for terminate"
            r = raw_input('> ')

    except (KeyboardInterrupt, SystemExit):
        pass
    except SystemExit:
        pass
    except getopt.GetoptError as e:
        logger.critical(str(e)) # will print something like "option -a not recognized"
        #usage()
        exit(-1)
    except LoadConfigurationException as e:
        logger.critical(str(e))
        exit(-1)
    except ovim.ovimException as e:
        logger.critical(str(e))
        exit(-1)

    logger.info('Exiting openvimd')
    if engine:
        engine.stop_service()
    if http_thread:
        http_thread.join(1)
    if http_thread_admin:
        http_thread_admin.join(1)

    logger.debug( "bye!")
    exit()

