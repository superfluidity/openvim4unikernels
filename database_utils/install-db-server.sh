#!/usr/bin/env bash

function usage(){
    echo -e "usage: sudo $0 [OPTIONS]"
    echo -e "Install openvim database server"
    echo -e "  OPTIONS"
    echo -e "     -U USER:    database admin user. 'root' by default. Prompts if needed"
    echo -e "     -P PASS:    database admin password to be used or installed. Prompts if needed"
    echo -e "     -d: d database name, default name  vim_db"
    echo -e "     -u: database user, default name  vim"
    echo -e "     -p: database pass, default name  vimpw"
    echo -e "     -q --quiet: install in unattended mode"
    echo -e "     -h --help:  show this help"
    echo -e "     --forcedb:  reinstall vim_db DB, deleting previous database if exists and creating a new one"
    echo -e "     --no-install-packages: <deprecate> use this option to skip updating and installing the requires packages. This avoid wasting time if you are sure requires packages are present e.g. because of a previous installation"
    echo -e "     --unistall: Delete DB, by default vim_db"


}

function _create_db(){
    echo '
    #################################################################
    #####               CREATE DATABASE                         #####
    #################################################################'
    echo -e "\nCreating temporary file for MYSQL installation and initialization"
    TEMPFILE="$(mktemp -q --tmpdir "installopenvim.XXXXXX")"
    trap 'rm -f "$TEMPFILE"' EXIT
    chmod 0600 "$TEMPFILE"
    echo -e "[client]\n user='${DB_ADMIN_USER}'\n password='$DB_ADMIN_PASSWD'">"$TEMPFILE"

    if db_exists $DB_NAME $TEMPFILE ; then
        if [[ -n $FORCEDB ]]; then
            DBDELETEPARAM=""
            [[ -n $QUIET_MODE ]] && DBDELETEPARAM="-f"
            mysqladmin  --defaults-extra-file=$TEMPFILE -s drop ${DB_NAME} $DBDELETEPARAM || ! echo "Could not delete ${DB_NAME} database" || exit 1
            mysqladmin  --defaults-extra-file=$TEMPFILE -s create ${DB_NAME} || ! echo "1 Error creating ${DB_NAME} database" || exit 1
            echo "CREATE USER $DB_USER@'localhost' IDENTIFIED BY '$DB_PASS';"   | mysql --defaults-extra-file=$TEMPFILE -s || ! echo "2 Failed while creating user ${DB_USER}"
            echo "GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO $DB_USER@'localhost';" | mysql --defaults-extra-file=$TEMPFILE -s || ! echo "3 Failed while granting privileges to user ${DB_USER} at database ${DB_NAME}" || exit 1
            echo " Database '${DB_NAME}' created, user $DB_USER password '$DB_PASS'"
        else
            echo "Database exists. Use option '--forcedb' to force the deletion of the existing one" && exit 1
        fi
    else
        echo "mysqladmin -u$DB_ADMIN_USER $DBPASSWD_PARAM -s create ${DB_NAME}"

        mysqladmin -u$DB_ADMIN_USER $DBPASSWD_PARAM -s create ${DB_NAME} || ! echo "4 Error creating ${DB_NAME} database" || exit 1
        echo "CREATE USER $DB_USER@'localhost' IDENTIFIED BY '$DB_PASS';"   | mysql --defaults-extra-file=$TEMPFILE -s || ! echo "Failed while creating user vim at database"
        echo "GRANT ALL PRIVILEGES ON ${DB_NAME}.* TO $DB_USER@'localhost';" | mysql --defaults-extra-file=$TEMPFILE -s || ! echo "Failed giving creating user vim at database" || exit 1
        echo " Database '${DB_NAME}' created, user $DB_USER password '$DB_PASS'"
    fi
}

function _init_db(){
    echo '
    #################################################################
    #####        INIT DATABASE                                  #####
    #################################################################'
    DIRNAME=$(dirname $(readlink -f ${BASH_SOURCE[0]}))
    su $SUDO_USER -c "${DIRNAME}/init_vim_db.sh -u $DB_USER -p $DB_PASS -d ${DB_NAME}" || ! echo "Failed while initializing database" || exit 1
}

function _uninstall_db(){
echo '
    #################################################################
    #####        DELETE DATABASE                                #####
    #################################################################'
    DBDELETEPARAM=""
    [[ -n $QUIET_MODE ]] && DBDELETEPARAM="-f"
    mysqladmin  --defaults-extra-file=$TEMPFILE -s drop ${DB_NAME} $DBDELETEPARAM || ! echo "Could not delete ${DB_NAME} database" || exit 1

}
function db_exists() {
    RESULT=`mysqlshow --defaults-extra-file="$2" | grep -v Wildcard | grep -o $1`
    if [ "$RESULT" == "$1" ]; then
        echo " DB $1 exists"
        return 0
    fi
    echo " DB $1 does not exist"
    return 1
}
DB_NAME='vim_db'
DB_ADMIN_USER="root"
DB_USER="vim"
DB_PASS="vimpw"
DB_ADMIN_PASSWD=""
DBPASSWD_PARAM=""
QUIET_MODE=""
FORCEDB=""
NO_PACKAGES=""
UNINSTALL=""
while getopts ":U:P:d:u:p:hiq-:" o; do
    case "${o}" in
        U)
            export DB_ADMIN_USER="$OPTARG"
            ;;
        P)
            export DB_ADMIN_PASSWD="$OPTARG"
            export DBPASSWD_PARAM="-p$OPTARG"
            ;;
        d)
            export DB_NAME="$OPTARG"
            ;;
        u)
            export DB_USER="$OPTARG"
            ;;
        p)
            export DB_PASS="$OPTARG"
            ;;
        q)
            export QUIET_MODE=yes
            export DEBIAN_FRONTEND=noninteractive
            ;;
        h)
            usage && exit 0
            ;;
        -)
            [ "${OPTARG}" == "help" ] && usage && exit 0
            [ "${OPTARG}" == "forcedb" ] && FORCEDB="y" && continue
            [ "${OPTARG}" == "quiet" ] && export QUIET_MODE=yes && export DEBIAN_FRONTEND=noninteractive && continue
            [ "${OPTARG}" == "no-install-packages" ] && export NO_PACKAGES=yes && continue
            [ "${OPTARG}" == "uninstall" ] &&  UNINSTALL="y" && continue
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
            exit 1
            ;;
    esac
done

HERE=$(realpath $(dirname $0))
OPENVIM_BASEFOLDER=$(dirname $HERE)
[ "$USER" != "root" ] && echo "Needed root privileges" >&2 && exit -1

if [[ -z "$SUDO_USER" ]] || [[ "$SUDO_USER" = "root" ]]
then
    export SUDO_USER='root'
fi

#Discover Linux distribution
#try redhat type
[ -f /etc/redhat-release ] && _DISTRO=$(cat /etc/redhat-release 2>/dev/null | cut  -d" " -f1)
#if not assuming ubuntu type
[ -f /etc/redhat-release ] || _DISTRO=$(lsb_release -is  2>/dev/null)

#check and ask for database user password. Must be done after database installation
if [[ -n $QUIET_MODE ]]
then
    echo -e "\nCheking database connection and ask for credentials"
    echo "mysqladmin -s -u$DB_ADMIN_USER $DBPASSWD_PARAM status >/dev/null"
    while ! mysqladmin -s -u$DB_ADMIN_USER $DBPASSWD_PARAM status >/dev/null
    do
        [ -n "$logintry" ] &&  echo -e "\nInvalid database credentials!!!. Try again (Ctrl+c to abort)"
        [ -z "$logintry" ] &&  echo -e "\nProvide database credentials"
        read -e -p "database user? ($DB_ADMIN_USER) " DBUSER_
        [ -n "$DBUSER_" ] && DB_ADMIN_USER=$DBUSER_
        read -e -s -p "database password? (Enter for not using password) " DBPASSWD_
        [ -n "$DBPASSWD_" ] && DB_ADMIN_PASSWD="$DBPASSWD_" && DBPASSWD_PARAM="-p$DBPASSWD_"
        [ -z "$DBPASSWD_" ] && DB_ADMIN_PASSWD=""           && DBPASSWD_PARAM=""
        logintry="yes"
    done
fi

if [[ ! -z "$UNINSTALL" ]]
then
    _uninstall_db
    exit
fi


if [[ -z "$NO_PACKAGES" ]]
then
    _create_db
    _init_db
fi


