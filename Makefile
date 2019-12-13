clean: nso-clean netsim-clean

dev: netsim nso netsim-load-base 

nso: nso-setup nso-sync-from

netsim: netsim-create netsim-start

dev-fabric: dev-vlan-fabric dev-vlan-tenant 

dev-full: dev dev-fabric

nso-setup:
	-@echo "Setting up local NSO instance..."
	-@ncs-setup \
	  --package cisco-nx-cli-5.10 \
	  --package cisco-ios-cli-6.33 \
	  --package cisco-asa-cli-6.7 \
	  --package cisco-ucs-cli-3.3 \
	  --package vmware-vsphere-gen-3.2 \
	  --package resource-manager \
	  --package ./vlan-fabric \
	  --dest .
	-@ncs

nso-sync-to:
	-@echo "Performing devices sync-to..."
	-@curl -X POST -u admin:admin http://localhost:8080/api/running/devices/_operations/sync-to

nso-sync-from:
	-@echo "Syncing From Devices to NSO..."
	-@echo "Performing devices sync-from..."
	-@curl -X POST -u admin:admin http://localhost:8080/api/running/devices/_operations/sync-from

nso-clean:
	-@echo "Stopping NSO..."
	-@ncs --stop
	-@rm -Rf README.ncs agentStore state.yml logs/ ncs-cdb/ ncs-java-vm.log ncs-python-vm.log ncs.conf state/ storedstate target/ packages/ scripts/

netsim-create:
	-@echo "Setting Up Netsim Instances..."
	-@ncs-netsim create-device cisco-asa-cli-6.7 admin-fw1
	-@ncs-netsim add-device cisco-ios-cli-6.33 admin-vsw
	-@ncs-netsim add-device cisco-asa-cli-6.7 dmz-fw01-1
	-@ncs-netsim add-device cisco-ios-cli-6.33 dmz-rtr02-1
	-@ncs-netsim add-device cisco-ios-cli-6.33 dmz-rtr02-2
	-@ncs-netsim add-device cisco-nx-cli-5.10 dmz-sw01-1
	-@ncs-netsim add-device cisco-nx-cli-5.10 dmz-sw01-2
	-@ncs-netsim add-device cisco-nx-cli-5.10 dmz-sw02-1
	-@ncs-netsim add-device cisco-nx-cli-5.10 dmz-sw02-2
	-@ncs-netsim add-device cisco-nx-cli-5.10 leaf01-1
	-@ncs-netsim add-device cisco-nx-cli-5.10 leaf01-2
	-@ncs-netsim add-device cisco-nx-cli-5.10 leaf02-1
	-@ncs-netsim add-device cisco-nx-cli-5.10 leaf02-2
	-@ncs-netsim add-device cisco-ios-cli-6.33 nfv-sw01
	-@ncs-netsim add-device cisco-ios-cli-6.33 nfv-sw02
	-@ncs-netsim add-device cisco-asa-cli-6.7 pod1-fw
	-@ncs-netsim add-device cisco-ios-cli-6.33 pod1-vsw
	-@ncs-netsim add-device cisco-asa-cli-6.7 pod2-fw
	-@ncs-netsim add-device cisco-asa-cli-6.7 pod3-fw
	-@ncs-netsim add-device cisco-nx-cli-5.10 spine01-1
	-@ncs-netsim add-device cisco-nx-cli-5.10 spine01-2
	# -@ncs-netsim add-device cisco-ucs-cli-3.3 fi01
	# -@ncs-netsim add-device cisco-ucs-cli-3.3 fi02

netsim-start:
	-@echo "Starting All Netsim Instances..."
	-@ncs-netsim start

netsim-load-base:
	-@echo "Loading base netsim configurations through NSO..."
	-@ncs_load -lmn nso-configurations/netsim-device-base-configs.xml
	-@curl -X POST -u admin:admin http://localhost:8080/api/running/devices/_operations/sync-to

netsim-clean:
	-@echo "Stopping All Netsim Instances..."
	-@killall confd
	-@rm -Rf netsim/
	-@rm README.netsim

dev-vlan-fabric:
	-@echo "Loading sample vlan-fabric configuration..."
	-@ncs_load -lmn nso-configurations/sample-vlan-fabrics.xml
	-@curl -X POST -u admin:admin http://localhost:8080/api/running/vlan-fabric/internal/_operations/re-deploy
	-@curl -X POST -u admin:admin http://localhost:8080/api/running/vlan-fabric/dmz01/_operations/re-deploy
	-@curl -X POST -u admin:admin http://localhost:8080/api/running/vlan-fabric/dmz02/_operations/re-deploy

dev-vlan-tenant:
	-@echo "Loading sample vlan-tenant configuration..."
	-@ncs_load -lmn nso-configurations/sample-vlan-tenants.xml
	-@curl -X POST -u admin:admin http://localhost:8080/api/running/devices/_operations/sync-to
