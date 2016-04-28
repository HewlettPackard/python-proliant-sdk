# Copyright 2016 Hewlett Packard Enterprise Development, LP.
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
Provides examples of using the HP RESTful API on iLO for common use cases.  This is for tutorial/example purposes only.
---------------------------------------------------------------------------------------------------------------------
IMPORTANT!!!
---------------------------------------------------------------------------------------------------------------------
When developing a client for the HP RESTful API, be sure to not code based upon assumptions that are not guaranteed.
Search for, and note any 'NOTE' comments in this code to read about ways to avoid incorrect assumptions.
The reason avoiding these assumptions is so important is that implementations may vary across systems and firmware
versions, and we want your code to work consistently.
---------------------------------------------------------------------------------------------------------------------
STARTING ASSUMPTIONS
---------------------------------------------------------------------------------------------------------------------
On URIs:
The HP RESTful API is a "hypermedia API" by design.  This is to avoid building in restrictive assumptions to the
data model that will make it difficult to adapt to future hardware implementations.  A hypermedia API avoids these
assumptions by making the data model discoverable via links between resources.
A URI should be treated by the client as opaque, and thus should not be attempted to be understood or deconstructed
by the client.  Only specific top level URIs (any URI in this sample code) may be assumed, and even these may be
absent based upon the implementation (e.g. there might be no /rest/v1/Systems collection on something that doesn't
have compute nodes.)
The other URIs must be discovered dynamically by following href links.  This is because the API will eventually be
implemented on a system that breaks any existing data model "shape" assumptions we may make now.  In particular,
clients should not make assumptions about the URIs for the resource members of a collection.  For instance, the URI of
a collection member will NOT always be /rest/v1/.../collection/1, or 2.  On Moonshot a System collection member might be
/rest/v1/Systems/C1N1.
This sounds very complicated, but in reality (as these examples demonstrate), if you are looking for specific items,
the traversal logic isn't too complicated.
On Resource Model Traversal:
Although the resources in the data model are linked together, because of cross link references between resources,
a client may not assume the resource model is a tree.  It is a graph instead, so any crawl of the data model should
keep track of visited resources to avoid an infinite traversal loop.
A reference to another resource is any property called "href" no matter where it occurs in a resource.
An external reference to a resource outside the data model is referred to by a property called "extref".  Any
resource referred to by extref should not be assumed to follow the conventions of the API.
On Resource Versions:
Each resource has a "Type" property with a value of the format Tyepname.x.y.z where
* x = major version - incrementing this is a breaking change to the schema
* y = minor version - incrementing this is a non-breaking additive change to the schema
* z = errata - non-breaking change
Because all resources are versioned and schema also have a version, it is possible to design rules for "nearest"
match (e.g. if you are interacting with multiple services using a common batch of schema files).  The mechanism
is not prescribed, but a client should be prepared to encounter both older and newer versions of resource types.
On HTTP POST to create:
WHen POSTing to create a resource (e.g. create an account or session) the guarantee is that a successful response
includes a "Location" HTTP header indicating the resource URI of the newly created resource.  The POST may also
include a representation of the newly created object in a JSON response body but may not.  Do not assume the response
body, but test it.  It may also be an ExtendedError object.
HTTP REDIRECT:
All clients must correctly handle HTTP redirect.  We (or Redfish) may eventually need to use redirection as a way
to alias portions of the data model.
FUTURE:  Asynchronous tasks
In the future some operations may start asynchonous tasks.  In this case, the client should recognized and handle
HTTP 202 if needed and the 'Location' header will point to a resource with task information and status.
JSON-SCHEMA:
The json-schema available at /rest/v1/Schemas governs the content of the resources, but keep in mind:
* not every property in the schema is implemented in every implementation.
* some properties are schemed to allow both null and anotehr type like string or integer.
Robust client code should check both the existence and type of interesting properties and fail gracefully if
expectations are not met.
GENERAL ADVICE:
Clients should always be prepared for:
* unimplemented properties (e.g. a property doesn't apply in a particular case)
* null values in some cases if the value of a property is not currently known due to system conditions
* HTTP status codes other than 200 OK.  Can your code handle an HTTP 500 Internal Server Error with no other info?
* URIs are case insensitive
* HTTP header names are case insensitive
* JSON Properties and Enum values are case sensitive
* A client should be tolerant of any set of HTTP headers the service returns
"""

import sys
import json
import logging
import urlparse
import jsonpatch

from ilorest import AuthMethod, ilorest_logger, rest_client


#Config logger used by HPE Restful library
LOGGERFILE = "RestfulApiExamples.log"
LOGGERFORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOGGER = ilorest_logger(LOGGERFILE, LOGGERFORMAT, logging.INFO)
LOGGER.info("HPE Restful API examples")

def ex1_get_resource_directory(restobj):
    sys.stdout.write("\nEXAMPLE 1: Find and store the resource directory " + "\n")
    response = restobj.rest_get("/rest/v1/resourcedirectory")
    resources = {}

    if response.status == 200:
        sys.stdout.write("\tFound resource directory at /rest/v1/resource" \
                                                            "directory" + "\n")
        resources["resources"] = response.dict["Instances"]
        return resources
    else:
        sys.stderr.write("\tResource directory missing at /rest/v1/resource" \
                                                            "directory" + "\n")

def ex2_get_base_registry(restobj):
    sys.stdout.write("\nEXAMPLE 2: Find and return registry " + "\n")
    response = restobj.rest_get("/rest/v1/Registries")
    messages = {}
    
    identifier = None
    
    for entry in response.dict["Items"]:
        if "Id" in entry:
            identifier = entry["Id"]
        else:
            identifier = entry["Schema"].split(".")[0]

        if identifier not in ["Base", "iLO"]:
            continue

        for location in entry["Location"]:  
            reg_resp = restobj.rest_get(location["Uri"]["extref"])

            if reg_resp.status == 200:
                sys.stdout.write("\tFound " + identifier + " at " + \
                                            location["Uri"]["extref"] + "\n")
                messages[identifier] = reg_resp.dict["Messages"]
            else:
                sys.stdout.write("\t" + identifier + " not found at "\
                                            + location["Uri"]["extref"] + "\n")

    return messages

def ex3_change_bios_setting(restobj, bios_property, property_value, \
                                                            bios_password=None):
    sys.stdout.write("\nEXAMPLE 3: Change a BIOS setting\n")
    instances = restobj.search_for_type("Bios.")

    for instance in instances:
        body = {bios_property: property_value}
        response = restobj.rest_patch(instance["href"], body, \
                                            optionalpassword=bios_password)
        restobj.error_handler(response)

def ex4_reset_server(restobj, bios_password=None):
    sys.stdout.write("\nEXAMPLE 4: Reset a server\n")
    instances = restobj.search_for_type("ComputerSystem.")

    for instance in instances:
        body = dict()
        body["Action"] = "Reset"
        body["ResetType"] = "ForceRestart"

        response = restobj.rest_post(instance["href"], body)
        restobj.error_handler(response)

def ex5_enable_secure_boot(restobj, secure_boot_enable, bios_password=None):
    sys.stdout.write("\nEXAMPLE 5: Enable/Disable UEFI Secure Boot\n")
    instances = restobj.search_for_type("SecureBoot.")

    for instance in instances:
        body = {"SecureBootEnable": secure_boot_enable}
        response = restobj.rest_patch(instance["href"], body, \
                                            optionalpassword=bios_password)
        restobj.error_handler(response)

def ex6_bios_revert_default(restobj):
    sys.stdout.write("\nEXAMPLE 6: Revert BIOS settings to default\n")
    instances = restobj.search_for_type("Bios.")

    for instance in instances:
        body = {"BaseConfig": "default"}
        response = restobj.rest_put(instance["href"], body)
        restobj.error_handler(response)

def ex7_change_boot_order(restobj, bios_password=None):
    sys.stdout.write("\nEXAMPLE 7: Change Boot Order (UEFI)\n")
    instances = restobj.search_for_type("ServerBootSettings.")

    for instance in instances:
        response = restobj.rest_get(instance["href"])
        bootorder = response.dict["PersistentBootConfigOrder"]
    
        #TODO: Need to change the persistent boot order here
        body = dict()
        body["PersistentBootConfigOrder"] = bootorder

        response = restobj.rest_patch(instance["href"], body, \
                                            optionalpassword=bios_password)            
        restobj.error_handler(response)

def ex8_change_temporary_boot_order(restobj, boottarget, bios_password=None):
    sys.stdout.write("\nEXAMPLE 8: Change temporary boot order (one time boot" \
                                                    " or temporary override)\n")
    instances = restobj.search_for_type("ComputerSystem.")

    for instance in instances:
        response = restobj.rest_get(instance["href"])
        bootoptions = response.dict["Boot"]
        
        if boottarget not in bootoptions["BootSourceOverrideSupported"]:
            sys.stderr.write("ERROR: %s is not a supported boot option.\n" \
                                                            % boottarget)

        body = dict()
        body["Boot"] = dict()
        body["Boot"]["BootSourceOverrideTarget"] = boottarget

        response = restobj.rest_patch(instance["href"], body, \
                                            optionalpassword=bios_password)            
        restobj.error_handler(response)

def ex9_find_ilo_mac_address(restobj):
    sys.stdout.write("\nEXAMPLE 9: Find iLO's MAC Addresses\n")
    instances = restobj.search_for_type("Manager.")

    for instance in instances:
        tmp = restobj.rest_get(instance["href"])  
        response = restobj.rest_get(tmp.dict["links"]["EthernetNICs"]["href"])

        for item in response.dict["Items"]:
            if "MacAddress" not in item:
                sys.stderr.write("\tNIC resource does not contain " \
                                                    "'MacAddress' property\n")
            else:
                sys.stdout.write("\t" + item["Name"] + " = " + \
                                             item["MacAddress"] + "\t(" + \
                                             item["Status"]["State"] + ")\n")

def ex10_add_ilo_user_account(restobj, new_ilo_loginname, new_ilo_username, \
                                 new_ilo_password, irc=None, cfg=None, \
                                 virtual_media=None, usercfg=None, vpr=None):
    sys.stdout.write("\nEXAMPLE 10: Create an iLO User Account\n")
    instances = restobj.search_for_type("AccountService.")

    for instance in instances:
        rsp = restobj.rest_get(instance["href"])

        body = {"UserName": new_ilo_loginname, "Password": \
                                                new_ilo_password, "Oem": {}}
        body["Oem"]["Hp"] = {}
        body["Oem"]["Hp"]["LoginName"] = new_ilo_username
        body["Oem"]["Hp"]["Privileges"] = {}
        body["Oem"]["Hp"]["Privileges"]["RemoteConsolePriv"] = irc
        body["Oem"]["Hp"]["Privileges"]["iLOConfigPriv"] = cfg
        body["Oem"]["Hp"]["Privileges"]["VirtualMediaPriv"] = virtual_media
        body["Oem"]["Hp"]["Privileges"]["UserConfigPriv"] = usercfg
        body["Oem"]["Hp"]["Privileges"]["VirtualPowerAndResetPriv"] = vpr

        newrsp = restobj.rest_post(rsp.dict["links"]["Accounts"]["href"], body)
        restobj.error_handler(newrsp)

def ex11_modify_ilo_user_account(restobj, ilo_login_name_to_modify, \
                new_ilo_loginname, new_ilo_username, new_ilo_password, \
                irc=None, cfg=None, virtual_media=None, usercfg=None, vpr=None):
    sys.stdout.write("\nEXAMPLE 11: Modify an iLO user account\n")
    instances = restobj.search_for_type("AccountService.")

    for instance in instances:
        response = restobj.rest_get(instance["href"])
        accounts = restobj.rest_get(response.dict["links"]["Accounts"]["href"])

        for account in accounts.dict["Items"]:
            if account["UserName"] == ilo_login_name_to_modify:
                body = {}
                body_oemhp = {}
                body_oemhp_privs = {}
    
                # if new loginname or password specified
                if new_ilo_password:
                    body["Password"] = new_ilo_password
                if new_ilo_loginname:
                    body["UserName"] = new_ilo_loginname
    
                # if different username specified
                if new_ilo_username:
                    body_oemhp["LoginName"] = new_ilo_username
    
                # if different privileges were requested (None = no change)
                if irc != None:
                    body_oemhp_privs["RemoteConsolePriv"] = irc
                if virtual_media != None:
                    body_oemhp_privs["VirtualMediaPriv"] = virtual_media
                if cfg != None:
                    body_oemhp_privs["iLOConfigPriv"] = cfg
                if usercfg != None:
                    body_oemhp_privs["UserConfigPriv"] = usercfg
                if vpr != None:
                    body_oemhp_privs["VirtualPowerAndResetPriv"] = vpr
    
                # component assembly
                if len(body_oemhp_privs):
                    body_oemhp["Privileges"] = body_oemhp_privs
                if len(body_oemhp):
                    body["Oem"] = {"Hp": body_oemhp}

                newrsp = restobj.rest_patch(account["links"]["self"]["href"], \
                                                                        body)
                restobj.error_handler(newrsp)
                return
            
    sys.stderr.write("Account not found\n")

def ex12_remove_ilo_account(restobj, ilo_loginname_to_remove):
    sys.stdout.write("\nEXAMPLE 12: Remove an iLO account\n")
    instances = restobj.search_for_type("AccountService.")

    for instance in instances:
        response = restobj.rest_get(instance["href"])
        accounts = restobj.rest_get(response.dict["links"]["Accounts"]["href"])

        for account in accounts.dict["Items"]:
            if account["UserName"] == ilo_loginname_to_remove:
                newrsp = restobj.rest_delete(account["links"]["self"]["href"])
                restobj.error_handler(newrsp)
                return
            
    sys.stderr.write("Account not found\n")

def ex13_dump_ilo_nic(restobj):
    sys.stdout.write("\nEXAMPLE 13: Get iLO NIC state\n")
    instances = restobj.search_for_type("Manager.")

    for instance in instances:
        rsp = restobj.rest_get(instance["href"])
        response = restobj.rest_get(rsp.dict["links"]["EthernetNICs"]["href"])

        for nic in response.dict["Items"]:
            if nic["Status"]["State"] == "Enabled":
                sys.stdout.write("\t" + nic["Name"] + "\n")

                if "MacAddress" not in nic:
                    sys.stderr.write("\tNo MacAddress information available (no"
                           " 'MacAddress' property in NIC resource)\n")
                else:
                    sys.stdout.write("\tMAC: " + str(nic["MacAddress"]) + "\n")

                sys.stdout.write("\tSpeed: " + str(nic["SpeedMbps"]) + "\n")
                sys.stdout.write("\tAutosense:  " + \
                                                str(nic["Autosense"]) + "\n")
                sys.stdout.write("\tFull Duplex:  " + str(nic["FullDuplex"]) \
                                                                        + "\n")
                if "FQDN" not in nic:
                    sys.stderr.write("\tNo FQDN information available\n")
                else:
                    sys.stdout.write("\tFQDN:  " + str(nic["FQDN"]) + "\n")
                for addr in nic["IPv4Addresses"]:
                    sys.stdout.write("\tIPv4 Address:  " + addr["Address"] 
                           + " from " + addr["AddressOrigin"] + "\n")
                if "IPv6Addresses" not in nic:
                    sys.stderr.write("\tIPv6Addresses information not "\
                                                                "available\n")
                else:
                    for addr in nic["IPv6Addresses"]:
                        sys.stdout.write("\tIPv6 Address:  " + addr["Address"] 
                               + " from " + addr["AddressOrigin"] + "\n")

def ex14_sessions(restobj, login_account, login_password):
    sys.stdout.write("\nEXAMPLE 14: Create/Use/Delete a user session\n")
    new_session = {"UserName": login_account, "Password": login_password}
    response = restobj.rest_post("/rest/v1/Sessions", new_session)
    restobj.error_handler(response)
    
    if response.status == 201:
        session_uri = response.getheader("location")
        session_uri = urlparse.urlparse(session_uri)
        sys.stdout.write("\tSession " + session_uri.path + " created\n")

        x_auth_token = response.getheader("x-auth-token")
        sys.stdout.write("\tSession key " + x_auth_token + " created\n")

        # Delete the created session
        sessresp = restobj.rest_delete(session_uri.path)
        restobj.error_handler(sessresp)
    else:
        sys.stderr.write("ERROR: failed to create a session.\n")

def ex15_set_uid_light(restobj, uid):
    sys.stdout.write("\nEXAMPLE 15: Set UID Light on or off\n")
    instances = restobj.search_for_type("ComputerSystem.")

    for instance in instances:
        body = dict()
        if uid:
            body["IndicatorLED"] = "Lit"
        else:
            body["IndicatorLED"] = "Off"

        response = restobj.rest_patch(instance["href"], body)
        restobj.error_handler(response)

def ex16_computer_details(restobj):
    sys.stdout.write("\nEXAMPLE 16: Dump host computer details\n")
    instances = restobj.search_for_type("ComputerSystem.")

    for instance in instances:
        response = restobj.rest_get(instance["href"])

        sys.stdout.write("\tManufacturer:  " + \
                                str(response.dict["Manufacturer"]) + "\n")
        sys.stdout.write("\tModel:  " + str(response.dict["Model"]) + "\n")
        sys.stdout.write("\tSerial Number:  " + \
                                str(response.dict["SerialNumber"]) + "\n")
        if "VirtualSerialNumber" in response.dict:
            sys.stdout.write("\tVirtual Serial Number:  " +
                   str(response.dict["VirtualSerialNumber"]) + "\n")
        else:
            sys.stderr.write("\tVirtual Serial Number information not " \
                                        "available on system resource\n")
        sys.stdout.write("\tUUID:  " + str(response.dict["UUID"]) + "\n")

        if "VirtualUUID" in response.dict["Oem"]["Hp"]:
            sys.stdout.write("\tVirtualUUID:  " + \
                     str(response.dict["Oem"]["Hp"]["VirtualUUID"]) + "\n")
        else:
            sys.stderr.write("\tVirtualUUID not available system " \
                                                            "resource\n")
        if "AssetTag" in response.dict:
            sys.stdout.write("\tAsset Tag:  " + response.dict["AssetTag"] \
                                                                    + "\n")
        else:
            sys.stderr.write("\tNo Asset Tag information on system " \
                                                            "resource\n")
        sys.stdout.write("\tBIOS Version: " + \
                 response.dict["Bios"]["Current"]["VersionString"] + "\n")

        sys.stdout.write("\tMemory:  " + 
               str(response.dict["Memory"]["TotalSystemMemoryGB"]) +" GB\n")

        sys.stdout.write("\tProcessors:  " + \
                 str(response.dict["Processors"]["Count"]) + " x " + \
                 str(response.dict["Processors"]["ProcessorFamily"])+ "\n")

        if "Status" not in response.dict or "Health" not in \
                                                    response.dict["Status"]:
            sys.stdout.write("\tStatus/Health information not available in "
                                                        "system resource\n")
        else:
            sys.stdout.write("\tHealth:  " + \
                             str(response.dict["Status"]["Health"]) + "\n")

        if "HostCorrelation" in response.dict:
            if "HostFQDN" in response.dict["HostCorrelation"]:
                sys.stdout.write("\tHost FQDN:  " + \
                     response.dict["HostCorrelation"]["HostFQDN"] + "\n")
                
            if "HostMACAddress" in response.dict["HostCorrelation"]:
                for mac in response.dict["HostCorrelation"]["HostMACAddress"]:
                    sys.stdout.write("\tHost MAC Address:  " + str(mac) + "\n")

            if "HostName" in response.dict["HostCorrelation"]:
                sys.stdout.write("\tHost Name:  " + \
                     response.dict["HostCorrelation"]["HostName"] + "\n")

            if "IPAddress" in response.dict["HostCorrelation"]:
                for ip_address in response.dict["HostCorrelation"]\
                                                            ["IPAddress"]:
                    if ip_address:
                        sys.stdout.write("\tHost IP Address:  " + \
                                                    str(ip_address) + "\n")

def ex17_mount_virtual_media_iso(restobj, iso_url, boot_on_next_server_reset):
    sys.stdout.write("\nEXAMPLE 17: Mount iLO Virtual Media DVD ISO from URL\n")
    instances = restobj.search_for_type("Manager.")

    for instance in instances:
        rsp = restobj.rest_get(instance["href"])
        rsp = restobj.rest_get(rsp.dict["links"]["VirtualMedia"]["href"])

        for vmlink in rsp.dict["links"]["Member"]:
            response = restobj.rest_get(vmlink["href"])

            if response.status == 200 and "DVD" in response.dict["MediaTypes"]:
                body = {"Image": iso_url}
                
                if (iso_url is not None and \
                                        boot_on_next_server_reset is not None):
                    body["Oem"] = {"Hp": {"BootOnNextServerReset": \
                                                    boot_on_next_server_reset}}
    
                    response = restobj.rest_patch(vmlink["href"], body)
                    restobj.error_handler(response)
            elif response.status != 200:
                restobj.error_handler(response)

def ex18_set_server_asset_tag(restobj, asset_tag):
    sys.stdout.write("\nEXAMPLE 18: Set Computer Asset Tag\n")
    instances = restobj.search_for_type("ComputerSystem.")

    for instance in instances:
        body = {"AssetTag": asset_tag}
        response = restobj.rest_patch(instance["href"], body)
        restobj.error_handler(response)

def ex19_reset_ilo(restobj):
    sys.stdout.write("\nEXAMPLE 19: Reset iLO\n")
    instances = restobj.search_for_type("Manager.")

    for instance in instances:
        body = {"Action": "Reset"}
        response = restobj.rest_post(instance["href"], body)
        restobj.error_handler(response)

def ex20_get_ilo_nic(restobj, get_active):
    sys.stdout.write("\nEXAMPLE 20: Get iLO's NIC configuration\n")
    instances = restobj.search_for_type("Manager.")

    for instance in instances:
        tmp = restobj.rest_get(instance["href"])  
        response = restobj.rest_get(tmp.dict["links"]["EthernetNICs"]["href"])

        for nic in response.dict["Items"]:
            if get_active and nic["Status"]["State"] == "Enabled":
                sys.stdout.write("Active\t" + nic["links"]["self"]["href"] + \
                                                ": " + json.dumps(nic) + "\n")
            elif get_active == False and nic["Status"]["State"] == "Disabled":
                sys.stdout.write("InActive\t" + nic["links"]["self"]["href"] + \
                                                ": " + json.dumps(nic) + "\n")

def ex21_set_active_ilo_nic(restobj, shared_nic):
    sys.stdout.write("\nEXAMPLE 21: Set the active iLO NIC\n")
    instances = restobj.search_for_type("Manager.")
    selected_nic_uri = None

    for instance in instances:
        tmp = restobj.rest_get(instance["href"])  
        response = restobj.rest_get(tmp.dict["links"]["EthernetNICs"]["href"])
        
        for nic in response.dict["Items"]:
            try:
                if (nic["Oem"]["Hp"]["SupportsFlexibleLOM"] == True and \
                                                            shared_nic == True):
                    selected_nic_uri = nic["links"]["self"]["href"]
                    break
            except KeyError:
                pass
    
            try:
                if (nic["Oem"]["Hp"]["SupportsLOM"] == True and \
                                                            shared_nic == True):
                    selected_nic_uri = nic["links"]["self"]["href"]
                    break
            except KeyError:
                pass
    
            if not shared_nic:
                selected_nic_uri = nic["links"]["self"]["href"]
                break
            elif not selected_nic_uri:
                sys.stderr.write("\tShared NIC is not supported\n")
                break
    
        if selected_nic_uri:
            body = {"Oem": {"Hp": {"NICEnabled": True}}}
            response = restobj.rest_patch(selected_nic_uri, body)
            restobj.error_handler(response)

def ex22_dump_iml(restobj):
    sys.stdout.write("\nEXAMPLE 22: Dump Integrated Management Log\n")
    instances = restobj.search_for_type("LogService.")

    for instance in instances:
        if instance["href"].endswith("IML"):
            tmp = restobj.rest_get(instance["href"])

            for entry in tmp.dict["links"]["Entries"]:
                response = restobj.rest_get(entry["href"])
                
                for log_entry in response.dict["Items"]:
                    sys.stdout.write(log_entry["Severity"] + ": Class " + \
                         str(log_entry["Oem"]["Hp"]["Class"]) + \
                         " / Code " + str(log_entry["Oem"]["Hp"]["Code"]) + \
                         ":\t" + log_entry["Message"] + "\n")

def ex23_dump_ilo_event_log(restobj):
    sys.stdout.write("\nEXAMPLE 23: Dump iLO Event Log\n")
    instances = restobj.search_for_type("LogService.")

    for instance in instances:
        if instance["href"].endswith("IEL"):
            tmp = restobj.rest_get(instance["href"])

            for entry in tmp.dict["links"]["Entries"]:
                response = restobj.rest_get(entry["href"])
                
                for log_entry in response.dict["Items"]:
                    sys.stdout.write(log_entry["Message"] + "\n")

def ex24_clear_iml(restobj):
    sys.stdout.write("\nEXAMPLE 24: Clear Integrated Management Log\n")
    instances = restobj.search_for_type("LogService.")

    for instance in instances:
        if instance["href"].endswith("IML"):
            body = {"Action": "ClearLog"}
            response = restobj.rest_post(instance["href"], body)
            restobj.error_handler(response)

def ex25_clear_ilo_event_log(restobj):
    sys.stdout.write("\nEXAMPLE 25: Clear iLO Event Log\n")
    instances = restobj.search_for_type("LogService.")

    for instance in instances:
        if instance["href"].endswith("IEL"):
            body = {"Action": "ClearLog"}
            response = restobj.rest_post(instance["href"], body)
            restobj.error_handler(response)

def ex26_configure_snmp(restobj, snmp_mode, snmp_alerts):
    sys.stdout.write("\nEXAMPLE 26: Configure iLO SNMP Settings\n")
    instances = restobj.search_for_type("SnmpService.")

    for instance in instances:
        body = {"Mode": snmp_mode, "AlertsEnabled": snmp_alerts}
        response = restobj.rest_patch(instance["href"], body)
        restobj.error_handler(response)

def ex27_get_schema(restobj, schema_prefix):
    sys.stdout.write("\nEXAMPLE 27:  Find and return schema " + \
                                                        schema_prefix + "\n")
    response = restobj.rest_get("/rest/v1/Schemas")

    for schema in response.dict["Items"]:
        if schema["Schema"].startswith(schema_prefix):
            for location in schema["Location"]:
                extref_uri = location["Uri"]["extref"]
                response = restobj.rest_get(extref_uri)
                if response.status == 200:
                    sys.stdout.write("\tFound " + schema_prefix + " at "\
                                                        + extref_uri + "\n")
                    return
                else:
                    sys.stderr.write("\t" + schema_prefix + " not found at " \
                                                        + extref_uri + "\n")
                    return

    sys.stderr.write("Registry " + schema_prefix + " not found.\n")

def ex28_set_ilo_timezone(restobj, olson_timezone):
    sys.stdout.write("\nEXAMPLE 28: Set iLO's Timezone\n")
    sys.stdout.write("\tNOTE: This only works if iLO is NOT configured to " \
                                    "take time settings from DHCP v4 or v6\n")
    instances = restobj.search_for_type("HpiLODateTime.")

    for instance in instances:
        response = restobj.rest_get(instance["href"])

        for timezone in response.dict["TimeZoneList"]:
            if timezone["Name"].startswith(olson_timezone):
                body = {"TimeZone": {"Index": timezone["Index"]}}
                response = restobj.rest_patch(instance["href"], body)
                restobj.error_handler(response)

def ex29_set_ilo_ntp_servers(restobj, ntp_servers):
    sys.stdout.write("\nEXAMPLE 29:  Set iLO's NTP Servers\n")
    instances = restobj.search_for_type("HpiLODateTime.")

    for instance in instances:
        response = restobj.rest_get(instance["href"])

        sys.stdout.write("\tCurrent iLO Date/Time Settings:  " +
                json.dumps(response.dict["ConfigurationSettings"]) + "\n")
        sys.stdout.write("\tCurrent iLO NTP Servers:  " +
                            json.dumps(response.dict["NTPServers"]) + "\n")

        body = {"StaticNTPServers": ntp_servers}
        response = restobj.rest_patch(instance["href"], body)
        restobj.error_handler(response)

def ex30_get_powermetrics_average(restobj):
    sys.stdout.write("\nEXAMPLE 30: Report PowerMetrics Average Watts\n")
    instances = restobj.search_for_type("PowerMetrics.")

    for instance in instances:
        response = restobj.rest_get(instance["href"])
        
        if "PowerMetrics" not in response.dict or \
            "AverageConsumedWatts" not in response.dict["PowerMetrics"] or \
                        "IntervalInMin" not in response.dict["PowerMetrics"]:
            sys.stdout.write("\tPowerMetrics resource does not contain "\
                       "'AverageConsumedWatts' or 'IntervalInMin' property\n")
        else:
            sys.stdout.write("\t" + " AverageConsumedWatts = " + \
                 str(response.dict["PowerMetrics"]["AverageConsumedWatts"]) + \
                 " watts over a " + str(response.dict["PowerMetrics"]\
                                ["IntervalInMin"]) + " minute moving average\n")

def ex31_set_license_key(restobj, iLO_Key):
    sys.stdout.write("\nEXAMPLE 31: Set iLO License Key\n")
    instances = restobj.search_for_type("Manager.")

    for instance in instances:
        rsp = restobj.rest_get(instance["href"])

        body = dict()
        body["LicenseKey"] = iLO_Key
        response = restobj.rest_post(\
                 rsp.dict["Oem"]["Hp"]["links"]["LicenseService"]["href"], body)
        restobj.error_handler(response)

class RestObject(object):
    def __init__(self, host, login_account, login_password):
        self.rest_client = rest_client(base_url=host, \
                          username=login_account, password=login_password, \
                          default_prefix="/rest/v1")
        self.rest_client.login(auth=AuthMethod.SESSION)
        self.SYSTEMS_RESOURCES = ex1_get_resource_directory(self)
        self.MESSAGE_REGISTRIES = ex2_get_base_registry(self)

    def __del__(self):
        self.rest_client.logout()

    def search_for_type(self, type):
        instances = []

        for item in self.SYSTEMS_RESOURCES["resources"]:
            foundsettings = False

            if type.lower() in item["Type"].lower():
                for entry in self.SYSTEMS_RESOURCES["resources"]:
                    if (item["href"] + "/settings").lower() == \
                                                        (entry["href"]).lower():
                        foundsettings = True

                if not foundsettings:
                    instances.append(item)

        if not instances:
            sys.stderr.write("\t'%s' resource or feature is not " \
                                            "supported on this system\n" % type)
        return instances

    def error_handler(self, response):
        if not self.MESSAGE_REGISTRIES:
            sys.stderr.write("ERROR: No message registries found.")

        try:
            message = json.loads(response.text)
            newmessage = message["Messages"][0]["MessageID"].split(".")
        except:
            sys.stdout.write("\tNo extended error information returned by " \
                                                                    "iLO.\n")
            return

        for err_mesg in self.MESSAGE_REGISTRIES:
            if err_mesg != newmessage[0]:
                continue
            else:
                for err_entry in self.MESSAGE_REGISTRIES[err_mesg]:
                    if err_entry == newmessage[3]:
                        sys.stdout.write("\tiLO return code %s: %s\n" % (\
                                   message["Messages"][0]["MessageID"], \
                                   self.MESSAGE_REGISTRIES[err_mesg][err_entry]\
                                   ["Description"]))

    def rest_get(self, suburi):
        """REST GET"""
        return self.rest_client.get(path=suburi)

    def rest_patch(self, suburi, request_body, optionalpassword=None):
        """REST PATCH"""
        sys.stdout.write("PATCH " + str(request_body) + " to " + suburi + "\n")
        response = self.rest_client.patch(path=suburi, body=request_body, \
                                            optionalpassword=optionalpassword)
        sys.stdout.write("PATCH response = " + str(response.status) + "\n")

        return response

    def rest_put(self, suburi, request_body, optionalpassword=None):
        """REST PUT"""
        sys.stdout.write("PUT " + str(request_body) + " to " + suburi + "\n")
        response = self.rest_client.put(path=suburi, body=request_body, \
                                            optionalpassword=optionalpassword)
        sys.stdout.write("PUT response = " + str(response.status) + "\n")

        return response


    def rest_post(self, suburi, request_body):
        """REST POST"""
        sys.stdout.write("POST " + str(request_body) + " to " + suburi + "\n")
        response = self.rest_client.post(path=suburi, body=request_body)
        sys.stdout.write("POST response = " + str(response.status) + "\n")

        return response


    def rest_delete(self, suburi):
        """REST DELETE"""
        sys.stdout.write("DELETE " + suburi + "\n")
        response = self.rest_client.delete(path=suburi)
        sys.stdout.write("DELETE response = " + str(response.status) + "\n")

        return response

if __name__ == "__main__":
    # When running on the server locally use the following commented values
    # iLO_host = "blobstore://."
    # iLO_account = "None"
    # iLO_password = "None"

    # When running remotely connect using the iLO address, iLO account name, 
    # and password to send https requests
    #iLO_host = "https://16.83.16.43"
    #login_account = "admin"
    #login_password = "password"

    #try:
    #    with open("/etc/puppetlabs/code/environments/production/modules/pythonilorestlibrary/files/credentials.txt", "r") as f:
    #        credentialslist = f.read()
    #        credentialslist = credentialslist.split("\n")
    #        credentialslist = filter(None, credentialslist)
    #except Exception:
    #    sys.stderr.write("error opening credentials \n")

    #accepts arguments when run,
    #RestfulApiExamples.py https://xx.xx.xx.xx username password
    try:
        iLO_host = "https://" + str(sys.argv[1])
    except Exception:
        sys.stderr.write("iLO address error \n")
    try:
        login_account = str(sys.argv[2])
        login_password = str(sys.argv[3])
    except IndexError:
        sys.stderr.write("Missing parameters \n")
    except Exception:
        sys.stderr.write("Credentials Error \n")
    #try:
    #    iLO_host = "https://"+str(credentialslist[0])
    #except Exception:
    #    sys.stderr.write("iLO address error \n")
    #try:
    #    login_account = str(credentialslist[1])
    #    login_password = str(credentialslist[2])
    #except IndexError:
    #    sys.stderr.write("Missing parameters \n")
    #except Exception:
    #    sys.stderr.write("Credentials Error \n")

    # Create a REST object
    try:
        REST_OBJ = RestObject(iLO_host, login_account, login_password)
    except Exception:
        sys.stderr.write("Error with credentials \n")

    # These examples are comment out because they are now part of the RestObject
    # class. They are initiated when you create a RestObject class object.
    #ex1_get_resource_directory(REST_OBJ)
    #ex2_get_base_registry(REST_OBJ)

    # Uncomment the examples you would like to execute
    #ex3_change_bios_setting(REST_OBJ, "AdminName", "admin")
    #ex4_reset_server(REST_OBJ)
    #ex5_enable_secure_boot(REST_OBJ, False)
    #ex6_bios_revert_default(REST_OBJ)
    #ex7_change_boot_order(REST_OBJ)
    #ex8_change_temporary_boot_order(REST_OBJ, "Hdd")
    ex9_find_ilo_mac_address(REST_OBJ)
    #ex10_add_ilo_user_account(REST_OBJ, "name", "username", "password")
    #ex11_modify_ilo_user_account(REST_OBJ, "name", "newname", "newusername", "newpassword")
    #ex12_remove_ilo_account(REST_OBJ, "newname")
    #ex13_dump_ilo_nic(REST_OBJ)
    #ex14_sessions(REST_OBJ, "admin", "admin123")
    #ex15_set_uid_light(REST_OBJ, True)
    #ex16_computer_details(REST_OBJ)
    #ex17_mount_virtual_media_iso(REST_OBJ, "http://10.0.0.100/test.iso", True)
    #ex18_set_server_asset_tag(REST_OBJ, "assettaghere")
    #ex19_reset_ilo(REST_OBJ)
    #ex20_get_ilo_nic(REST_OBJ, True)
    #ex21_set_active_ilo_nic(REST_OBJ, False)
    #ex22_dump_iml(REST_OBJ)
    #ex23_dump_ilo_event_log(REST_OBJ)
    #ex24_clear_iml(REST_OBJ)
    #ex25_clear_ilo_event_log(REST_OBJ)
    #ex26_configure_snmp(REST_OBJ, "Agentless", False)
    #ex27_get_schema(REST_OBJ, "ComputerSystem")
    #ex28_set_ilo_timezone(REST_OBJ, "America/Chicago")
    #ex29_set_ilo_ntp_servers(REST_OBJ, ["192.168.0.1", "192.168.0.2"])
    #ex30_get_powermetrics_average(REST_OBJ)
    #ex31_set_license_key(REST_OBJ, "test_iLO_Key")
