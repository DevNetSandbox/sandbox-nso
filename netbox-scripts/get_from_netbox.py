import pynetbox
import os
import ipaddress

netbox_token = os.getenv("NETBOX_TOKEN")
netbox_url = os.getenv("NETBOX_URL")

netbox = pynetbox.api(netbox_url, token=netbox_token)

site_name = os.getenv("NETBOX_SITE")
tenant_group_name = os.getenv("NETBOX_TENANT_GROUP")

site = netbox.dcim.sites.get(name=site_name)
tenant_group = netbox.tenancy.tenant_groups.get(name=tenant_group_name)

admin_tenant = netbox.tenancy.tenants.get(name="{} Admin".format(site_name), tenant_group_id=tenant_group.id)
admin_private_tenant = netbox.tenancy.tenants.get(name="{} Admin-Private".format(site_name), tenant_group_id=tenant_group.id)
dmz01_tenant = netbox.tenancy.tenants.get(name="{} DMZ01".format(site_name), tenant_group_id=tenant_group.id)
dmz02_tenant = netbox.tenancy.tenants.get(name="{} DMZ02".format(site_name), tenant_group_id=tenant_group.id)
edge_tenant = netbox.tenancy.tenants.get(name="{} Edge".format(site_name), tenant_group_id=tenant_group.id)
shared_services_tenant = netbox.tenancy.tenants.get(name="{} Shared Services".format(site_name), tenant_group_id=tenant_group.id)
pod_tenants = netbox.tenancy.tenants.filter(q="{} Pod".format(site_name), tenant_group_id=tenant_group.id)

internal_vlan_group = netbox.ipam.vlan_groups.get(site_id=site.id, name="Internal")
dmz01_vlan_group = netbox.ipam.vlan_groups.get(site_id=site.id, name="DMZ01")
dmz02_vlan_group = netbox.ipam.vlan_groups.get(site_id=site.id, name="DMZ02")
edge_vlan_group = netbox.ipam.vlan_groups.get(site_id=site.id, name="Edge")

def get_devices(site, tenant, name=None): 

    # Get devices for site
    if name: 
        devices = netbox.dcim.devices.filter(site_id=site.id, tenant_id=tenant.id, name=name)
    else: 
        devices = netbox.dcim.devices.filter(site_id=site.id, tenant_id=tenant.id)

    # Fill in details
    for device in devices:
        device.interfaces = netbox.dcim.interfaces.filter(device_id=device.id)
        for interface in device.interfaces:
            interface.ip_addresses = netbox.ipam.ip_addresses.filter(
                interface_id=interface.id
            )
            for ip_address in interface.ip_addresses:
                ip_address.ip = ipaddress.ip_address(
                    ip_address.address.split("/")[0]
                )
                ip_address.network = ipaddress.ip_network(
                    ip_address.address, strict=False
                )
    return devices

# /virtualization/virtual-machines/?q=&site=usw1-preprod&tenant=usw1-preprod-admin
def get_vms(site, tenant): 
    vms = netbox.virtualization.virtual_machines.filter(site_id=site.id, tenant_id=tenant.id)

    # Fill in details
    for vm in vms:
        vm.interfaces = netbox.virtualization.interfaces.filter(virtual_machine_id=vm.id)
        for interface in vm.interfaces:
            interface.ip_addresses = netbox.ipam.ip_addresses.filter(
                interface_id=interface.id
            )
            for ip_address in interface.ip_addresses:
                ip_address.ip = ipaddress.ip_address(
                    ip_address.address.split("/")[0]
                )
                ip_address.network = ipaddress.ip_network(
                    ip_address.address, strict=False
                )

    return vms

def get_vlans(site, vlan_group, tenant=None): 
    # Get VLAN Info from Netbox
    if tenant: 
        vlans = netbox.ipam.vlans.filter(site_id=site.id, group_id=vlan_group.id, tenant_id=tenant.id)
    else: 
        vlans = netbox.ipam.vlans.filter(site_id=site.id, group_id=vlan_group.id)

    vlan_ids = [vlan.id for vlan in vlans]

    # Get all prefixes for all vlans, single API call. 
    prefixes = netbox.ipam.prefixes.filter(site_id = site.id, vlan_id = vlan_ids)
    prefixes_by_vlan_id = { prefix.vlan.id:prefix for prefix in prefixes }

    # Match Prefixes for VLANs
    for vlan in vlans:
        try:
            vlan.prefix = prefixes_by_vlan_id[vlan.id]
        except Exception as e:
            print(e)
        # print("VLAN ID: {} Name {}".format(vlan.vid, vlan.name))

    return vlans 

def device_interfaces_from_template(device): 
    # get current interfaces for devices 
    device_interfaces = netbox.dcim.interfaces.filter(device_id=device.id)

    if len(device_interfaces) == 0: 
        # get device template 
        device_type = netbox.dcim.device_types.get(device.device_type.id)

        # get interfaces for template 
        device_type_interfaces = netbox.dcim.interface_templates.filter(devicetype_id=device_type.id)

        # create interfaces on device 
        if len(device_type_interfaces) > 0: 
            for interface_template in device_type_interfaces: 
                new_interface = netbox.dcim.interfaces.create(
                    device=device.id, 
                    name=interface_template.name, 
                    type=interface_template.type.value, 
                    mgmt_only=interface_template.mgmt_only,
                )

    return netbox.dcim.interfaces.filter(device_id=device.id)

def device_console_from_template(device): 
    # get current interfaces for devices 
    device_console_ports = netbox.dcim.console_ports.filter(device_id=device.id)

    if len(device_console_ports) == 0: 
        # get device template 
        device_type = netbox.dcim.device_types.get(device.device_type.id)

        # get interfaces for template 
        device_type_console_ports = netbox.dcim.console_port_templates.filter(devicetype_id=device_type.id)

        # create interfaces on device 
        if len(device_type_console_ports) > 0: 
            for console_template in device_type_console_ports: 
                new_interface = netbox.dcim.console_ports.create(
                    device=device.id, 
                    name=console_template.name, 
                )

    return netbox.dcim.console_ports.filter(device_id=device.id)    

def device_power_port_from_template(device): 
    # get current interfaces for devices 
    device_power_ports = netbox.dcim.power_ports.filter(device_id=device.id)

    if len(device_power_ports) == 0: 
        # get device template 
        device_type = netbox.dcim.device_types.get(device.device_type.id)

        # get interfaces for template 
        device_type_power_ports = netbox.dcim.power_port_templates.filter(devicetype_id=device_type.id)

        # create interfaces on device 
        if len(device_type_power_ports) > 0: 
            for template in device_type_power_ports: 
                new_interface = netbox.dcim.power_ports.create(
                    device=device.id, 
                    name=template.name, 
                )

    return netbox.dcim.power_ports.filter(device_id=device.id)        