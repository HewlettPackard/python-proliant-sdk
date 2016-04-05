python-ilorestful-library
==============

.. contents:: :depth: 1

Description
----------

 HPE RESTful API for iLO is a RESTful application programming interface for the management of iLO and iLO Chassis Manager based HPE servers. REST (Representational State Transfer) is a web based software architectural style consisting a set of constraints that focus on a system's resource. HPE REST library performs the basic HTTP operations GET, POST, PUT, PATCH and DELETE on resources using the HATEOS (Hypermedia as the Engine of Application) REST architecture. The API allows the clients to manage and interact with iLO through a fixed URL and several URIs. Go to the `wiki <../../wiki>`_ for more details.

Installing
----------

.. code-block:: console

	pip install python-ilorest-library

Installing from source
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: console

	python setup.py sdist --formats=zip
	cd dist
	pip install python-ilorest-library-x.x.x.zip

Requirements
----------

Remote communication
~~~~~~~~~~~~~~~~~~~~~~~~~

 No special requirements.
 
Inband communication
~~~~~~~~~~~~~~~~~~~~~~~~~

 To enable support for inband communications. You must download the DLL/SO for your system: windows_ / linux_. It must be placed in your working environment path. 
 
.. _windows: https://www.hp.com/swpublishing/MTX-43efdf5067924c78a34bf384c9
.. _linux: https://www.hp.com/swpublishing/MTX-5f86c051cbd042a6975250da39

Usage
----------

.. code-block:: python
	import ilorest

Create a Rest Object
~~~~~~~~~~~~~~~~~~~~~~~~~
 In RestfulApiExamples.py module, a rest object instance is created by calling the **rest_client** method with four parameters: ip address, iLO user name, iLO password and the default prefix.
 
.. code-block:: python

	REST_OBJ = ilorest.rest_client(base_url=host,username=login_account, \
                              password=login_password, default_prefix='/rest/v1') 

Create a Redfish Object
~~~~~~~~~~~~~~~~~~~~~~~~~
 Just like Rest object, a Redfish object instance in RedfishAPiExamples.py is created by calling the **create_object** method with four parameters: ip address, iLO user name, iLO password and the default prefix.

.. code-block:: python

	REST_OBJ = ilorest.redfish_client(base_url=host,username=login_account, \ 
                                 password=login_password, default_prefix='/redfish/v1')   	

Login to the server
~~~~~~~~~~~~~~~~~~~~~~~~~
 You must login to the server to create a session. You can continue with a basic authentication, but it would less secure.

.. code-block:: python

	REST_OBJ.login(auth="session")

Perform a GET operation
~~~~~~~~~~~~~~~~~~~~~~~~~
 Do a GET operation on a given path.

.. code-block:: python

	response = REST_OBJ.get("/rest/v1/systems/1", None)

Logout the created session
~~~~~~~~~~~~~~~~~~~~~~~~~
 Make sure you logout every session you create as it will remain alive until it timesout.

.. code-block:: python

	REST_OBJ.logout()
	
Contributing
----------

 1. Fork it!
 2. Create your feature branch: `git checkout -b my-new-feature`
 3. Commit your changes: `git commit -am 'Add some feature'`
 4. Push to the branch: `git push origin my-new-feature`
 5. Submit a pull request :D

History
----------

  04/01/2016: Initial Commit

Copyright and License
---------------------

::

 Copyright 2016 Hewlett Packard Enterprise, Inc. All rights reserved.

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
