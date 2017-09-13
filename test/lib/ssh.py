import subprocess
import pexpect


def execute_local(cmd):
    """
    Execute a command in locally    
    :param cmd: command to be executed
    :return: 
    """

    print "execute_local cmd = {}".format(cmd)
    p = subprocess.Popen(['bash', "-c", cmd], stdout=subprocess.PIPE)
    out = p.stdout.read()
    print "execute_local result = {}".format(out)
    return out


def execute_namespace(vlan, cmd):
    """
    Execute a command inside a namespace created by openvim 
    :param vlan: namespace id
    :param cmd: command to be executed
    :return: 
    """

    n_cmd = 'sudo ip netns exec {}-qrouter {} '.format(vlan, cmd)
    return execute_local(n_cmd)


def ping_ok(vlan_id, ip, retries=200):
    """

    :param vlan_id: namespace id
    :param ip: vm ip to be pinged
    :param retries: retries, by default 200
    :return: 
    """
    print 'waiting for vm to be active vm with ip = {}'.format(ip)
    for i in xrange(retries):
        try:
            subprocess.check_output(['bash', "-c", "sudo ip netns exec {}-qrouter ping -c 1 {}".format(vlan_id, ip)])
            return True
        except Exception, e:
            pass
    return False


def ping_ok_btw_2_vms(vlan_id, ip_1, ip_2, retires=8):
    """
    Check net connectivity between to VM
    :param vlan_id: namepsace id
    :param ip_1: first vm ip
    :param ip_2: second vm ip
    :param retires: 
    :return: 
    """
    for i in xrange(retires):

        try:
            ns_cmd = 'sudo ip netns exec {}-qrouter '.format(vlan_id)
            cmd = ns_cmd + ' ssh -oStrictHostKeyChecking=no cirros@{} "ping -c 1 {}"'.format(ip_1, ip_2)
            child = pexpect.spawn(cmd)
            child.expect('.*assword*')
            child.sendline('cubswin:)')
            child.sendline('cubswin:)')

            cmd = ns_cmd + ' ssh -oStrictHostKeyChecking=no  cirros@{} "ping -c 1 {}"'.format(ip_2, ip_1)
            child = pexpect.spawn(cmd)
            child.expect('.*assword*')
            child.sendline('cubswin:)')
            child.sendline('cubswin:)')

        except EOFError as e:
            if i == retires:
                return False
            pass

    return True


def copy_rsa_keys_into_vm(vlan_id, ip, rsa_key_path):
    """
    copy an RSA key given by the user to a vm 
    :param vlan_id: 
    :param ip: 
    :param rsa_key_path: 
    :return: 
    """

    try:
        execute_local('sudo ssh-keygen -f "/root/.ssh/known_hosts" -R  {}'.format(ip))
        cmd = 'sudo ip netns exec {}-qrouter ssh-copy-id -i {} ' \
              '-oStrictHostKeyChecking=no -f cirros@{}'.format(vlan_id, rsa_key_path + '.pub', ip)

        print 'copy_rsa_keys_into_vm = ' + cmd
        child = pexpect.spawn(cmd)
        child.expect('.*assword*')
        child.sendline('cubswin:)')
        child.sendline('cubswin:)')
        return True
    except EOFError as e:
        return False


def execute_check_output(vlan_id, cmd):
    """
    Execute a command inside a namespace and raise an expection in case of command fail
    :param vlan_id: namepsace id
    :param cmd: command
    :return: 
    """
    try:
        cmd = "sudo ip netns exec {}-qrouter  {}".format(vlan_id, cmd)
        print "execute_check_output = {}".format(cmd)
        subprocess.check_output(['bash', "-c", cmd])
        return True
    except Exception, e:
        print "error execute_check_output"
        return False






