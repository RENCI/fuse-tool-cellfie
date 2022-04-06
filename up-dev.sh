#!/bin/bash

docker-compose -f docker-compose-dev.yml up --build -V --remove-orphans -d
