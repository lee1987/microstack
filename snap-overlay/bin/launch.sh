#!/bin/bash

set -e

# Check for microstack.init. TODO: just run microstack.init ...
if ! [ "$(snapctl get initialized)" == "true" ]; then
    echo "Microstack is not initialized. Please run microstack.init!"
    exit 1;
fi

source $SNAP_COMMON/etc/microstack.rc

if [ -z "$1" ]; then
    echo "Please specify a name for the server."
    exit 1
else
    SERVER=$1
fi

echo "Launching instance ..."
openstack server create --flavor m1.tiny --image cirros --nic net-id=test --key-name microstack $SERVER

TRIES=0
while [[ $(openstack server list | grep $SERVER | grep ERROR) ]]; do
    TRIES=$(($TRIES + 1))
    if test $TRIES -gt 3; then
        break
    fi
    echo "I ran into an issue launching an instance. Retrying ... (try $TRIES of 3)"
    openstack server delete $SERVER
    openstack server create --flavor m1.tiny --image cirros --nic net-id=test --key-name microstack $SERVER
    while [[ $(openstack server list | grep $SERVER | grep BUILD) ]]; do
        sleep 1;
    done
done

echo "Allocating floating ip ..."
ALLOCATED_FIP=`openstack floating ip create -f value -c floating_ip_address external`
openstack server add floating ip $SERVER $ALLOCATED_FIP

echo "Waiting for server to become ACTIVE."
while :; do
    if [[ $(openstack server list | grep $SERVER | grep ACTIVE) ]]; then
        openstack server list
        echo "Access your server with 'ssh -i $HOME/.ssh/id_microstack cirros@$ALLOCATED_FIP'"
        break
    fi
    if [[ $(openstack server list | grep $SERVER | grep ERROR) ]]; then
        openstack server list
        echo "Uh-oh. There was an error. Run `journalctl -xe` for details."
        exit 1
    fi
done

extgateway=`snapctl get questions.ext-gateway`
echo "You can also visit the openstack dashboard at 'http://$extgateway/'"
