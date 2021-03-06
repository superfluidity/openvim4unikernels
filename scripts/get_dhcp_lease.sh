#!/bin/bash
##
# Copyright 2016 Telefónica Investigación y Desarrollo, S.A.U.
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

if [ -e /var/lib/dhcp/dhcpd.leases ]
then 
	awk '
	($1=="lease" && $3=="{"){ lease=$2; active="no"; found="no" }
	($1=="binding" && $2=="state" && $3=="active;"){ active="yes" }
	($1=="hardware" && $2=="ethernet" && $3==tolower("'$1';")){ found="yes" }
	($1=="client-hostname"){ name=$2 }
	($1=="}"){ if (active=="yes" && found=="yes"){ target_lease=lease; target_name=name}}
	END{printf("%s", target_lease)} #print target_name
	' /var/lib/dhcp/dhcpd.leases
elif [ -e /var/lib/lxd-bridge/dnsmasq.lxdbr0.leases ]
then
	awk '
	($2=="'$1'"){ lease=$3; name=$4}
	END{printf("%s", lease)} 
	' /var/lib/lxd-bridge/dnsmasq.lxdbr0.leases
fi
