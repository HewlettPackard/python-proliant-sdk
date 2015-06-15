
 # Copyright 2014 Hewlett-Packard Development Company, L.P.
 #
 # Licensed under the Apache License, Version 2.0 (the "License"); you may
 # not use this file except in compliance with the License. You may obtain
 # a copy of the License at
 #
 #      http://www.apache.org/licenses/LICENSE-2.0
 #
 # Unless required by applicable law or agreed to in writing, software
 # distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
 # WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
 # License for the specific language governing permissions and limitations
 # under the License.


"""

Provides functions for using the Redfish RESTful API.

"""

import collections
import json
import sys
from redfish import connection

class RedfishOperation(connection.RedfishConnection):

    def reset_server(self):
        (status, headers, system) = self.rest_get('/redfish/v1/Systems', None)

        memberuri = system['links']['Member'][0]['href']
        # verify expected type
        # hint:  don't limit to version 0 here as we will rev to 1.0 at some point hopefully with minimal changes
#        assert(connection.get_type(system) == 'ComputerSystem.0' or connection.get_type(system) == 'ComputerSystem.1')

        # verify it supports POST
#        assert(connection.operation_allowed(headers, 'POST'))

        action = dict()
        action['Action'] = 'Reset'
        action['ResetType'] = 'ForceRestart'

        # perform the POST action
        print('POST ' + json.dumps(action) + ' to ' + memberuri)
        (status, headers, response) = self.rest_post(memberuri, None, action)
        print('POST response = ' + str(status))
        connection.print_extended_error(response)
