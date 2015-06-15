#!/bin/bash

# Build and tag images
docker build -t "redfish-simulator" .
docker tag redfish-simulator:latest localhost:5000/redfish-simulator
