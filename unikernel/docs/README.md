# OpenVIM for  Unikernels edition

OpenVIM for Unikernels edition can startup unikernels VMs such as ClickOS.

The OpenVIM for Unikernels main features are:
- Xen hypervisor support for the VMs bootup
- Unikernels support with Xen (main focus on ClickOS)
- Full HVM machines with Xen
- Boot of Unikernels VMs and HVM VMs on the same compute node
- Networking review to adapt it on the requirements of our testbed

This OpenVIM patch is developed on our testbed that, for its functional features, is not fully compliant with the EPA requirements of the normal OpenVIM version.

For this reason is added a new mode called .unikernel.. This mode excludes the not compliant features with our testbed and simplify the network part to meet our requirements.

The backward compatibility with the original OpenVIM.s mode (_normal_, _test_, _host only_, _OF only_, _development_) is granted in this version. The Unikernels mode is an extension of othe riginal development mode that excludes the EPA features, but enables the Xen hypervisor support and redesign the networking part for our testbed.

# Installation: Clean install
To perform a clean installation of OpenVIM download the patch version of OpenVIM in your system from our repository::

        $ git clone https://github.com/superfluidity/openvim-unikernels.git
        $ cd openvim/scripts
        openvim/scripts$ ./install-openvim.sh --noclone
        openvim/scripts$ git checkout unikernel
        openvim/scripts$ cd ../..
        $ ./unikernels_patch_vim_db.sh -u vim -p vimpw install
        
The credentials above and the database name is set to default value. If the values are different from the default ones, update them with the correct data. To reverse the process type uninstall. For more information type --help.
After updating the database, you can start the OpenVIM as usual.


