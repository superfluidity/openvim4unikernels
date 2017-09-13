For launch openvim pytest regresion:

    pytest -v -s test/test_openvim_inf.py --config=test/test_openvim_fake.yaml

The regresion must be launch from an user included in the visudo.
If the regression will be use real infrastructure (fake_mode=False) create a new yaml or modify
the existing template -> test/test_openvim_fake.yaml


test.yaml example:

---
host:
   host_1: <path_to_host_descriptor_1>
   host_2: <path_to_host_descriptor_1>
   host_n: <path_to_host_descriptor_1>
tenant: test/tenants/test_tenant.yaml
flavor: test/flavors/cirros_flavor.yaml
image: <path_to_iamge_descriptor>
server: test/servers/cirros_server_template.yaml
net: test/networks/net-example5.yaml
fake_mode:  <True/False>                     # depend on openvimd.cfg mode (test,normal, host only, OF only, development)
create_inf: <True/False>                     # Create host and mgmt net if True, if False host and mgmt net need to be precreated.
