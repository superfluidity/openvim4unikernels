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

from charms.reactive import hook
from charms.reactive import RelationBase
from charms.reactive import scopes


class OpenVimRequires(RelationBase):
    scope = scopes.UNIT

    @hook('{requires:openvim}-relation-{joined,changed}')
    def changed(self):
        conv = self.conversation()
        if conv.get_remote('port'):
            # this unit's conversation has a port, so
            # it is part of the set of available units
            conv.set_state('{relation_name}.available')

    @hook('{requires:openvim}-relation-{departed,broken}')
    def broken(self):
        conv = self.conversation()
        conv.remove_state('{relation_name}.available')

    def services(self):
        """
        Returns a list of available openvim services and their associated hosts
        and ports.

        The return value is a list of dicts of the following form::

            [
                {
                    'service_name': name_of_service,
                    'hosts': [
                        {
                            'hostname': address_of_host,
                            'port': port_for_host,
                            'user': user_for_host,
                        },
                        # ...
                    ],
                },
                # ...
            ]
        """
        services = {}
        for conv in self.conversations():
            service_name = conv.scope.split('/')[0]
            service = services.setdefault(service_name, {
                'service_name': service_name,
                'hosts': [],
            })
            host = conv.get_remote('hostname') or \
                conv.get_remote('private-address')
            port = conv.get_remote('port')
            user = conv.get_remote('user')
            if host and port:
                service['hosts'].append({
                    'hostname': host,
                    'port': port,
                    'user': user,
                })
        return [s for s in services.values() if s['hosts']]
