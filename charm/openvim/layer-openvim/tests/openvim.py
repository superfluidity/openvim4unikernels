##
# Copyright 2016
# This file is part of openvim
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
##

import requests
import json

class Connection(object):
    def __init__(self, base_url):
        self.base_url = base_url

    def set_active_tenant(self, tenant):
        self.tenant_id = tenant["id"]

    def get_tenants(self):
        return self._http_get("tenants")["tenants"]

    def get_hosts(self):
        return self._http_get("hosts")["hosts"]

    def get_networks(self):
        return self._http_get("networks")["networks"]

    def get_images(self):
        return self._http_get(self.tenant_id + "/images")["images"]

    def get_flavors(self):
        return self._http_get(self.tenant_id + "/flavors")["flavors"]

    def create_server(self, name, description, image, flavor, networks):
        request_data = {"server": {
            "name": name,
            "description": description,
            "imageRef": image["id"],
            "flavorRef": flavor["id"],
            "networks": [
                {"name": n["name"], "uuid": n["id"]}
                for n in networks
            ]
        }}

        path = self.tenant_id + "/servers"
        return self._http_post(path, request_data)

    def _http_get(self, path):
        response = requests.get(self.base_url + path)
        assert response.status_code == 200
        return response.json()

    def _http_post(self, path, request_data):
        data = json.dumps(request_data)
        headers = {"content-type": "application/json"}
        response = requests.post(self.base_url + path, data=data, headers=headers)
        assert response.status_code == 200
        return response.json()

def connect(host, port=9080):
    base_url = "http://%s:%s/openvim/" % (host, port)
    return Connection(base_url)
