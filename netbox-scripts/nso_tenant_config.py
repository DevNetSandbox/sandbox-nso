
from get_from_netbox import * 
from jinja2 import Template, Environment, FileSystemLoader

def interface_details(interface): 

    if interface.find("Ethernet") >= 0: 
        offset = interface.find("Ethernet")+8
    elif interface.find("Port-channel") >= 0: 
        offset = interface.find("Port-channel")+12

    interface_type = interface[0:offset]
    interface_num = interface[offset:]

    return (interface_type, interface_num)

def interface_num(interface): 
    return interface_details(interface)[1]

def build_nso_tenant_config(vlan_tenant): 

    # Make sure the vlan_tenant details are valid 
    if vlan_tenant["vlan-group"] is None or vlan_tenant["tenant"] is None: 
        return None

    # TODO: Missing Static Routes 
    vlans = get_vlans(site, vlan_tenant["vlan-group"], vlan_tenant["tenant"])

    vlan_configs = nso_tenant_network_config(vlans)

    with open("nso_generated_configs/vlan-tenant_{vlan_tenant}.xml".format(vlan_tenant=vlan_tenant["name"]), "w") as f: 
        xml_config = vlan_tenant_template.render(vlan_tenant = vlan_tenant, vlans = vlan_configs)
        f.write(xml_config)
    with open("nso_generated_configs/vlan-tenant_{vlan_tenant}.cfg".format(vlan_tenant=vlan_tenant["name"]), "w") as f: 
        xml_config = vlan_tenant_template_cli.render(vlan_tenant = vlan_tenant, vlans = vlan_configs)
        f.write(xml_config)

    # return (vlans, vlan_configs)




def nso_tenant_network_config(vlans): 
    network_config = ""

    # problem with effecient searh for connections, api/sdk only uses last element in list
    # need to look at other options to be more efficient 
    # vlan_ids = [vlan.id for vlan in vlans]

    # all_connections = netbox.dcim.interfaces.filter(vlan_id=vlan_ids)

    # vlan_connections = {}

    # for connection in all_connections: 
    #     for tagged in connection.tagged_vlans: 
    #         if tagged.id not in vlan_connections:
    #             vlan_connections[tagged.id] = [connection]
    #         else: 
    #             vlan_connections[tagged.id].append(connection)

    #     if connection.untagged_vlan: 
    #         if connection.untagged_vlan.id not in vlan_connections:
    #             vlan_connections[connection.untagged_vlan.id] = [connection]
    #         else: 
    #             vlan_connections[connection.untagged_vlan.id].append(connection)

    for vlan in vlans: 
        # try: 
        #     vlan.connections = vlan_connections[vlan.id]
        # except KeyError:
        #     vlan.connections = None

        # Using above logit to reduce number of API calls
        # connections = netbox.dcim.interfaces.filter(vlan_id=vlan.id)
        vlan.connections = netbox.dcim.interfaces.filter(vlan_id=vlan.id)

        switch_pairs_done = []
        for connection in vlan.connections: 
            if not connection.device.device_role.name in ["Access Switch", "Spine Switch", "Border Switch", "Distributed Virtual Switch - VIRL", "Distribution Switch"]: 
                continue

            interface_num = interface_details(connection.name)[1]
            connection.num = interface_details(connection.name)[1]

            if connection.form_factor.label == "Link Aggregation Group (LAG)":
                # Interfaces in port-channel
                lag_members = netbox.dcim.interfaces.filter(lag_id=connection.id)
                connection.lag_members = netbox.dcim.interfaces.filter(lag_id=connection.id)
                for member in lag_members: 
                    member_num = interface_details(member.name)[1]
                    member.member_num = interface_details(member.name)[1]

    return vlans

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()

    parser.add_argument("--tenant", action="append", help="What tenant to build the config for.")
    parser.add_argument("--not_tenant", action="append", help="What tenants to skip configurations for.")

    args = parser.parse_args()

    jinja_env = Environment(
        loader=FileSystemLoader(searchpath="."), 
        trim_blocks=False, 
        lstrip_blocks=False
    )
    jinja_env.filters["interface_num"] = interface_num
    vlan_tenant_template = jinja_env.get_template("templates/nso-vlan-tenant.xml.j2")
    vlan_tenant_template_cli = jinja_env.get_template("templates/nso-vlan-tenant.cfg.j2")

    # with open("templates/nso-vlan-tenant.xml.j2") as f: 
    #     vlan_tenant_template = Template(f.read())

    vlan_tenants = [
        {"name": "admin", "fabric": "internal", "tenant": admin_tenant, "vlan-group": internal_vlan_group}, 
        {"name": "admin-private", "fabric": "internal", "tenant": admin_private_tenant, "vlan-group": internal_vlan_group}, 
        {"name": "shared-services", "fabric": "internal", "tenant": shared_services_tenant, "vlan-group": internal_vlan_group}, 

        {"name": "dmz02", "fabric": "dmz02", "tenant": dmz02_tenant, "vlan-group": dmz02_vlan_group}, 
        {"name": "dmz01", "fabric": "dmz01", "tenant": dmz01_tenant, "vlan-group": dmz01_vlan_group}, 
        {"name": "edge", "fabric": "edge", "tenant": edge_tenant, "vlan-group": edge_vlan_group}, 
    ]



    for pod_tenant in pod_tenants:
        vlan_tenants.append(
            {"name": pod_tenant.name.replace(site.name, "").strip().lower().replace(" ", ""), "fabric": "internal", "tenant": pod_tenant, "vlan-group": internal_vlan_group}
        )

    for vlan_tenant in vlan_tenants: 
        if args.not_tenant and vlan_tenant["name"] in args.not_tenant: 
            print("❌❌ Skipping Tenant: {} because listed in `not_tenant`".format(vlan_tenant["name"]))
        elif args.tenant is None or vlan_tenant["name"] in args.tenant: 
            print("✅  Processing Tenant: {}".format(vlan_tenant["name"]))
            build_nso_tenant_config(vlan_tenant)
        else: 
            print("❌  Skipping Tenant: {} because it was NOT listed in `tenant`".format(vlan_tenant["name"]))