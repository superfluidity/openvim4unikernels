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

# Authors: Antonio Lopez, Pablo Montes, Alfonso Tierno
# June 2015

# Personalize RHEL7.1 on compute nodes
# Prepared to work with the following network card drivers:
# 	tg3, igb drivers for management interfaces
# 	ixgbe (Intel Niantic) and i40e (Intel Fortville) drivers for data plane interfaces

# To download:
# wget https://raw.githubusercontent.com/nfvlabs/openmano/master/scripts/configure-compute-node-develope-UBUNTU16.04.sh
# To execute:
# chmod +x ./configure-compute-node-RHEL7.1.sh
# sudo ./configure-compute-node-RHEL7.1.sh <user> <iface>

# Assumptions:
# All virtualization options activated on BIOS (vt-d, vt-x, SR-IOV, no power savings...)
# RHEL7.1 installed without /home partition and with the following packages selection:
# @base, @core, @development, @network-file-system-client, @virtualization-hypervisor, @virtualization-platform, @virtualization-tools

interfaced_path='/etc/network/interfaces.d/'
#interfaced_path='/home/ubuntu/openvim_install/openvim/test-inter/'
set_mtu_path='/etc/'
VLAN_INDEX=20

function _usage(){
    echo -e "Usage: sudo $0 [-y] <user-name>  <iface-name>"
    echo -e "  Configure compute host for VIM usage. (version 0.4). OPTIONS:"
    echo -e "     -h --help    this help"
    echo -e "     -f --force:  do not prompt for confirmation. If a new user is created, the user name is set as password"
    echo -e "     -u --user:   Create if not exist and configure this user for openvim to connect"
    echo -e "     --in --iface-name:  creates bridge interfaces on this interface, needed for openvim overlay networks"
    exit 1
}

function _interface_cfg_generator(){
    #$1 interface name | $2 MTU | $3 type

echo "
auto ${1}
iface ${1} inet ${3}
        mtu ${2}
        ${bridge_ports}
" >> ${interfaced_path}${1}."cfg"
}


function _interface_cfg_generator(){
    #$1 interface name | $2 vlan  | $3 virbrMan | $4  MTU

echo "
auto ${1}.${2}
iface ${1}.${2} inet manual
        mtu ${4}
        post-up vconfig add ${1} ${2}
        post-down vconfig rem ${1}.${2}

auto ${3}
iface ${3} inet manual
        bridge_ports ${1}.${2}
        mtu ${4}
        vlan-raw-device $1
" >> ${interfaced_path}${1}.${2}."cfg"
}

function _install_user() {
    # create user given by the user and add to groups need it.
    # Add required groups
    groupadd -f admin
    groupadd -f libvirt   #for other operating systems may be libvirtd

    # Adds user, default password same as name
    if grep -q "^${option_user}:" /etc/passwd
    then
        #user exist, add to group
        echo "adding user ${option_user} to groups libvirt,admin"
        usermod -a -G libvirt,admin -g admin ${option_user}
    else
        #create user if it does not exist
        [ -z "$FORCE" ] && read -p "user '${option_user}' does not exist, create (Y/n)" kk
        if ! [ -z "$kk" -o "$kk"="y" -o "$kk"="Y" ]
        then
            exit
        fi
        echo "creating and configuring user ${option_user}"
        useradd -m -G libvirt,admin -g admin ${option_user}
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

function _openmano_img_2_libvirt_img(){
    # Links the OpenMANO required folder /opt/VNF/images to /var/lib/libvirt/images.
    # The OS installation
    # should have only a / partition with all possible space available

    echo " link /opt/VNF/images to /var/lib/libvirt/images"
    if [ "$option_user" != "" ]
    then
        # The orchestator needs to link the images folder
        rm -f /opt/VNF/images
        mkdir -p /opt/VNF/
        ln -s /var/lib/libvirt/images /opt/VNF/images
        chown -R ${option_user}:admin /opt/VNF
        chown -R root:admin /var/lib/libvirt/images
        chmod g+rwx /var/lib/libvirt/images
    else
        mkdir -p /opt/VNF/images
        chmod o+rx /opt/VNF/images
    fi
}

function _install_pacckags_dependences()
{
    # Required packages by openvim
    apt-get -y update
    apt-get -y install  grub-common screen virt-manager ethtool build-essential \
                        x11-common x11-utils libguestfs-tools hwloc libguestfs-tools \
                        numactl vlan nfs-common nfs-kernel-server
    echo "Remove unneeded packages....."
    apt-get -y autoremove
}

function _network_configuration(){
    # adding vlan support
    grep -q '8021q' '/etc/modules'; [ $? -eq 1 ] && sudo su -c 'echo "8021q" >> /etc/modules'

    #grep -q ${interface} '/etc/network/interfaces.d/50-cloud-init.cfg'; [ $? -eq 0 ] && sed -e '/'${interface}'/ s/^#*/#/' -i  '/etc/network/interfaces.d/50-cloud-init.cfg'

    # Network interfaces static configuration
    echo "Interface ==> $interface"
    if [ -n "$interface" ]
    then
        # For management and data interfaces
        rm -f /etc/udev/rules.d/pci_config.rules # it will be created to define VFs
        # Set ONBOOT=on and MTU=9000 on the interface used for the bridges
        echo "configuring iface $interface"

    # Static network interface configuration and MTU
    MTU=9000
    virbrMan_interface_number=20

    #Create bridge interfaces
    echo "Creating bridge ifaces: "
    for ((i =1; i <= ${virbrMan_interface_number}; i++))
        do
            i2digits=${i}
            [ ${i} -lt 10 ] && i2digits="0${i}"
            echo "    ${interface} ${VLAN_INDEX}${i2digits}"
            echo "    virbrMan${i}  vlan ${VLAN_INDEX}${i2digits}"
            j=${i}
            #$1 interface name | $2 vlan | $3 MTU | $3 virbrMan | $4 bridge_ports
            _interface_cfg_generator  ${interface} ${VLAN_INDEX}${i2digits} 'virbrMan'${i} ${MTU}
    done

    fi
}

function _disable_aaparmor(){
    #Deactivating apparmor while looking for a better solution
    /etc/init.d/apparmor stop
    update-rc.d -f apparmor remove
}

function _check_interface(){
    #check if interface given as an argument exits
    if [ -n "$1" ] && ! ifconfig $1 &> /dev/null
    then
        echo "Error: interface '$1' is not present in the system"\n
        exit 1
    fi
}

function _user_remainder_pront()
{
    echo
    echo "Do not forget to create a shared (NFS, Samba, ...) where original virtual machine images are allocated"
    echo
    echo "Do not forget to copy the public ssh key into /home/${option_user}/.ssh/authorized_keys for authomatic login from openvim controller"
    echo
    echo "Reboot the system to make the changes effective"
}

function _libvirt_configuration(){
    # Libvirt options for openvim
    echo "configure Libvirt options"
    sed -i 's/#unix_sock_group = "libvirt"/unix_sock_group = "libvirt"/' /etc/libvirt/libvirtd.conf
    sed -i 's/#unix_sock_rw_perms = "0770"/unix_sock_rw_perms = "0770"/' /etc/libvirt/libvirtd.conf
    sed -i 's/#unix_sock_dir = "\/var\/run\/libvirt"/unix_sock_dir = "\/var\/run\/libvirt"/' /etc/libvirt/libvirtd.conf
    sed -i 's/#auth_unix_rw = "none"/auth_unix_rw = "none"/' /etc/libvirt/libvirtd.conf

    chmod a+rwx /var/lib/libvirt/images
    mkdir /usr/libexec/
    pushd /usr/libexec/
    ln -s /usr/bin/qemu-system-x86_64 qemu-kvm
    popd
}

function _hostinfo_config()
{

    echo "#By default openvim assumes control plane interface naming as em1,em2,em3,em4 " > /opt/VNF/images/hostinfo.yaml
    echo "creating local information /opt/VNF/images/hostinfo.yaml"
    echo "#and bridge ifaces as virbrMan1, virbrMan2, ..." >> /opt/VNF/images/hostinfo.yaml
    echo "#if compute node contain a different name it must be indicated in this file" >> /opt/VNF/images/hostinfo.yaml
    echo "#with the format extandard-name: compute-name" >> /opt/VNF/images/hostinfo.yaml
    chmod o+r /opt/VNF/images/hostinfo.yaml
}

function _get_opts()
{
    options="$1"
    shift

    get_argument=""
    #reset variables
    params=""
    for option_group in $options
    do
        _name=${option_group%%:*}
        _name=${_name%=}
        _name=${_name//-/_}
        eval option_${_name}='""'
    done

    while [[ $# -gt 0 ]]
    do
        argument="$1"
        shift
        if [[ -n $get_argument ]]
        then
            [[ ${argument:0:1} == "-" ]] && echo "option '-$option' requires an argument"  >&2 && return 1
            eval ${get_argument}='"$argument"'
            #echo option $get_argument with argument
            get_argument=""
            continue
        fi


        #short options
        if [[ ${argument:0:1} == "-" ]] && [[ ${argument:1:1} != "-" ]] && [[ ${#argument} -ge 2 ]]
        then
            index=0
            while index=$((index+1)) && [[ $index -lt ${#argument} ]]
            do
                option=${argument:$index:1}
                bad_option=y
                for option_group in $options
                do
                    _name=""
                    for o in $(echo $option_group | tr ":=" " ")
                    do
                        [[ -z "$_name" ]] && _name=${o//-/_}
                        #echo option $option versus $o
                        if [[ "$option" == "${o}" ]]
                        then
                            eval option_${_name}='${option_'${_name}'}-'
                            bad_option=n
                            if [[ ${option_group:${#option_group}-1} != "=" ]]
                            then
                                continue
                            fi
                            if [[ ${#argument} -gt $((index+1)) ]]
                            then
                                eval option_${_name}='"${argument:$((index+1))}"'
                                index=${#argument}
                            else
                                get_argument=option_${_name}
                                #echo next should be argument $argument
                            fi

                            break
                        fi
                    done
                done
                [[ $bad_option == y ]] && echo "invalid argument '-$option'?  Type -h for help" >&2 && return 1
            done
        elif [[ ${argument:0:2} == "--" ]] && [[ ${#argument} -ge 3 ]]
        then
            option=${argument:2}
            option_argument=${option#*=}
            option_name=${option%%=*}
            [[ "$option_name" == "$option" ]] && option_argument=""
            bad_option=y
            for option_group in $options
            do
                _name=""
                for o in $(echo $option_group | tr ":=" " ")
                do
                    [[ -z "$_name" ]] && _name=${o//-/_}
                    #echo option $option versus $o
                    if [[ "$option_name" == "${o}" ]]
                    then
                        bad_option=n
                        if [[ ${option_group:${#option_group}-1} != "=" ]]
                        then #not an argument
                            [[ -n "${option_argument}" ]] && echo "option '--${option%%=*}' do not accept an argument " >&2 && return 1
                            eval option_${_name}='"${option_'${_name}'}-"'
                        elif [[ -n "${option_argument}" ]]
                        then
                            eval option_${_name}='"${option_argument}"'
                        else
                            get_argument=option_${_name}
                            #echo next should be argument $argument
                        fi
                        break
                    fi
                done
            done
            [[ $bad_option == y ]] && echo "invalid argument '-$option'?  Type -h for help" >&2 && return 1
        elif [[ ${argument:0:2} == "--" ]]
        then
            option__="$*"
            bad_option=y
            for o in $options
            do
                if [[ "$o" == "--" ]]
                then
                    bad_option=n
                    option__=" $*"
                    break
                fi
            done
            [[ $bad_option == y ]] && echo "invalid argument '--'?  Type -h for help" >&2 && return 1
            break
        else
            params="$params ${argument}"
        fi

    done

    [[ -n "$get_argument" ]] && echo "option '-$option' requires an argument"  >&2 && return  1
    return 0
}

function _parse_opts()
{
    [ -n "$option_help" ] && _usage && exit 0

    FORCE=""
    [ -n "$option_force" ] && FORCE="yes"

    [ -z "$option_user" ] && echo -e "ERROR: User argument is mandatory, --user=<user>\n" >&2 && _usage
    #echo "user_name = "$option_user

    [ -z "$option_iface_name" ] && echo -e "ERROR: iface-name argument is mandatory, --iface-name=<interface>\n" && _usage
    interface=$option_iface_name

}

#Parse opts
_get_opts "help:h force:f user:u= iface-name:in= "  $*  || exit 1
_parse_opts

#check root privileges
[ "${USER}" != "root" ] && echo "Needed root privileges" >&2 && exit 2

echo "checking interface "$interface

_check_interface $interface

echo '
#################################################################
#####       INSTALL USER                                    #####
#################################################################'
_install_user

echo '
#################################################################
#####       INSTALL NEEDED PACKETS                          #####
#################################################################'
_install_pacckags_dependences

echo '
#################################################################
#####       OTHER CONFIGURATION                             #####
#################################################################'
_openmano_img_2_libvirt_img
_hostinfo_config
_libvirt_configuration

echo '
#################################################################
#####       NETWORK CONFIGURATION                           #####
#################################################################'
_network_configuration
_disable_aaparmor
_user_remainder_pront



