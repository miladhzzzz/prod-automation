#!/bin/bash

docker run -d --privileged -v /usr/lib/systemd/system/docker.sock:/var/run/docker.sock -p 5001:5001 <your-image-name>
