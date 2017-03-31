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

DBUSER="vim"
DBPASS=""
DBHOST="localhost"
DBPORT="3306"
DBNAME="vim_db"
 
# Detect paths
MYSQL=$(which mysql)
AWK=$(which awk)
GREP=$(which grep)
DIRNAME=`dirname $0`

function usage(){
    echo -e "Usage: $0 OPTIONS [{openvim_version}]"
    echo -e "  Inits openvim database; deletes previous one and loads from ${DBNAME}_structure.sql"
    echo -e "   and data from host_ranking.sql, nets.sql, of_ports_pci_correspondece*.sql"
    echo -e "  If openvim_version is not provided it tries to get from openvimd.py using relative path"
    echo -e "  OPTIONS"
    echo -e "     -u USER  database user. '$DBUSER' by default. Prompts if DB access fails"
    echo -e "     -p PASS  database password. 'No password' or 'vimpw' by default. Prompts if DB access fails"
    echo -e "     -P PORT  database port. '$DBPORT' by default"
    echo -e "     -h HOST  database host. '$DBHOST' by default"
    echo -e "     -d NAME  database name. '$DBNAME' by default.  Prompts if DB access fails"
    echo -e "     --help   shows this help"
}

while getopts ":u:p:P:h:d:-:" o; do
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

#Creating temporary file
TEMPFILE="$(mktemp -q --tmpdir "initmanodb.XXXXXX")"
trap 'rm -f "$TEMPFILE"' EXIT
chmod 0600 "$TEMPFILE"

#if password is missing, before prompting for it try without password and with "manopw"
DBHOST_="-h$DBHOST"
DBPORT_="-P$DBPORT"
DEF_EXTRA_FILE_PARAM="--defaults-extra-file=$TEMPFILE"
if [ -z "${DBPASS}" ]
then
    password_ok=""
    echo -e "[client]\nuser='${DBUSER}'\npassword=vimpw" > "$TEMPFILE"
    mysql --defaults-extra-file="$TEMPFILE" $DBHOST_ $DBPORT_ $DBNAME -e "quit" >/dev/null 2>&1 && DBPASS="vimpw"
    echo -e "[client]\nuser='${DBUSER}'\npassword=''" > "$TEMPFILE"
    mysql --defaults-extra-file="$TEMPFILE" $DBHOST_ $DBPORT_ $DBNAME -e "quit" >/dev/null 2>&1 && DBPASS=""
fi
echo -e "[client]\nuser='${DBUSER}'\npassword='${DBPASS}'" > "$TEMPFILE"

#check and ask for database user password
while ! mysql "$DEF_EXTRA_FILE_PARAM" $DBHOST_ $DBPORT_ $DBNAME -e "quit" >/dev/null 2>&1
do
        [ -n "$logintry" ] &&  echo -e "\nInvalid database credentials!!!. Try again (Ctrl+c to abort)"
        [ -z "$logintry" ] &&  echo -e "\nProvide database name and credentials"
        read -e -p "mysql database name($DBNAME): " KK
        [ -n "$KK" ] && DBNAME="$KK"
        read -e -p "mysql user($DBUSER): " KK
        [ -n "$KK" ] && DBUSER="$KK"
        read -e -s -p "mysql password: " DBPASS
        echo -e "[client]\nuser='${DBUSER}'\npassword='${DBPASS}'" > "$TEMPFILE"
        logintry="yes"
        echo
done

DBCMD="mysql $DEF_EXTRA_FILE_PARAM $DBHOST_ $DBPORT_ $DBNAME"
DBUSER_="-u$DBUSER"
DBPASS_="-p$DBPASS"


echo "    loading ${DIRNAME}/vim_db_structure.sql"
sed -e "s/vim_db/$DBNAME/" ${DIRNAME}/vim_db_structure.sql |  mysql $DEF_EXTRA_FILE_PARAM $DBHOST_ $DBPORT_

echo "    migrage database version"
#${DIRNAME}/migrate_vim_db.sh $DBHOST_ $DBPORT_ $DBUSER_ $DBPASS_ -d$DBNAME $1
DIRNAME=$(dirname $(readlink -f ${BASH_SOURCE[0]}))
echo "${DIRNAME}/migrate_vim_db.sh $DBHOST_ $DBPORT_ $DBUSER_ $DBPASS_ -d$DBNAME $1"
${DIRNAME}/migrate_vim_db.sh $DBHOST_ $DBPORT_ $DBUSER_ $DBPASS_ -d$DBNAME $1

echo  "    loading ${DIRNAME}/host_ranking.sql"
mysql $DEF_EXTRA_FILE_PARAM $DBHOST_ $DBPORT_ $DBNAME < ${DIRNAME}/host_ranking.sql

echo  "    loading ${DIRNAME}/of_ports_pci_correspondence.sql"
mysql $DEF_EXTRA_FILE_PARAM $DBHOST_ $DBPORT_ $DBNAME < ${DIRNAME}/of_ports_pci_correspondence.sql
#mysql -h $HOST -P $PORT -u $MUSER -p$MPASS $MDB < ${DIRNAME}/of_ports_pci_correspondence_centos.sql

echo  "    loading ${DIRNAME}/nets.sql"
mysql $DEF_EXTRA_FILE_PARAM $DBHOST_ $DBPORT_ $DBNAME < ${DIRNAME}/nets.sql

