#!/bin/bash

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

#ONLY TESTED for Ubuntu 16.04
#it configures openvim to run as a service

function usage(){
    echo -e "usage: sudo $0 [OPTIONS]"
    echo -e "Configures openvim to run as a service at /opt"
    echo -e "  OPTIONS"
    echo -e "     -u USER_OWNER  user owner of the service, 'root' by default"
    echo -e "     -f PATH  path where openvim source is located. If missing it is downloaded from git"
    echo -e "     -d --delete:  if -f is provided, delete this path after copying to /opt"
    echo -e "     -h:  show this help"
    echo -e "     --uninstall: remove created service and files"
}

function uninstall(){
    echo "systemctl disable openvim.service " &&  systemctl disable openvim.service 2>/dev/null || echo "  Already done"
    echo "service openvim stop " && service openvim stop 2>/dev/null || echo "  Already done"
    for file in /opt/openvim /etc/default/openvimd.cfg /var/log/openvim /etc/systemd/system/openvim.service /usr/bin/openvim /usr/bin/initopenvim /usr/sbin/service-openvim /usr/bin/openvim-report
    do
        rm -rf $file || ! echo "Can not delete '$file'. Needed root privileges?" >&2 || exit 1
    done
    echo "Done"
}

BAD_PATH_ERROR="Path '$FILE' does not contain a valid openvim distribution"
GIT_URL=https://osm.etsi.org/gerrit/osm/openvim.git
USER_OWNER="root"
QUIET_MODE=""
FILE=""
DELETE=""
while getopts ":u:f:hdq-:" o; do
    case "${o}" in
        u)
            export USER_OWNER="$OPTARG"
            ;;
        f)
            export FILE="$OPTARG"
            ;;
        q)
            export QUIET_MODE=yes
            ;;
        h)
            usage && exit 0
            ;;
        d)
            DELETE=y
            ;;
        -)
            [ "${OPTARG}" == "help" ] && usage && exit 0
            [ "${OPTARG}" == "uninstall" ] && uninstall && exit 0
            [ "${OPTARG}" == "delete" ] && DELETE=y && continue
            echo -e "Invalid option: '--$OPTARG'\nTry $0 --help for more information" >&2
            exit 1
            ;; 
        \?)
            echo -e "Invalid option: '-$OPTARG'\nTry $0 --help for more information" >&2
            exit 1
            ;;
        :)
            echo -e "Option '-$OPTARG' requires an argument\nTry $0 --help for more information" >&2
            exit 1
            ;;
        *)
            usage >&2
            exit -1
            ;;
    esac
done
BAD_PATH_ERROR="Path '$FILE' does not contain a valid openvim distribution"

#check root privileges
[ "$USER" != "root" ] && echo "Needed root privileges" >&2 && exit 1

#Discover Linux distribution
#try redhat type
if [[ -f /etc/redhat-release ]]
then 
    _DISTRO=$(cat /etc/redhat-release 2>/dev/null | cut  -d" " -f1)
else 
    #if not assuming ubuntu type
    _DISTRO=$(lsb_release -is  2>/dev/null)
fi            
if [[ "$_DISTRO" == "Ubuntu" ]]
then
    _RELEASE=$(lsb_release -rs)
    if [[ ${_RELEASE%%.*} != 16 ]] 
    then 
        echo "Only tested in Ubuntu Server 16.04" >&2 && exit 1
    fi
else
    echo "Only tested in Ubuntu Server 16.04" >&2 && exit 1
fi


if [[ -z $FILE ]]
then
    FILE=__temp__${RANDOM}
    git clone $GIT_URL $FILE || ! echo "Cannot get openvim source code from $GIT_URL" >&2 || exit 1
    DELETE=y
    #git checkout <tag version>
else
    [[ -d  "$FILE" ]] || ! echo $BAD_PATH_ERROR >&2 || exit 1
fi

#make idenpotent
uninstall
#copy files
cp -r "$FILE" /opt/openvim         || ! echo $BAD_PATH_ERROR >&2 || exit 1
mkdir -p /opt/openvim/logs
#makes links
ln -s -v /opt/openvim/openvimd.cfg /etc/default/openvimd.cfg  || echo "warning cannot create link '/etc/default/openvimd.cfg'"
ln -s -v /opt/openvim/logs /var/log/openvim  || echo "warning cannot create link '/var/log/openvim'"
ln -s -v /opt/openvim/openvim /usr/bin/openvim
ln -s -v /opt/openvim/scripts/service-openvim.sh /usr/sbin/service-openvim
ln -s -v /opt/openvim/scripts/openvim-report.sh /usr/bin/openvim-report
ln -s -v /opt/openvim/scripts/initopenvim.sh /usr/bin/initopenvim

chown -R $SUDO_USER /opt/openvim

mkdir -p /etc/systemd/system/
cat  > /etc/systemd/system/openvim.service  << EOF 
[Unit]
Description=openvim server

[Service]
User=${USER_OWNER}
ExecStart=/opt/openvim/openvimd.py -c /opt/openvim/openvimd.cfg --log-file=/opt/openvim/logs/openvim.log
Restart=always

[Install]
WantedBy=multi-user.target
EOF

[[ -n $DELETE ]] && rm -rf $FILE

service openvim start
systemctl enable openvim.service

echo Done
exit
