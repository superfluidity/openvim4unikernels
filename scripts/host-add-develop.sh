
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

#Get configuration of a host for using it as a compute node

function usage(){

    echo -e "\nUsage: $0 --user <user> --ip=<X.X.X.X> --cores=<core_number> --huge-pages-1G=<huga_pages_number> --nb-10GB-interfaces==<interface_number>"
    echo -e "Generate a develop host yaml to be used for openvim host-add\n"
    echo -e "   --user  -u  <user>        Server OAM Ip"
    echo -e "   --ip    -i  <ip>          Server hostname"
    echo -e "   --cores -c  <cores>       Numa Cores available must be an odd number and bigger or equal to 4."
    echo -e "   --huge-pages-1G      -hp  <huge_pages_number>   Must be an odd number and bigger or equal to 16. 4GiB of memory will be reserved for the host OS, the rest will be used by VM."
    echo -e "   --nb-10GB-interfaces -ni  <nb-10GB-interfaces>  Dataplane interfaces must be an odd number and bigger or equal to 4."
    echo -e "\n"
    echo -e "The output will be a server descriptor with two numas and resources (memory, cores and interfaces) equally distributed between them."
    echo -e "Each interface (physical funtion) will have defined 8 SR-IOV (virtual functions)."
    echo -e "\n"
    exit 1
}

function get_hash_value() {   echo `eval  echo $\{\`echo $USER[$IP]\`\}`; }

function get_mac(){
  seed=$1
  b1=$((seed%16)); seed=$((seed/16))
  b2=$((seed%16)); seed=$((seed/16))
  b3=$((seed%16)); seed=$((seed/16))
  b4=$((seed%16)); seed=$((seed/16))
  b5=$((seed%16)); seed=$((seed/16))
  mac=`printf "%02X:%02X:%02X:%02X:%02X:%02X" 2 $b5 $b4 $b3 $b2 $b1`
  echo $mac
}

function _parse_opts(){

    #help argument
    if [ -n "$option_help" ];
    then
        usage
    fi

    #User argument
    [ -z "$option_user" ] && echo -e "ERROR: User argument is mandatory, --user=<user>\n" && usage
    USER=${option_user}

    [ -z "$option_ip" ] && echo -e "ERROR: OAM IP argument is mandatory, --ip=<X.X.X.X>\n" && usage
    IP=${option_ip}

    #TODO to be checl diference between real cores an numa cores
    #cores argument
    REAL_CORES=$(grep -c "^processor" "/proc/cpuinfo")
    if [ -z "$option_cores" ] ; then
        CORES=REAL_CORES
    else
        CORES=${option_cores}
    fi

    #Ensure the core user input is big enough
    ([ $((CORES%2)) -ne 0 ]) && echo -e "ERROR: Wrong number of cores\n" && usage

    MEMORY=$(($(grep MemTotal /proc/meminfo | awk '{print $2}') /1024/1024))
    if [ -z "$option_huge_pages_1G" ] ; then
        HUGE_PAGES_MEMORY=0
    else
        HUGE_PAGES_MEMORY=${option_huge_pages_1G}
    fi
    #Ensure the memory user input is big enough
    #([ $((MEMORY%2)) -ne 0 ] || [ $MEMORY -lt 16 ] ) && echo -e "ERROR: Wrong number of memory\n" && usage

    #nb_10GB_interfaces argument
    if [ -z "$nb_10GB_interfaces" ] ; then
        INTERFACES=8
    else
        INTERFACES=${nb_10GB_interfaces}
    fi
    ([ $((INTERFACES%2)) -ne 0 ] || [ $INTERFACES -lt 4 ] ) && echo -e "ERROR: Wrong number of interfaces\n" && usage

    # Parameter by default
    NUMAS=1
    ([ $((NUMAS%2)) -ne 0 ]) && NUMAS=1
}

function _generate_compute_develope_yaml(){

    _yaml_init

    FEATURES_LIST="lps,dioc,hwsv,tlbps,ht,lps,64b,iommu"

    #Generate a cpu topology for 4 numas with hyperthreading
    #in this developing/fake server all cores can be used
    #TODO check if this calculation is correct
    echo2file "#This file was created by $0"
    echo2file "#for adding this compute node to openvim"
    echo2file "#copy this file to openvim controller and run"
    echo2file "#openvim host-add <this>"
    echo2file
    echo2file "host:"
    echo2file "  name:    $HOST_NAME"
    echo2file "  user:    $USER"
    echo2file "  ip_name: $IP"
    echo2file "host-data:"
    echo2file "  name:        $HOST_NAME"
    echo2file "  user:        $USER"
    echo2file "  ip_name:     $IP"
    echo2file "  ranking:     100"
    echo2file "  description: $HOST_NAME"
    echo2file "  features:    $FEATURES_LIST"
    echo2file "  numas:"

    numa=0
    last_iface=0
    iface_counter=0

    while [ $numa -lt $NUMAS ]
    do

      HUGE_PAGES=$((HUGE_PAGES_MEMORY/2-2))
      ([ ${HUGE_PAGES} -lt -1 ]) && HUGE_PAGES=0

      echo2file "  - numa_socket:  $numa"
    #MEMORY
      echo2file "    hugepages: $((HUGE_PAGES))"
      echo2file "    memory:    $((MEMORY/$NUMAS))"
    #CORES
      echo2file "    cores:"

      for((n_core=0;n_core<$REAL_CORES;n_core++))
        do
            THREAD_ID=$(($n_core+1))
            CORE_ID=$(($((${n_core}+${numa}))/2))
            echo2file "    - core_id:   ${CORE_ID}"
            echo2file "      thread_id: ${THREAD_ID}"
            [ $CORE_ID -eq 0 ] && echo2file "      status:    noteligible"

            thread_counter=$((thread_counter+1))
      done
      # GENERATE INTERFACES INFORMATION AND PRINT IT
      seed=$RANDOM
      echo2file "    interfaces:"
      for ((iface=0;iface<$INTERFACES;iface+=2))
      do
        name="iface$iface_counter"
        bus=$((iface+last_iface))
        bus=$((iface))
        pci=`printf "0000:%02X:00.0" $bus`
        mac=`get_mac $seed`
        seed=$((seed+1))

        echo2file "    - source_name: $name"
        echo2file "      Mbps: 10000"
        echo2file "      pci: \"$pci\""
        echo2file "      mac: \"$mac\""
        echo2file "      sriovs:"

        PCI_COUNTER=0
        for((nb_sriov=0;nb_sriov<8;nb_sriov++))
        do
          #PCI_COUNTER=$((PCI_COUNTER+2))
          #echo2file "nb_sriov "$nb_sriov
          #echo2file "PCI_COUNTER "$PCI_COUNTER

          pci=`printf "0000:%02X:10.%i" $bus $nb_sriov`
          mac=`get_mac $seed`
          seed=$((seed+1))
          echo2file "      - source_name: eth$nb_sriov"
          echo2file "        mac: \"$mac\""
          echo2file "        pci: \"$pci\""
        done
        iface_counter=$((iface_counter+1))
      done
      last_iface=$(((numa+1)*127/NUMAS+5)) #made-up formula for more realistic pci numbers
      numa=$((numa+1))
    done
}

function _yaml_init(){
    echo -n > host-develope.yaml
}

function echo2file(){
    echo "${1}"
    echo "${1}" >> host-develope.yaml
}

function _get_opts()
{
    [[ ${BASH_SOURCE[0]} != $0 ]] && ___exit="return" || ___exit="exit"

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
            [[ ${argument:0:1} == "-" ]] && echo "option '-$option' requires an argument"  >&2 && $___exit 1
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
                [[ $bad_option == y ]] && echo "invalid argument '-$option'?  Type -h for help" >&2 && $___exit 1
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
                            [[ -n "${option_argument}" ]] && echo "option '--${option%%=*}' do not accept an argument " >&2 && $___exit 1
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
            [[ $bad_option == y ]] && echo "invalid argument '-$option'?  Type -h for help" >&2 && $___exit 1
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
            [[ $bad_option == y ]] && echo "invalid argument '--'?  Type -h for help" >&2 && $___exit 1
            break
        else
            params="$params ${argument}"
        fi

    done

    [[ -n "$get_argument" ]] && echo "option '-$option' requires an argument"  >&2 && $___exit 1
    $___exit 0

}

#check root privileges and non a root user behind
[ "${USER}" != "root" ] && echo "Needed root privileges" && _usage && exit -1

#process options
DIRNAME=$(readlink -f ${BASH_SOURCE[0]})
DIRNAME=$(dirname $DIRNAME)

#source ${DIRNAME}/get-options.sh "help:h user:u= ip:i= cores:c= huge-pages-1G:hp= nb-10GB-interfaces:ni="  $*
_get_opts "help:h user:u= ip:i= cores:c= huge-pages-1G:hp= nb-10GB-interfaces:ni="  $*
_parse_opts

HOST_NAME=`cat /etc/hostname`

_generate_compute_develope_yaml

