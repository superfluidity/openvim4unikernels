#!/bin/bash
##
#
#         Copyright info
#
##

#launch openvim component for clickos tests


DIRNAME=$(readlink -f ${BASH_SOURCE[0]})
DIRNAME=$(dirname $DIRNAME )
DIR_OM=$(dirname $DIRNAME )
XENSTORE="No"
NETNAME="default"

function usage(){

    echo -e "Usage: $0 OPTIONS NAME"
    echo -e " Start ClickOS chain demo with OpenVIM Release ONE and Xen" 
    echo -e " OPTIONS"
    echo -e "    -c [c408|c409] compute node. By dafault c408"
    echo -e "    -d [c408|c409] mysql node. By default c409"
    echo -e "    -n network name. By default default"
    echo -e "    -s use vanilla images and enable it with xenstore"
    echo -e "    --help   shows this help"
    echo -e " "
}

getLastId() {
    # return the greatest domain id
    XLLIST=$(ssh compute408@10.0.11.2 "sudo xl list")
    DOMID=$(echo -e "$XLLIST" | tail -n 1 | awk '{print $2}')
    echo $DOMID
}

getIdFromName() {
    # get a domain id from the domain name
    DOMNAME="$1"
    XLLIST=$(ssh compute408@10.0.11.2 "sudo xl list")
    DOMID=$(echo -e "$XLLIST" | awk '{print $1 ":" $2}' | grep "\<${DOMNAME}\>" | awk -F':' '{print $2}')
    echo $DOMID
}

myCosmos() {
    # emulate cosmos by writing on the xenstore
    DOMID="$1"
    CLICKFILE="$2"
    CLICKCFG=$(cat $CLICKFILE)
    ssh compute408@10.0.11.2 "sudo xenstore-write /local/domain/${DOMID}/clickos/0/config/0 \"$CLICKCFG\""
    ssh compute408@10.0.11.2 "sudo xenstore-write /local/domain/${DOMID}/clickos/0/status  'Running'"
}

getOvsPortFromId() {
    # get the ovs switch port corresponding to a domain id and device id
    DOMID=$1
    DEVID=$2
    RESULT=$(ssh compute408@10.0.11.2 "sudo ovs-ofctl show ovim-$NETNAME" | grep vif${DOMID}.${DEVID} | awk -F'(' '{print $1}' | sed 's/\ //g')
    echo $RESULT
}

getOvsPortFromName() {
    # get the ovs switch port corresponding to a name
    DEVNAME=$1
    ssh compute408@10.0.11.2 "sudo ovs-ofctl show ovim-$NETNAME" | grep $DEVNAME | awk -F'(' '{print $1}' | sed 's/\ //g'
}


while getopts ":n:c:d:rmxt:u:s-:" o; do
    case "${o}" in
        c)
            CNODE="$OPTARG"
            ;;
        d)
            DBNODE="$OPTARG"
            ;;
        n)
            NETNAME="$OPTARG"
            ;;
        s)
            XENSTORE="Yes"
            ;;
        -)
            [ "${OPTARG}" == "help" ] && usage && exit 0
            echo "Invalid option: --$OPTARG" >&2 && usage >&2
            exit 1
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2 && usage >&2
            exit 1
            ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2 && usage >&2
            exit 1
            ;;
        *)
            usage >&2
            exit -1
            ;;
    esac 
done
shift $((OPTIND-1))


#If missing set default values
[ -z "$CNODE" ] && CNODE=c408
[ -z "$DBNODE" ] && DBNODE=c409
[ -z "$NETNAME" ] && NETNAME="default"

#check if compute nodes strings is correct
if [[ "$CNODE" != "c408" && "$CNODE" != "c409" ]]; then
 echo -e "\nUnknown compute node. Type c408 or c409\n" >&2 && usage >&2; exit 1
fi

#check if database strings is correct
if [[ "$DBNODE" != "c408" && "$DBNODE" != "c409" ]]; then
 echo -e "\nUnknown MySQL node. Type c408 or c409\n" >&2 && usage >&2; exit 1
fi

echo -e " "
echo -e "-------------------------------------"
echo -e " Demo of ClickOS chains on OpenVIM"
echo -e " "
echo -e " PARAMETERS:"
echo -e "  - Compute Node: $CNODE"
echo -e "  - MySQL server: $DBNODE"
echo -e "  - Network name: $NETNAME"
echo -e " "
echo -e " Process ID: $$"
echo -e " "
echo -e "-------------------------------------"

# Check selected database
#  - Set mysql server ip address to selected node on openvimd.cfg file
#  e file templete openvimd.cfg settati con i due diversi mysql server copiare quello esatto all'occorrenza
#if [[ "$DBNODE" == "c408" ]]; then
#   echo -e "\n > Setting DB Node to c408 \n"
#   cp "$DIRNAME/openmano/openvim/openvimd_c408.cfg" "$DIRNAME/openmano/openvim/openvimd.cfg"
#else
#   echo -e "\n > Setting DB Node to c409 \n"
#   cp "$DIRNAME/openmano/openvim/openvimd_c409.cfg" "$DIRNAME/openmano/openvim/openvimd.cfg"
#fi

# Restore OpenVIM database to default values.
#echo -e "\n > Restore $DBNODE database... \n"
#if [[ "$DBNODE" == "c408" ]]; then
#    ssh compute408@10.0.11.2 "mysql -uvim -pvimpw vim_db < vim_db_release-one.sql"
#else
#    mysql -uvim -pvimpw vim_db < vim_db_release-one.sql
#fi

# Start OpenVIM instance.
echo -e "\n > Starting OpenVIM..."
ovstatus=$(/home/openvim/openvim-two/openvim/scripts/service-openvim vim status)
if [[ $ovstatus == *"not running"* ]]; then
  /home/openvim/openvim-two/openvim/scripts/service-openvim vim start >/dev/null
else
  echo $ovstatus
fi

#echo -e "\n > Check all compute nodes"
## Get compute node list
#ovcnode=$(/home/openvim/openvim-two/openvim/openvim host-list)
##Set all compute node down
#while read -r line; do
#    /home/openvim/openvim-two/openvim/openvim host-down --force ${line:0:36} >/dev/null
#done <<< "$ovcnode"

##Search the selected compute node
#sel_cnode=$(echo "$ovcnode" | grep ${CNODE:1})
##If compute node is not configured, setup it
#echo -e "\n > Setting $CNODE as compute node"
#if [[ -z $sel_cnode  ]]; then
#    echo " Compute node c${CNODE:1} is not configured, setting up..."
#    /home/openvim/openvim-two/openvim/openvim host-add /home/openvim/clickfiles/host-nec-${CNODE}-eth3.json
#fi
#/home/openvim/openvim-two/openvim/openvim host-up --force  nec-test-${CNODE:1}-eth3

echo -e "\n*******************************\n Starting ClickOS demo session \n*******************************"
sleep 2

echo -e "\n Loading ClickOS Ping responder VNF..."
TIME3=$(date +%s.%3N)
/home/openvim/openvim-two/openvim/openvim vm-create /home/openvim/clickfiles/vm-clickos-ping2.yaml  #ping preset version
TIME4=$(date +%s.%3N)
ping_time1=$(bc -l <<< "scale=3; ($TIME4 - $TIME3)*1000")
echo -e " Task completed in: \e[1;32m $ping_time1 ms \e[0m"
sleep 2
ICMPID=$(getLastId)
echo " Xen DomU id: $ICMPID"

echo -e "\n Loading ClickOS Firewall VNF..."
TIME7=$(date +%s.%3N)
/home/openvim/openvim-two/openvim/openvim vm-create /home/openvim/clickfiles/vm-clickos-firewall2.yaml  #firewall preset version
TIME8=$(date +%s.%3N)
fw_time1=$(bc -l <<< "scale=3; ($TIME8 - $TIME7)*1000")
echo -e " Task completed in: \e[1;32m $fw_time1 ms \e[0m"
sleep 2
FWID=$(getLastId)
echo " Xen DomU id: $FWID"

echo -e "\n Loading ClickOS VLAN Decapsulator-Encapsulator VNF..."
TIME5=$(date +%s.%3N)
/home/openvim/openvim-two/openvim/openvim vm-create /home/openvim/clickfiles/vm-clickos-vlandecenc2.yaml #vlandecenc preset version
TIME6=$(date +%s.%3N)
vl_time1=$(bc -l <<< "scale=3; ($TIME6 - $TIME5)*1000")
echo -e " Task completed in: \e[1;32m $vl_time1 ms \e[0m"
sleep 2
VLANDEID=$(getLastId)
echo " Xen DomU id: $VLANDEID"

echo -e "\n Loading Alpine Linux full VM..."
TIME1=$(date +%s.%3N)
/home/openvim/openvim-two/openvim/openvim vm-create /home/openvim/clickfiles/vm-alpine14.yaml
TIME2=$(date +%s.%3N)
alpine_time1=$(bc -l <<< "scale=3; ($TIME2 - $TIME1)*1000")
echo -e " Task completed in: \e[1;32m $alpine_time1 ms \e[0m"
sleep 2
ALPINEID=$(getLastId)
echo " Xen DomU id: $ALPINEID"


if [[ "$XENSTORE" == "Yes" ]]; then
  myCosmos $FWID "$DIRNAME/clickfiles/basicfirewall.click"
  myCosmos $ICMPID "$DIRNAME/clickfiles/ping.click"
fi

echo -e "\n Set up networking..."
## - Setup networking
ICMPPORT0=$(getOvsPortFromId $ICMPID 0)
FWPORT0=$(getOvsPortFromId $FWID 0)
FWPORT1=$(getOvsPortFromId $FWID 1)
VLANEDPORT0=$(getOvsPortFromId $VLANDEID 0)
VLANEDPORT1=$(getOvsPortFromId $VLANDEID 1)
ALPINEPORT0=$(getOvsPortFromId $FWID 0)

#echo " - Create forward flow entry from firewall port $FWPORT1 to ping port $ICMPPORT0"
#echo " - Create reverse flow entry from ping port $ICMPPORT0 to firewall port $FWPORT1"
# connect the exit port of the firewall to the input port of the ICMP responder
#ssh compute408@10.0.11.2 "sudo ovs-ofctl add-flow ovim-$NETNAME \"in_port=${FWPORT1},actions=output:${ICMPPORT0}\""
#ssh compute408@10.0.11.2 "sudo ovs-ofctl add-flow ovim-$NETNAME \"in_port=${ICMPPORT0},actions=output:${FWPORT1}\""
#echo " - Create forward flow entry from vlan encap/decap port $VLANEDPORT1 to firewall port $FWPORT0"
#echo " - Create reverse flow entry from firewall port $FWPORT0 to vlan encap/decap port $VLANEDPORT1"
# connect the exit port of the VLANED to the input port of the firewall
#ssh compute408@10.0.11.2 "sudo ovs-ofctl add-flow ovim-$NETNAME \"in_port=${VLANEDPORT1},actions=output:${FWPORT0}\""
#ssh compute408@10.0.11.2 "sudo ovs-ofctl add-flow ovim-$NETNAME \"in_port=${FWPORT0},actions=output:${VLANEDPORT1}\""

# create a veth at the beginning of the chain
echo " - Create veth port begin0v and set peer conection with begin1 port"
echo " - Set ip address 10.10.0.2/24 to begin0 (VLAN ID 100)"
ssh compute408@10.0.11.2 "sudo ip link add begin0 type veth peer name begin1"
ssh compute408@10.0.11.2 "sudo ovs-vsctl add-port ovim-$NETNAME begin1"
ssh compute408@10.0.11.2 "sudo ip link add link begin0 name begin0.100 type vlan id 100"
ssh compute408@10.0.11.2 "sudo ip address add 10.10.0.2/24 dev begin0.100"
ssh compute408@10.0.11.2 "sudo ip link set begin0 up"
ssh compute408@10.0.11.2 "sudo ip link set begin0.100 up"
ssh compute408@10.0.11.2 "sudo ip link set begin1 up"
ssh compute408@10.0.11.2 "sudo ip link set ovim-$NETNAME up"

#management port of alpine vm
ssh compute408@10.0.11.2 "sudo ip link add amp0 type veth peer name amp1"
ssh compute408@10.0.11.2 "sudo ovs-vsctl add-port ovim-alpine_man amp1"
ssh compute408@10.0.11.2 "sudo ip address add 10.20.0.1/24 dev amp0"
ssh compute408@10.0.11.2 "sudo ip link set amp0 up"
ssh compute408@10.0.11.2 "sudo ip link set amp1 up"
ssh compute408@10.0.11.2 "sudo ip link set ovim-alpine_man up"


OVSBEGINPORT=$(getOvsPortFromName begin1)
#echo " - Create forward flow entry from begin1 port $OVSBEGINPORT to vlan encap/decap port $VLANEDPORT0"
#echo " - Create reverse flow entry from vlan encap/decap port $VLANEDPORT0 to begin1 port $OVSBEGINPORT"
#ssh compute408@10.0.11.2 "sudo ovs-ofctl add-flow ovim-$NETNAME \"in_port=${OVSBEGINPORT},actions=output:${VLANEDPORT0}\""
#ssh compute408@10.0.11.2 "sudo ovs-ofctl add-flow ovim-$NETNAME \"in_port=${VLANEDPORT0},actions=output:${OVSBEGINPORT}\""
#ssh compute408@10.0.11.2 "sudo ovs-ofctl add-flow ovim-$NETNAME \"in_port=${ICMPPORT0},actions=output:${OVSBEGINPORT}\""

# create a veth at the end of the chain
#ip link add end0 type veth peer name end1
#ovs-vsctl add-port ovsbr0 end0
#ip link set end0 up
#ip link set end1 up
#OVSENDPORT=$(getOvsPortFromName end0)
#ovs-ofctl add-flow ovsbr0 "in_port=${ICMPPORT1},actions=output:${OVSENDPORT}"

echo -e "\n TOPOLOGY:"
echo -e "\e[0;31m -------------              \e[0;34m ------------       \e[0;35m ------------       \e[0;32m -------------\e[0m"
echo -e "\e[0;31m |           |              \e[0;34m |          |       \e[0;35m |          |       \e[0;32m |           |\e[0m"
echo -e "\e[0;31m |  Alpine   |              \e[0;34m |   VLAN   |       \e[0;35m |          |       \e[0;32m |   Ping    |\e[0m"
echo -e "\e[0;31m |  distro   |\e[0;37m--------O------\e[0;34m|  Enc/dec |\e[0;37m--------\e[0;35m| Firewall |\e[0;37m--------\e[0;32m| Responder |\e[0m"
echo -e "\e[0;31m | 10.10.0.4 |       \e[0;33m ^\e[0m     \e[0;34m |  id 100  |       \e[0;35m |          |       \e[0;32m | 10.10.0.3 |\e[0m"
echo -e "\e[0;31m |           |       \e[0;33m |\e[0m     \e[0;34m |          |       \e[0;35m |          |       \e[0;32m |           |\e[0m"
echo -e "\e[0;31m -------------       \e[0;33m |\e[0m     \e[0;34m ------------       \e[0;35m ------------       \e[0;32m -------------\e[0m"
echo -e "                     \e[0;33m |\e[0m"
echo -e "                  \e[0;33m begin0\e[0m"
echo -e "                \e[0;33m 10.10.0.2\e[0m"
echo -e "\n--------------------\nDemo setup completed"
echo -e "\nType 'ping' to send normal ICMP ECHO packets to VNFs"
echo -e "Type 'ping-tos' to send ICMP ECHO packets to VNFs with set ToS field to 0xcc"
echo -e "Type 'stop' to start the VNFs shutdown procedure\n"


while true
do
  read -p " > " option
  if [ "$option" == "stop" ]; then
    echo -e "\n Closing OpenVIM..."
    /home/openvim/openvim-two/openvim/openvim vm-delete -f vm-clickos-ping2
    /home/openvim/openvim-two/openvim/openvim vm-delete -f vm-clickos-firewall2
    /home/openvim/openvim-two/openvim/openvim vm-delete -f vm-clickos-vlandecenc2
    /home/openvim/openvim-two/openvim/openvim vm-delete -f vm-alpine14
    echo -e "\n***************\n Demo Complete \n***************"
    sleep 5
    # Stop OpenVIM instance.
    echo -e "\n > Stopping OpenVIM..."
    /home/openvim/openvim-two/openvim/scripts/service-openvim vim stop

    # Delete all ovs flows
    echo -n -e "\n > Stopping Networking ..."
    #ssh compute408@10.0.11.2 "sudo ovs-ofctl del-flows ovim-$NETNAME"
    ssh compute408@10.0.11.2 "sudo ip link set begin0 down"
    ssh compute408@10.0.11.2 "sudo ip link set begin0.100 down"
    ssh compute408@10.0.11.2 "sudo ip link set begin1 down"
    ssh compute408@10.0.11.2 "sudo ovs-vsctl del-port ovim-$NETNAME begin1"
    ssh compute408@10.0.11.2 "sudo ip link del begin0.100"
#    ssh compute408@10.0.11.2 "sudo ip link del begin0"
    ssh compute408@10.0.11.2 "sudo ip link del begin0 type veth peer name begin1"

    ssh compute408@10.0.11.2 "sudo ip link set amp0 down"
    ssh compute408@10.0.11.2 "sudo ip link set amp1 down"
    ssh compute408@10.0.11.2 "sudo ovs-vsctl del-port ovim-alpine_man amp1"
    ssh compute408@10.0.11.2 "sudo ip link del amp0 type veth peer name amp1"
    echo -e " done"
    break
  elif [ "$option" == "ping" ]; then
    echo -e "\nSending ICMP ECHO packets to VNFs..."
    echo -e "computer98:~\$ ping -c 4 10.10.0.3"
    ssh compute408@10.0.11.2 "ping -c 4 10.10.0.3"
  elif [ "$option" == "ping-tos" ]; then
    echo -e "\nSending ICMP ECHO packets to VNFs..."
    echo -e "computer98:~\$ ping -c 4 -Q 0xcc 10.10.0.3"
    ssh compute408@10.0.11.2 "ping -c 4 -Q 0xcc 10.10.0.3"
  elif [ "$option" == "" ]; then
    continue
  else
    echo -e "Unknow command."
    echo -e "Type 'ping' to send normal ICMP ECHO packets to VNFs"
    echo -e "Type 'ping-tos' to send ICMP ECHO packets to VNFs with set ToS field to 0xcc"
    echo -e "Type 'stop' to start the VNFs shutdown procedure\n"
  fi
done

exit 0
