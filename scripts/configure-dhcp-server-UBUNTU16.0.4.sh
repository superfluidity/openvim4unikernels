#!/bin/bash
##
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
# Authors: Leonardo Mirabal
# February 2017



function _usage(){
    echo -e "Usage: sudo $0  <user-name>  "
    echo -e "  Configure dhcp server for VIM usage. (version 1.0). Params:"
    echo -e "     <user-name> Create if not exist and configure this user for openvim to connect"
    echo -e "     -h --help    this help"
    exit 1
}

function _install_packages_dependencies()
{
    # Required packages by openvim
    apt-get -y update
    apt-get -y install   ethtool build-essential dnsmasq openvswitch-switch
    echo "Remove unneeded packages....."
    apt-get -y autoremove
}

function _add_user_to_visudo()
{
# Allow admin users to access without password
if ! grep -q "#openmano" /etc/sudoers
then
    cat >> /home/${option_user}/script_visudo.sh << EOL
#!/bin/bash
echo "#openmano allow to group admin to grant root privileges without password" >> \$1
echo "${option_user} ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers
EOL
    chmod +x /home/${option_user}/script_visudo.sh
    echo "allowing admin user to get root privileges withut password"
    export EDITOR=/home/${option_user}/script_visudo.sh && sudo -E visudo
    rm -f /home/${option_user}/script_visudo.sh
fi

}

function _create_ovs_controller_config_path() {
    mkdir -p '/var/lib/openvim'
}

function _install_user() {
    # create user given by the user and add to groups need it.
    # Add required groups
    groupadd -f admin

    # Adds user, default password same as name
    if grep -q "^${option_user}:" /etc/passwd
    then
        #user exist, add to group
        echo "adding user ${option_user} to group admin"
        usermod -a -G admin -g admin ${option_user}
    else
        #create user if it does not exist
        [ -z "$FORCE" ] && read -p "user '${option_user}' does not exist, create (Y/n)" kk
        if ! [ -z "$kk" -o "$kk"="y" -o "$kk"="Y" ]
        then
            exit
        fi
        echo "creating and configuring user ${option_user}"
        useradd -m -G admin -g admin ${option_user}
        #Password
        if [ -z "$FORCE" ]
            then
                echo "Provide a password for ${option_user}"
                passwd ${option_user}
            else
                echo -e "$option_user\n$option_user" | passwd --stdin ${option_user}
        fi
    fi

}




#1.2 input parameters
FORCE=""
while getopts "h" o; do
    case "${o}" in
        h)
            _usage
            exit -1
            ;;
    esac
done
shift $((OPTIND-1))



if [ $# -lt 1 ]
then
  _usage
  exit
fi

[ -z "$1" ] && echo -e "ERROR: User argument is mandatory, --user=<user>\n"  && _usage

option_user=$1

#check root privileges
[ "${USER}" != "root" ] && echo "Needed root privileges" >&2 && exit 2


echo '
#################################################################
#####       INSTALL USER                                    #####
#################################################################'

_install_user
_add_user_to_visudo

echo '
#################################################################
#####       INSTALL NEEDED PACKETS                          #####
#################################################################'
_install_packages_dependencies

_create_ovs_controller_config_path

echo
echo "Do not forget to copy the public ssh key into /home/${option_user}/.ssh/authorized_keys for authomatic login from openvim controller"
echo

echo "Reboot the system to make the changes effective"
