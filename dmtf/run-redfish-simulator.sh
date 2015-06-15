#!/bin/bash

# Th -p option needs to be after the run command. No warning is given if before but doesn't work
docker run -d -p 8000:80 --name "redfish-simulator" localhost:5000/redfish-simulator
