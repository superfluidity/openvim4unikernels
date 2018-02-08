#!/bin/bash

##
# Copyright 2017 
#
# -- Put copyright info there --
#
#
# 
##

DBUSER="vim"
DBPASS="vimpw"
DBHOST="localhost"
DBPORT="3306"
DBNAME="vim_db"
 
# Detect paths
MYSQL=$(which mysql)
AWK=$(which awk)
GREP=$(which grep)
DIRNAME=`dirname $0`

function usage(){
    echo -e "Usage: $0 OPTIONS [install|uninstall|upgrade-server|downgrade-server|upgrade-host|downgrade-host]"
    echo -e "  Upgrades/Downgrades openvim database to support ClickOS images"
    echo -e "  OPTIONS"
    echo -e "     -u USER  database user. '$DBUSER' by default. Prompts if DB access fails"
    echo -e "     -p PASS  database password. 'No password' by default. Prompts if DB access fails"
    echo -e "     -P PORT  database port. '$DBPORT' by default"
    echo -e "     -h HOST  database host. '$DBHOST' by default"
    echo -e "     -d NAME  database name. '$DBNAME' by default.  Prompts if DB access fails"
    echo -e "     --help   shows this help"
}

while getopts ":u:p:P:h:-:" o; do
    case "${o}" in
        u)
            DBUSER="$OPTARG"
            ;;
        p)
            DBPASS="$OPTARG"
            ;;
        P)
            DBPORT="$OPTARG"
            ;;
        d)
            DBNAME="$OPTARG"
            ;;
        h)
            DBHOST="$OPTARG"
            ;;
        -)
            [ "${OPTARG}" == "help" ] && usage && exit 0
            echo "Invalid option: --$OPTARG" >&2 && usage  >&2
            exit 1
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2 && usage  >&2
            exit 1
            ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2 && usage  >&2
            exit 1
            ;;
        *)
            usage >&2
            exit -1
            ;;
    esac
done
shift $((OPTIND-1))

#CHECK MODE OPTION
MODE_OPT="$1"
if [ -z "$MODE_OPT" ]
then 
    echo "Error. Requires install|uninstall or upgrade-server|downgrade-server or upgrade-host|downgrade-host as argument." >&2 && usage  >&2
    exit 1
fi

#check and ask for database user password
DBUSER_="-u$DBUSER"
DBPASS_=""
[ -n "$DBPASS" ] && DBPASS_="-p$DBPASS"
DBHOST_="-h$DBHOST"
DBPORT_="-P$DBPORT"
while !  echo ";" | mysql $DBHOST_ $DBPORT_ $DBUSER_ $DBPASS_ $DBNAME >/dev/null 2>&1
do
        [ -n "$logintry" ] &&  echo -e "\nInvalid database credentials!!!. Try again (Ctrl+c to abort)"
        [ -z "$logintry" ] &&  echo -e "\nProvide database name and credentials"
        read -e -p "mysql database name($DBNAME): " KK
        [ -n "$KK" ] && DBNAME="$KK"
        read -e -p "mysql user($DBUSER): " KK
        [ -n "$KK" ] && DBUSER="$KK" && DBUSER_="-u$DBUSER"
        read -e -s -p "mysql password: " DBPASS
        [ -n "$DBPASS" ] && DBPASS_="-p$DBPASS"
        [ -z "$DBPASS" ] && DBPASS_=""
        logintry="yes":
        echo
done

DBCMD="mysql $DBHOST_ $DBPORT_ $DBUSER_ $DBPASS_ $DBNAME"
#echo DBCMD $DBCMD

#function check_patch(){
#    #This function check if hypervisor and osType column existchange of foreign key does not work
#    echo "    upgrade database to ClickOS support"
#    echo "IF COL_LENGTH('table_name','column_name') IS NULL
#           BEGIN
#             /*Column does not exist or caller does not have permission to view the object*/
#           END;"| $DBCMD || ! echo "ERROR. Aborted!" || exit -1 
#}

function upgrade_to_clickos(){
    #This function add hypervisor and os_type column to instances table
    echo "    upgrade database to ClickOS support"
    echo "ALTER TABLE instances ADD COLUMN hypervisor enum('kvm','xen-unik','xenhvm') NOT NULL DEFAULT 'kvm' AFTER flavor_id;"| $DBCMD || ! echo "ERROR. Aborted!" || exit -1
	echo "ALTER TABLE instances ADD COLUMN os_image_type VARCHAR(24) NOT NULL DEFAULT 'other'  AFTER hypervisor;"| $DBCMD || ! echo "ERROR. Aborted!" || exit -1
}

function downgrade_from_clickos(){
    #This function remove hypervisor and os_type column from instances table
    echo "    downgrade database to revome ClickOS support"
    echo "ALTER TABLE instances DROP COLUMN hypervisor;"| $DBCMD || ! echo "ERROR. Aborted!" || exit -1
    echo "ALTER TABLE instances DROP COLUMN os_image_type;"| $DBCMD || ! echo "ERROR. Aborted!" || exit -1
}

function upgrade_host_table(){
    #This function add hypervisors column to hosts table
    echo "    upgrade hosts table to support hypervisors field"
    echo "ALTER TABLE hosts ADD COLUMN hypervisors VARCHAR(64) NOT NULL DEFAULT 'kvm' AFTER features;"| $DBCMD || ! echo "ERROR. Aborted!" || exit     -1
}


function downgrade_host_table(){
    #This function remove hypervisors column from hosts table
    echo "    downgrade hosts table to remove hypervisors field"
    echo "ALTER TABLE hosts DROP COLUMN hypervisors;"| $DBCMD || ! echo "ERROR. Aborted!" || exit -1
}

if [ $MODE_OPT == 'install' ]
then
    upgrade_to_clickos
    upgrade_host_table
elif [ $MODE_OPT == 'uninstall' ]
then
    downgrade_from_clickos
    downgrade_host_table
elif [ $MODE_OPT == 'upgrade-server' ]
then
    upgrade_to_clickos
elif [ $MODE_OPT == 'downgrade-server' ]
then
    downgrade_from_clickos
elif [ $MODE_OPT == 'upgrade-host' ]
then
    upgrade_host_table
elif [ $MODE_OPT == 'downgrade-host' ]
then
    downgrade_host_table
else
    echo "Error. Invalid argument." >&2 && usage  >&2
    exit 1
fi

echo "Done."
