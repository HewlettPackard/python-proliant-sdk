#!/usr/bin/env python

#import logging
import sys
from oslo_config import cfg
from oslo_log import log as logging

import redfish

# Sets up basic logging for this module
#log_root = logging.getLogger('redfish')
#log_root.addHandler(logging.StreamHandler(sys.stdout))
#log_root.setLevel(logging.DEBUG)

CONF = cfg.CONF
logging.set_defaults(['redfish=DEBUG'])
logging.register_options(CONF)
#logging.setup(CONF, "redfish")

# Connect to a redfish API endpoint
host = 'http://localhost'
user_name = ''
password = ''

# This returns a RedfishConnection object, which implements
# the low-level HTTP methods like GET, PUT, etc
connection = redfish.server.connect(host, user_name, password)

# From this connection, we can get the Root resource.
# Note that the root resource is somewhat special - you create it from
# the connection, but you create other resources from the root resource.
# (You don't strictly have to do this, but it's simpler.)
root = connection.get_root()

print("\n")
print("ROOT CONTROLLER")
print("===============")
print(root)


# The Root class has well-defined top-level resources, such as
# chassis, systems, managers, sessions, etc...
chassis = root.get_chassis()

print("\n")
print("CHASSIS DATA")
print("============")
print(chassis)
print("\n")
print("WALKING CHASSIS")
print("\n")
print("CHASSIS contains %d items" % len(chassis))
print("\n")
for item in chassis:
    print("SYSTEM")
    print("======")
    print(item)
    print("\n")
