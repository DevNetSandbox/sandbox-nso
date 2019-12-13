# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.application import Service
import resource_manager.id_allocator as id_allocator
import ipaddress


# ------------------------
# SERVICE CALLBACK EXAMPLE
# ------------------------
class ServiceCallbacks(Service):

    # The create() callback is invoked inside NCS FASTMAP and
    # must always exist.
    @Service.create
    def cb_create(self, tctx, root, service, proplist):
        self.log.info('Service create(service=', service._path, ')')

        vars = ncs.template.Variables()
        template = ncs.template.Template(service)

        # Setup VPC Domain Id Pool 
        template.apply("vpc-domain-id-pool", vars)

        # PHASE - Configure Switch Pairs
        for pair in service.switch_pair: 
            self.log.info("Processing Switch Pair {}".format(pair.name))

            # Allocate VPC Domain Ids for Switch Pairs
            self.log.info("Allocating VPC Domain Id for Switch Pair {}".format(pair.name))
            pool_name = "VPC-DOMAIN-ID-POOL-{}".format(service.name)
            alloc_name = "SWITCH-PAIR-{}".format(pair.name)
            id_allocator.id_request(
                service, 
                "/vlan-fabric[name='%s']" % (service.name),
                tctx.username,
                pool_name,
                alloc_name,
                False)
            vpc_domain_id = id_allocator.id_read(
                tctx.username,
                root,
                pool_name,
                alloc_name,
            )
            self.log.info("vpc_domain_id = {}".format(vpc_domain_id))
            
            
            # Test if Allocations are ready 
            if not vpc_domain_id: 
                self.log.info("VPC Domain ID Allocation not ready - {}".format(pair.name))
            else: 
                # PHASE - VPC Domain Setup
                primary_ip_address = root.devices.device[pair.primary].config.interface.mgmt["0"].ip.address.ipaddr

                vpc_vars = ncs.template.Variables()
                disable_trunk_negotiation = False
                vpc_vars.add("DISABLE_TRUNK_NEGOTIATION", disable_trunk_negotiation)

                # Support pairs that lack a secondary - ie for PreProd
                if pair.secondary: 
                    secondary_ip_address = root.devices.device[pair.secondary].config.interface.mgmt["0"].ip.address.ipaddr
                    vpc_vars.add("VPC_ENABLED", True)
                else: 
                    secondary_ip_address = ""
                    vpc_vars.add("VPC_ENABLED", "")

                self.log.info("Primary IP Address: {}".format(primary_ip_address))
                self.log.info("Secondary IP Address: {}".format(secondary_ip_address))

                vpc_vars.add("VPC_DOMAIN_ID", vpc_domain_id)
                vpc_vars.add("VPC_PEERLINK_ID", pair.vpc_peerlink.id)
                vpc_vars.add("LAYER3", pair.layer3)
                vpc_vars.add("MTU_SIZE", "1500")

                self.log.info("Setting up VPC Domain on pair {} primary device {}".format(pair.name, pair.primary))
                vpc_vars.add("DEVICE_NAME", pair.primary)
                vpc_vars.add("VPC_PEER_KEEPALIVE_SOURCE", primary_ip_address.split("/")[0])
                vpc_vars.add("VPC_PEER_KEEPALIVE_DESTINATION", secondary_ip_address.split("/")[0])
                # vpc_vars.add("", )
                self.log.info("vpc_vars=", vpc_vars)
                template.apply("vpc-domain-base", vpc_vars)

                if pair.secondary: 
                    self.log.info("Setting up VPC Domain on pair {} secondary device {}".format(pair.name, pair.secondary))
                    vpc_vars.add("DEVICE_NAME", pair.secondary)
                    vpc_vars.add("VPC_PEER_KEEPALIVE_SOURCE", secondary_ip_address.split("/")[0])
                    vpc_vars.add("VPC_PEER_KEEPALIVE_DESTINATION", primary_ip_address.split("/")[0])
                    # self.log.info("vpc_secondary_vars=", vpc_vars)
                    # vpc_vars.add("", )
                    template.apply("vpc-domain-base", vpc_vars)

                    # PHASE - VPC Peerlink Setup 
                    for interface in pair.vpc_peerlink.interface: 
                        vpc_pl_vars = ncs.template.Variables()
                        vpc_pl_vars.add("DISABLE_TRUNK_NEGOTIATION", disable_trunk_negotiation)
                        vpc_pl_vars.add("INTERFACE_ID", interface.interface)
                        vpc_pl_vars.add("PORTCHANNEL_ID", pair.vpc_peerlink.id)
                        vpc_pl_vars.add("DESCRIPTION", "VPC Peer Link")
                        vpc_pl_vars.add("MODE", "trunk")
                        vpc_pl_vars.add("VLAN_ID", "all")
                        vpc_pl_vars.add("MTU_SIZE", "1500")
                        # vpc_pl_vars.add("OLD_SWITCH", "false")


                        self.log.info("Setting up VPC Peerlink Interfaces on pair {} primary device {}".format(pair.name, pair.primary))
                        vpc_pl_vars.add("DEVICE_NAME", pair.primary)
                        self.log.info("vpc_pl_vars=", vpc_pl_vars)
                        template.apply("portchannel-member-interface", vpc_pl_vars)

                        if pair.secondary: 
                            self.log.info("Setting up VPC Peerlink Interfaces on pair {} secondary device {}".format(pair.name, pair.secondary))
                            vpc_pl_vars.add("DEVICE_NAME", pair.secondary)
                            self.log.info("vpc_pl_vars=", vpc_pl_vars)
                            template.apply("portchannel-member-interface", vpc_pl_vars)

                # PHASE - Enable Jumbo Frames 
                mtu_vars = ncs.template.Variables()
                mtu_vars.add("FRAME_SIZE", "9216")

                # Primary
                mtu_vars.add("DEVICE_NAME", pair.primary)
                self.log.info("Setting up Jumbo System MTU on pair {} primary device {}".format(pair.name, pair.primary))
                self.log.info("mtu_vars=", mtu_vars)
                template.apply("system-jumbo-frames", mtu_vars)

                # Secondary 
                if pair.secondary:
                    mtu_vars.add("DEVICE_NAME", pair.primary)
                    self.log.info("Setting up Jumbo System MTU on pair {} secondary device {}".format(pair.name, pair.secondary))
                    self.log.info("mtu_vars=", mtu_vars)
                    template.apply("system-jumbo-frames", mtu_vars)


                # PHASE - Interswitch Trunk Setup 
                for trunk in pair.fabric_trunk: 
                    trunk_vars = ncs.template.Variables()
                    trunk_vars.add("DISABLE_TRUNK_NEGOTIATION", disable_trunk_negotiation)
                    trunk_vars.add("INTERFACE_ID", trunk.interface)
                    trunk_vars.add("PORTCHANNEL_ID", trunk.portchannel_id)
                    trunk_description = "Interswitch Fabric Link"
                    trunk_vars.add("DESCRIPTION", trunk_description)
                    trunk_vars.add("MTU_SIZE", "9216")
                    
                    if pair.secondary: 
                        trunk_vars.add("VPC", True)
                    else: 
                        trunk_vars.add("VPC", "")
                    trunk_vars.add("MODE", "trunk")
                    trunk_vars.add("VLAN_ID", "all")
                    # trunk_vars.add("OLD_SWITCH", "false")


                    self.log.info("Setting up Trunk {} on pair {} primary device {}".format(trunk.portchannel_id, pair.name, pair.primary))
                    trunk_vars.add("DEVICE_NAME", pair.primary)
                    self.log.info("trunk_vars=", trunk_vars)
                    template.apply("portchannel-interface", trunk_vars)

                    if pair.secondary: 
                        self.log.info("Setting up Trunk {} on pair {} secondary device {}".format(trunk.portchannel_id, pair.name, pair.secondary))
                        trunk_vars.add("DEVICE_NAME", pair.secondary)
                        self.log.info("trunk_vars=", trunk_vars)
                        template.apply("portchannel-interface", trunk_vars)
                    
                    # PHASE - Configure Trunk Member Interfaces
                    for interface in trunk.interface: 
                        trunk_vars.add("INTERFACE_ID", interface.interface)

                        self.log.info("Setting up Trunk {} Member Interface {} on pair {} primary device {}".format(trunk.portchannel_id, interface.interface, pair.name, pair.primary))
                        trunk_vars.add("DEVICE_NAME", pair.primary)
                        self.log.info("trunk_vars=", trunk_vars)
                        template.apply("portchannel-member-interface", trunk_vars)

                        if pair.secondary: 
                            self.log.info("Setting up Trunk {} Member Interface {} on pair {} secondary device {}".format(trunk.portchannel_id, interface.interface, pair.name, pair.secondary))
                            trunk_vars.add("DEVICE_NAME", pair.secondary)
                            self.log.info("trunk_vars=", trunk_vars)
                            template.apply("portchannel-member-interface", trunk_vars)

        # PHASE - Configure individual switches 
        for switch in service.switch: 
            self.log.info("Processing Individual Switch {}".format(switch.device))
            switch_platform = {}
            switch_platform["name"] = root.devices.device[switch.device].platform.name
            switch_platform["version"] = root.devices.device[switch.device].platform.version
            switch_platform["model"] = root.devices.device[switch.device].platform.model
            self.log.info("Switch Platform Info: {}".format(switch_platform))

            if switch_platform["model"] != "NETSIM" and switch_platform["name"] == "ios" and int(switch_platform["version"][0:2]) < 16: 
                disable_trunk_negotiation = True 
            else: 
                disable_trunk_negotiation = False


            # PHASE - Enable Jumbo Frames 
            # Limit to 3850 and 9300 Switcehs 
            if "3850" in switch_platform["model"] or "9300" in switch_platform["model"]: 
                mtu_vars = ncs.template.Variables()
                mtu_vars.add("FRAME_SIZE", "9198")
                mtu_vars.add("DEVICE_NAME", switch.device)
                self.log.info("Setting up Jumbo System MTU on switch {}".format(switch.device))
                self.log.info("mtu_vars=", mtu_vars)
                template.apply("system-jumbo-frames", mtu_vars)


            # PHASE - Interswitch Trunk Setup 
            for trunk in switch.fabric_trunk: 
                trunk_vars = ncs.template.Variables()
                # if switch.oldswitch_fix: 
                #     trunk_vars.add("OLD_SWITCH", "true")    
                # else: 
                #     trunk_vars.add("OLD_SWITCH", "false")
                trunk_vars.add("DEVICE_NAME", switch.device)
                trunk_vars.add("PORTCHANNEL_ID", trunk.portchannel_id)
                trunk_description = "Interswitch Fabric Link"
                trunk_vars.add("DESCRIPTION", trunk_description)
                trunk_vars.add("VPC", "")
                trunk_vars.add("MODE", "trunk")
                trunk_vars.add("VLAN_ID", "all")
                trunk_vars.add("DISABLE_TRUNK_NEGOTIATION", disable_trunk_negotiation)
                trunk_vars.add("MTU_SIZE", "9216")

                self.log.info("Setting up Trunk {} on switch {}".format(trunk.portchannel_id, switch.device))
                self.log.info("trunk_vars=", trunk_vars)
                template.apply("portchannel-interface", trunk_vars)
                
                # PHASE - Configure Trunk Member Interfaces
                for interface in trunk.interface: 
                    trunk_vars.add("INTERFACE_ID", interface.interface)
                    self.log.info("Setting up Trunk {} Member Interface {} on switch {}".format(trunk.portchannel_id, interface.interface, switch.device))
                    self.log.info("trunk_vars=", trunk_vars)
                    template.apply("portchannel-member-interface", trunk_vars)

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

