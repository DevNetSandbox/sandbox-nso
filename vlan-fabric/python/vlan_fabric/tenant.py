# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.application import Service

# import resource_manager.id_allocator as id_allocator
import ipaddress


# ------------------------
# SERVICE CALLBACK EXAMPLE
# ------------------------
class ServiceCallbacks(Service):

    # The create() callback is invoked inside NCS FASTMAP and
    # must always exist.
    @Service.create
    def cb_create(self, tctx, root, service, proplist):
        self.log.info("Service create(service=", service._path, ")")

        vars = ncs.template.Variables()
        vars.add("DUMMY", "127.0.0.1")
        template = ncs.template.Template(service)

        disable_trunk_negotiation = False

        # PHASE - Get Fabric Member Devices
        # primary_ip_address = root.devices.device[pair.primary].config.interface.mgmt["0"].ip.address.ipaddr
        switch_pairs = root.vlan_fabric[service.fabric].switch_pair
        switches = root.vlan_fabric[service.fabric].switch
        # Initialize with NONE
        border_pair = None
        self.log.info("Switches for Fabric {} are: ".format(service.fabric))
        for pair in switch_pairs:
            self.log.info(
                "Pair: {} Primary {} Secondary {}".format(
                    pair.name, pair.primary, pair.secondary
                )
            )
            if pair.layer3:
                border_pair = pair
                self.log.info(
                    "Layer 3 Switch Pair is {} Primary {} Secondary {}".format(
                        pair.name, pair.primary, pair.secondary
                    )
                )

        self.log.info(
            "Switches for Fabric {} are {}".format(service.fabric, switches.__dict__)
        )
        for switch in switches:
            self.log.info("Switch: {}".format(switch.device))

        # PHASE - Get Fabric Interconnect Resources for Fabric
        fabric_interconnects = root.vlan_fabric[service.fabric].fabric_interconnect
        self.log.info("Fabric Interconnects for Fabric {} are:".format(service.fabric))
        for fabric_interconnect in fabric_interconnects:
            self.log.info("FI: {}".format(fabric_interconnect.device))

        # PHASE - Get VMwar DVS Resources for Fabric
        vswitches = root.vlan_fabric[service.fabric].vmware_dvs
        self.log.info(
            "VMware Distributed vSwitches for Fabric {} are:".format(service.fabric)
        )
        for vswitch in vswitches:
            self.log.info(
                "vCenter {} Datacenter {} dVS {}".format(
                    vswitch.vcenter, vswitch.datacenter, vswitch.dvs
                )
            )

        # PHASE - Configure Static Routes if configured
        if border_pair:
            routing_vars = ncs.template.Variables()
            routing_vars.add("VRFNAME", service.name)

            # PHASE - Static routes
            for route in service.static_routes:
                # self.log.info("Setting up static route for {} to {} in VRF {}".format(route.network, route.gateway, service.name))
                routing_vars.add("STATIC_ROUTE_NETWORK", route.network)
                routing_vars.add("STATIC_ROUTE_GATEWAY", route.gateway)

                # PRIMARY
                self.log.info(
                    "Setting up static route for {} to {} in VRF {} on switch_pair {} Primary Device {}".format(
                        route.network,
                        route.gateway,
                        service.name,
                        border_pair,
                        border_pair.primary,
                    )
                )
                routing_vars.add("DEVICE_NAME", border_pair.primary)
                self.log.info("routing_vars={}".format(routing_vars))
                template.apply("vrf-static-routes", routing_vars)
                # Secondary
                if border_pair.secondary:
                    self.log.info(
                        "Setting up static route for {} to {} in VRF {} on switch_pair {} Primary Device {}".format(
                            route.network,
                            route.gateway,
                            service.name,
                            border_pair,
                            border_pair.secondary,
                        )
                    )
                    routing_vars.add("DEVICE_NAME", border_pair.secondary)
                    template.apply("vrf-static-routes", routing_vars)

        else:
            self.log.info(
                "Note: Fabric {} has NO Layer 3 Border Pair.".format(service.fabric)
            )

        # PHASE Process Each Network in Service
        for network in service.network:
            # PHASE - Add VLANS to all Fabric Switches
            self.log.info(
                "Adding VLAN {} for Network {}".format(network.name, network.vlanid)
            )
            network_vars = ncs.template.Variables()
            network_vars.add("VLAN_ID", network.vlanid)
            network_vars.add("VLAN_NAME", network.name)

            for pair in switch_pairs:
                self.log.info(
                    "Adding VLAN for Pair: {} Primary {} Secondary {}".format(
                        pair.name, pair.primary, pair.secondary
                    )
                )
                # PRIMARY
                network_vars.add("DEVICE_NAME", pair.primary)
                template.apply("vlan-new", network_vars)
                if pair.secondary:

                    # Secondary
                    network_vars.add("DEVICE_NAME", pair.secondary)
                    template.apply("vlan-new", network_vars)
            for switch in switches:
                self.log.info("Adding VLAN for Switch: {}".format(switch.device))
                network_vars.add("DEVICE_NAME", switch.device)
                template.apply("vlan-new", network_vars)

            # PHASE - Configure Layer 3 For Network
            # Check if layer3-on-fabric is configured for network
            if network.layer3_on_fabric:
                self.log.info(
                    "Configuring Layer 3 for {} IP Network {} ".format(
                        network.name, network.network
                    )
                )
                ipnet = ipaddress.ip_network(network.network)
                hsrp_ipv4 = ipnet.network_address + 1
                primary_ipv4 = ipnet.network_address + 2
                secondary_ipv4 = ipnet.network_address + 3
                network_vars.add("VRFNAME", service.name)
                network_vars.add("HSRP_GROUP", 1)
                network_vars.add("HSRP_IPV4", hsrp_ipv4)
                if network.build_route_neighbors:
                    network_vars.add("BUILD_ROUTING_NEIGHBOR", "True")
                else:
                    network_vars.add("BUILD_ROUTING_NEIGHBOR", "")

                # PRIMARY
                network_vars.add("DEVICE_NAME", border_pair.primary)
                network_vars.add(
                    "SVI_IPV4", "{}/{}".format(primary_ipv4, ipnet.prefixlen)
                )
                network_vars.add("HSRP_PRIORITY", 110)
                template.apply("vlan-layer3", network_vars)

                if network.dhcp_relay_address: 
                    network_vars.add("DHCP_RELAY_ADDRESS", network.dhcp_relay_address)
                    self.log.info("Configuring DHCP Relay address {} for {} IP Network {} ".format(
                            network.dhcp_relay_address, network.name, network.network
                        )
                    )
                    template.apply("vlan-layer3-dhcp-relay", network_vars)

                if border_pair.secondary:
                    # Secondary
                    network_vars.add("DEVICE_NAME", border_pair.secondary)
                    network_vars.add(
                        "SVI_IPV4", "{}/{}".format(secondary_ipv4, ipnet.prefixlen)
                    )
                    network_vars.add("HSRP_PRIORITY", 90)
                    template.apply("vlan-layer3", network_vars)
                    if network.dhcp_relay_address: 
                        network_vars.add("DHCP_RELAY_ADDRESS", network.dhcp_relay_address)
                        self.log.info("Configuring DHCP Relay address {} for {} IP Network {} ".format(
                                network.dhcp_relay_address, network.name, network.network
                            )
                        )
                        template.apply("vlan-layer3-dhcp-relay", network_vars)

            else:
                self.log.info(
                    "Skipping Layer 3 configuration in fabric for {} IP Network {} ".format(
                        network.name, network.network
                    )
                )

            # PHASE Process Connections for Network
            # PHASE Switch Connections
            for switch in network.connections.switch:
                self.log.info(
                    "Adding Connections for Network {} on Switch {}".format(
                        network.name, switch.device
                    )
                )
                network_vars.add("DEVICE_NAME", switch.device)

                switch_platform = {}
                switch_platform["name"] = root.devices.device[
                    switch.device
                ].platform.name
                switch_platform["version"] = root.devices.device[
                    switch.device
                ].platform.version
                switch_platform["model"] = root.devices.device[
                    switch.device
                ].platform.model
                self.log.info("Switch Platform Info: {}".format(switch_platform))

                # For old IOS that supported DTP, need to disable negotiation
                if (
                    switch_platform["model"] != "NETSIM"
                    and switch_platform["name"] == "ios"
                    and int(switch_platform["version"][0:2]) < 16
                ):
                    disable_trunk_negotiation = True
                else:
                    disable_trunk_negotiation = False

                network_vars.add("DISABLE_TRUNK_NEGOTIATION", disable_trunk_negotiation)
                network_vars.add("MTU_SIZE", "9216")

                # PHASE Interfaces
                for interface in switch.interface:
                    self.log.info(
                        "Configuring Intereface {} for Network {} on Switch {}".format(
                            interface.interface, network.name, switch.device
                        )
                    )
                    network_vars.add("INTERFACE_ID", interface.interface)
                    network_vars.add("DESCRIPTION", interface.description)
                    network_vars.add("MODE", interface.mode)
                    network_vars.add("MTU_SIZE", "9216")
                    self.log.info("network_vars=", network_vars)
                    template.apply("tenant_network_interface", network_vars)

                # PHASE Port-Channels
                for port_channel in switch.port_channel:
                    self.log.info(
                        "Configuring PortChannel {} for Network {} on Switch {}".format(
                            port_channel.portchannel_id, network.name, switch.device
                        )
                    )
                    network_vars.add("PORTCHANNEL_ID", port_channel.portchannel_id)
                    network_vars.add("DESCRIPTION", port_channel.description)
                    network_vars.add("MODE", port_channel.mode)
                    network_vars.add("VPC", "")
                    self.log.info("network_vars=", network_vars)
                    template.apply("portchannel-interface", network_vars)

                    # PHASE Port-Channel Member Interfaces
                    for interface in port_channel.interface:
                        self.log.info(
                            "Adding Interface {} to Port-Channel {} on Network {} on Switch {}.".format(
                                interface.interface,
                                port_channel.portchannel_id,
                                network.name,
                                switch.device,
                            )
                        )
                        network_vars.add("INTERFACE_ID", interface.interface)
                        self.log.info("network_vars=", network_vars)
                        template.apply("portchannel-member-interface", network_vars)

            # PHASE Switch Pair connections
            for pair in network.connections.switch_pair:
                self.log.info(
                    "Adding Connections for Network {} on Switch Pair {}".format(
                        network.name, pair.name
                    )
                )
                # Lookup Pair from Fabric
                # switch_pairs = root.vlan_fabric[service.fabric].switch_pair
                this_pair = root.vlan_fabric[service.fabric].switch_pair[pair.name]
                self.log.info(
                    "Primary {} Secondary {}".format(
                        this_pair.primary, this_pair.secondary
                    )
                )

                # Nexus Leaf Pairs Always False
                disable_trunk_negotiation = False
                network_vars.add("DISABLE_TRUNK_NEGOTIATION", disable_trunk_negotiation)

                # PHASE Interfaces
                for interface in pair.interface:
                    self.log.info(
                        "Configuring Intereface {} for Network {} on Pair {}".format(
                            interface.interface, network.name, this_pair.name
                        )
                    )
                    network_vars.add("INTERFACE_ID", interface.interface)
                    network_vars.add("DESCRIPTION", interface.description)
                    network_vars.add("MODE", interface.mode)
                    network_vars.add("MTU_SIZE", "9216")

                    # Primary
                    network_vars.add("DEVICE_NAME", this_pair.primary)
                    self.log.info("network_vars=", network_vars)
                    template.apply("tenant_network_interface", network_vars)

                    if this_pair.secondary:
                        # Secondary
                        network_vars.add("DEVICE_NAME", this_pair.secondary)
                        self.log.info("network_vars=", network_vars)
                        template.apply("tenant_network_interface", network_vars)

                # PHASE Port-Channels
                for port_channel in pair.port_channel:
                    self.log.info(
                        "Configuring Port-Channel {} for Network {} on Pair {}".format(
                            port_channel.portchannel_id, network.name, this_pair.name
                        )
                    )
                    network_vars.add("PORTCHANNEL_ID", port_channel.portchannel_id)
                    network_vars.add("DESCRIPTION", port_channel.description)
                    network_vars.add("MODE", port_channel.mode)
                    network_vars.add("MTU_SIZE", "9216")
                    network_vars.add("VPC", True)

                    # Primary
                    network_vars.add("DEVICE_NAME", this_pair.primary)
                    self.log.info("network_vars=", network_vars)
                    template.apply("portchannel-interface", network_vars)

                    # Secondary
                    network_vars.add("DEVICE_NAME", this_pair.secondary)
                    self.log.info("network_vars=", network_vars)
                    template.apply("portchannel-interface", network_vars)

                    # PHASE Port-Channel Member Interfaces
                    for interface in port_channel.interface:
                        self.log.info(
                            "Adding Interface {} to Port-Channel {} on Network {} on Pair {}.".format(
                                interface.interface,
                                port_channel.portchannel_id,
                                network.name,
                                this_pair.name,
                            )
                        )
                        network_vars.add("INTERFACE_ID", interface.interface)

                        # Primary
                        network_vars.add("DEVICE_NAME", this_pair.primary)
                        self.log.info("network_vars=", network_vars)
                        template.apply("portchannel-member-interface", network_vars)

                        # Secondary
                        network_vars.add("DEVICE_NAME", this_pair.secondary)
                        self.log.info("network_vars=", network_vars)
                        template.apply("portchannel-member-interface", network_vars)

            # PHASE Fabric Interconnects
            for fabric_interconnect in fabric_interconnects:
                self.log.info(
                    "Configuring Network {} on Fabric Interconnect {}".format(
                        network.name, fabric_interconnect.device
                    )
                )
                ucs_vars = ncs.template.Variables()
                ucs_vars.add("DEVICE_NAME", fabric_interconnect.device)
                ucs_vars.add("VLAN_NAME", network.name)
                ucs_vars.add("VLAN_ID", network.vlanid)

                # PHASE - Add VLAN to Configuration
                self.log.info(
                    "Adding VLAN {} ({}) on Fabric Interconnect {}".format(
                        network.name, network.vlanid, fabric_interconnect.device
                    )
                )
                self.log.info("ucs_vars=", ucs_vars)
                template.apply("ucs-vlan-setup", ucs_vars)

                # PHASE - Update vnic-templates
                for vnic_template in fabric_interconnect.vnic_template_trunks:
                    ucs_vars.add("UCS_ORG", vnic_template.org)
                    ucs_vars.add("UCS_VNIC_TEMPLATE", vnic_template.vnic_template)
                    self.log.info(
                        "Adding VLAN {} ({}) to vnic-template {}/{} on Fabric Interconnect {}".format(
                            network.name,
                            network.vlanid,
                            vnic_template.org,
                            vnic_template.vnic_template,
                            fabric_interconnect.device,
                        )
                    )
                    self.log.info("ucs_vars=", ucs_vars)
                    template.apply("ucs-vnic-template-vlan-setup", ucs_vars)

            # PHASE - VMwar Distributed Virtual Switch
            for vswitch in vswitches:
                self.log.info(
                    "Configuring Network {} on DVS: {}/{}/{}".format(
                        network.name, vswitch.vcenter, vswitch.datacenter, vswitch.dvs
                    )
                )
                dvs_vars = ncs.template.Variables()
                dvs_vars.add("DEVICE_NAME", vswitch.vcenter)
                dvs_vars.add("VLAN_NAME", network.name)
                dvs_vars.add("VLAN_ID", network.vlanid)
                dvs_vars.add("VMWARE_DATACENTER", vswitch.datacenter)
                dvs_vars.add("VMWARE_DVS", vswitch.dvs)
                self.log.info("dvs_vars=", dvs_vars)
                template.apply("vmware-dvs-portprofile-setup", dvs_vars)

    # The pre_modification() and post_modification() callbacks are optional,
    # and are invoked outside FASTMAP. pre_modification() is invoked before
    # create, update, or delete of the service, as indicated by the enum
    # ncs_service_operation op parameter. Conversely
    # post_modification() is invoked after create, update, or delete
    # of the service. These functions can be useful e.g. for
    # allocations that should be stored and existing also when the
    # service instance is removed.

    # @Service.pre_lock_create
    # def cb_pre_lock_create(self, tctx, root, service, proplist):
    #     self.log.info('Service plcreate(service=', service._path, ')')

    # @Service.pre_modification
    # def cb_pre_modification(self, tctx, op, kp, root, proplist):
    #     self.log.info('Service premod(service=', kp, ')')

    # @Service.post_modification
    # def cb_post_modification(self, tctx, op, kp, root, proplist):
    #     self.log.info('Service premod(service=', kp, ')')
