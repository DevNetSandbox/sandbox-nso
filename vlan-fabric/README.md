# vlan-fabric 
A "vlan-fabric" is a collection of L2 network devices that will share common VLAN configurations.  The `vlan-fabric` service for Sandbox describes the devices that make up the fabric, and how they are connected together.  Then NSO will ensure that the devices are configured as required.  Here is an example of a fabric configuration. 

```
vlan-fabric dmz02
 switch-pair dmz-sw02
  layer3 true
  primary   dmz-sw02-1
  secondary dmz-sw02-2
  !
  vpc-peerlink id 1
  vpc-peerlink interface 1/1
  vpc-peerlink interface 1/2
  !
  fabric-trunk 2
   interface 1/11
 !
 switch nfv-sw01
  fabric-trunk 2
   interface 0/1
```

In a fabric a `switch-pair` represents a pair of Cisco NX-OS devices that will be configured in a VPC relationship.  You simply need to specify which device is primary and secondary, and the ports that make up the peerlink.  

A `switch-pair` can be configured with `layer3 true` (the default is `layer3 false`).  This indicates that within this fabric, this pair of devices would be configured with SVIs for networks, including HSRP and OSPF for routing.  

A `switch` would be an independent switch, or either IOS or NX-OS model.  

For both `switch-pairs` and `switches`, the `fabric-trunks` identify interswitch links that connect to other devices in the fabric.  The service will setup LACP port-channels made up of the identified interfaces, and configure them to be dot1q trunks.  

A `vlan-fabric` can also include Cisco UCS and VMware networks.  You'd add them to a fabric like this. 

```
vlan-fabric dmz02 
 fabric-interconnect ucsfi01
  vnic-template-trunks org sandbox vnic-template esxi-vnic

 vmware-dvs vcenter myvcenter datacenter sandbox dvs mydvs
```

In this case, the service will configure VLANs within UCS and then add them to the specified `vnic-templates`.  It will also create new VMware port-groups on the `dvs` specified.  

For a more complete example of `vlan-fabric` configurations, you can look at [sample-vlan-fabrics.cfg](samples/sample-vlan-fabrics.cfg) or [sample-vlan-fabrics.xml](samples/sample-vlan-fabrics.xml)

# vlan-tenant 
A `vlan-fabric` is simply a defintion of the network devices that make up a part of the network, but to create vlans and networks on the fabric a `vlan-tenant` is used.  

The `vlan-tenant` describes a set of `networks` (or VLANs) that make up a single layer-3 environment.  Here is an exmaple of a `vlan-tenant` configuration.  

```
vlan-tenant admin
 fabric internal
 static-routes 0.0.0.0/0
  gateway 10.255.250.4
 !
 network admin-main
  vlanid  11
  network 10.255.2.0/23
  connections switch admin-vsw
   interface 0/3
    mode access
 !
 network admin-small
  vlanid  12
  network 10.255.1.0/24
```

Notice how the `vlan-tenant` exists on a `fabric` - this is the linkage that determines which switches and other devices these networks will be created on.  

A VRF will be configured for the  `vlan-tenant` (if at least one network is configured for `layer3-on-fabric true`).  You can add static routes to the VRF as part of the tenant configuration.  

You can add as many `network` objects to the tenant as you desire.  Each `network` will need a `vlanid` and `network` (or prefix) specified.  The service will then create this VLAN on all devices in the fabric.  

If there are any physical network connections into a network needed, you can specify them with `connections`.  

For a more complete example of `vlan-tenant` configurations, you can look at [sample-vlan-tenants.cfg](samples/sample-vlan-tenants.cfg) or [sample-vlan-tenants.xml](samples/sample-vlan-tenants.xml)
