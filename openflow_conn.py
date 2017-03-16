# -*- coding: utf-8 -*-

##
# Copyright 2015 Telefónica Investigación y Desarrollo, S.A.U.
# This file is part of openmano
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
import logging
import base64

"""
vimconn implement an Abstract class for the vim connector plugins
 with the definition of the method to be implemented.
"""
__author__ = "Alfonso Tierno, Leonardo Mirabal"
__date__ = "$16-oct-2015 11:09:29$"



# Error variables
HTTP_Bad_Request = 400
HTTP_Unauthorized = 401
HTTP_Not_Found = 404
HTTP_Method_Not_Allowed = 405
HTTP_Request_Timeout = 408
HTTP_Conflict = 409
HTTP_Not_Implemented = 501
HTTP_Service_Unavailable = 503
HTTP_Internal_Server_Error = 500


class OpenflowconnException(Exception):
    """Common and base class Exception for all vimconnector exceptions"""
    def __init__(self, message, http_code=HTTP_Bad_Request):
        Exception.__init__(self, message)
        self.http_code = http_code


class OpenflowconnConnectionException(OpenflowconnException):
    """Connectivity error with the VIM"""
    def __init__(self, message, http_code=HTTP_Service_Unavailable):
        OpenflowconnException.__init__(self, message, http_code)


class OpenflowconnUnexpectedResponse(OpenflowconnException):
    """Get an wrong response from VIM"""
    def __init__(self, message, http_code=HTTP_Internal_Server_Error):
        OpenflowconnException.__init__(self, message, http_code)


class OpenflowconnAuthException(OpenflowconnException):
    """Invalid credentials or authorization to perform this action over the VIM"""
    def __init__(self, message, http_code=HTTP_Unauthorized):
        OpenflowconnException.__init__(self, message, http_code)


class OpenflowconnNotFoundException(OpenflowconnException):
    """The item is not found at VIM"""
    def __init__(self, message, http_code=HTTP_Not_Found):
        OpenflowconnException.__init__(self, message, http_code)


class OpenflowconnConflictException(OpenflowconnException):
    """There is a conflict, e.g. more item found than one"""
    def __init__(self, message, http_code=HTTP_Conflict):
        OpenflowconnException.__init__(self, message, http_code)


class OpenflowconnNotSupportedException(OpenflowconnException):
    """The request is not supported by connector"""
    def __init__(self, message, http_code=HTTP_Service_Unavailable):
        OpenflowconnException.__init__(self, message, http_code)


class OpenflowconnNotImplemented(OpenflowconnException):
    """The method is not implemented by the connected"""
    def __init__(self, message, http_code=HTTP_Not_Implemented):
        OpenflowconnException.__init__(self, message, http_code)


class OpenflowConn:
    """
    Openflow controller connector abstract implementeation.
    """
    def __init__(self, params):
        self.name = "openflow_conector"
        self.headers = {'content-type': 'application/json', 'Accept': 'application/json'}
        self.auth = None
        self.pp2ofi = {}  # From Physical Port to OpenFlow Index
        self.ofi2pp = {}  # From OpenFlow Index to Physical Port
        self.dpid = '00:01:02:03:04:05:06:07'
        self.id = 'openflow:00:01:02:03:04:05:06:07'
        self.rules = {}
        self.url = "http://%s:%s" % ('localhost', str(8081))
        self.auth = base64.b64encode('of_user:of_password')
        self.headers['Authorization'] = 'Basic ' + self.auth
        self.logger = logging.getLogger('openflow_conn')
        self.logger.setLevel(getattr(logging, params.get("of_debug", "ERROR")))
        self.ip_address = None

    def get_of_switches(self):
        """"
        Obtain a a list of switches or DPID detected by this controller
        :return: list length, and a list where each element a tuple pair (DPID, IP address), text_error: if fails
        """
        raise OpenflowconnNotImplemented("Should have implemented this")

    def obtain_port_correspondence(self):
        """
        Obtain the correspondence between physical and openflow port names
        :return: dictionary: with physical name as key, openflow name as value, error_text: if fails
        """
        raise OpenflowconnNotImplemented("Should have implemented this")

    def get_of_rules(self, translate_of_ports=True):
        """
        Obtain the rules inserted at openflow controller
        :param translate_of_ports: if True it translates ports from openflow index to physical switch name
        :return: dict if ok: with the rule name as key and value is another dictionary with the following content:
                    priority: rule priority
                    name:         rule name (present also as the master dict key)
                    ingress_port: match input port of the rule
                    dst_mac:      match destination mac address of the rule, can be missing or None if not apply
                    vlan_id:      match vlan tag of the rule, can be missing or None if not apply
                    actions:      list of actions, composed by a pair tuples:
                        (vlan, None/int): for stripping/setting a vlan tag
                        (out, port):      send to this port
                    switch:       DPID, all
                 text_error if fails
        """
        raise OpenflowconnNotImplemented("Should have implemented this")

    def del_flow(self, flow_name):
        """
        Delete all existing rules
        :param flow_name: flow_name, this is the rule name
        :return: None if ok, text_error if fails
        """
        raise OpenflowconnNotImplemented("Should have implemented this")

    def new_flow(self, data):
        """
        Insert a new static rule
        :param data: dictionary with the following content:
                priority:     rule priority
                name:         rule name
                ingress_port: match input port of the rule
                dst_mac:      match destination mac address of the rule, missing or None if not apply
                vlan_id:      match vlan tag of the rule, missing or None if not apply
                actions:      list of actions, composed by a pair tuples with these posibilities:
                    ('vlan', None/int): for stripping/setting a vlan tag
                    ('out', port):      send to this port
        :return: None if ok, text_error if fails
        """
        raise OpenflowconnNotImplemented("Should have implemented this")

    def clear_all_flows(self):
        """"
        Delete all existing rules
        :return: None if ok, text_error if fails
        """
        raise OpenflowconnNotImplemented("Should have implemented this")


class OfTestConnector(OpenflowConn):
    """
    This is a fake openflow connector for testing.
    It does nothing and it is used for running openvim without an openflow controller
    """

    def __init__(self, params):
        OpenflowConn.__init__(self, params)

        name = params.get("name", "test-ofc")
        self.name = name
        self.dpid = params.get("dpid")
        self.rules = {}
        self.logger = logging.getLogger('vim.OF.TEST')
        self.logger.setLevel(getattr(logging, params.get("of_debug", "ERROR")))
        self.pp2ofi = {}

    def get_of_switches(self):
        return ()

    def obtain_port_correspondence(self):
        return ()

    def del_flow(self, flow_name):
        if flow_name in self.rules:
            self.logger.debug("del_flow OK")
            del self.rules[flow_name]
            return None
        else:
            self.logger.warning("del_flow not found")
            raise OpenflowconnUnexpectedResponse("flow {} not found".format(flow_name))

    def new_flow(self, data):
        self.rules[data["name"]] = data
        self.logger.debug("new_flow OK")
        return None

    def get_of_rules(self, translate_of_ports=True):
        return self.rules

    def clear_all_flows(self):
        self.logger.debug("clear_all_flows OK")
        self.rules = {}
        return None
