# -*- mode: python; python-indent: 4 -*-
import ncs
from ncs.application import Service

from . import fabric
from . import tenant

# ---------------------------------------------
# COMPONENT THREAD THAT WILL BE STARTED BY NCS.
# ---------------------------------------------
class Main(ncs.application.Application):
    def setup(self):
        self.log.info('Main RUNNING')

        # Service callbacks require a registration for a 'service point',
        # as specified in the corresponding data model.
        #
        self.register_service('vlan-fabric-servicepoint', fabric.ServiceCallbacks)
        self.register_service('vlan-tenant', tenant.ServiceCallbacks)


    def teardown(self):
        self.log.info('Main FINISHED')
