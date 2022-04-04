# fuse-tool-cellfie

FUSE stands for "[FAIR](https://www.go-fair.org/)", Usable, Sustainable, and Extensible.

FUSE tools can be run as a stand-alone tool (see `up.sh` below) or as a plugin to a FUSE deployment (e.g., [fuse-immcellfie](http://github.com/RENCI/fuse-immcellfie)). FUSE tools are one of 3 flavors of appliances:
* provider: provides a common data access protocol to a digital object provider
* mapper: maps the data from a particular data provider type into a common data model with consistent syntax and semantics
* tool: analyzes data from a mapper, providing results and a specification that describes the data types and how to display them.

## prerequisites:
* python 3.10 or higher
* Docker 20.10 or higher
* docker-compose v1.28 a
* jq
* create docker volume for staged CellFie inputs: `docker volume create --opt type=none --opt o=bind --opt device=/path/to/fuse-tool-cellfie/CellFie/input cellfie-input-data`


Tips for updating docker-compose on Centos:

```
sudo yum install jq
VERSION=$(curl --silent https://api.github.com/repos/docker/compose/releases/latest | jq .name -r)
sudo mv /usr/local/bin/docker-compose /usr/local/bin/docker-compose.old-version
DESTINATION=/usr/local/bin/docker-compose
sudo curl -L https://github.com/docker/compose/releases/download/${VERSION}/docker-compose-$(uname -s)-$(uname -m) -o $DESTINATION
sudo chmod 755 $DESTINATION
```


## configuration

1. Copy `sample.env` to `.env` and edit to suit your provider:
* __API_PORT__ pick a unique port to avoid appliances colliding with each other
* __LOG_LEVEL__ DEBUG, INFO, WARNING, ERROR

## start
```
./up.sh
```

## validate installation

Start container prior to validations:
```
./up.sh
```
Simple test from command line

```
curl -X 'GET' 'http://localhost:${API_PORT}/openapi.json' -H 'accept: application/json' | jq -r 2> /dev/null
```

## stop
```
./down.sh
```
