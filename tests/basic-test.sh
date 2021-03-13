#!/bin/bash
##############################################################################
#
# This is a "basic" test script for Microstack. It will install the
# microstack snap, spin up a test instance, and verify that the test
# instance is accessible, and can access the Internet.
#
# The basic test accepts two command line arguments:
#
# -u <channel> # First installs a released snap from the named
#              # channel, in order to test basic upgrade functionality.
# -m           # Run tests in a multipass machine.
# -d <distro>  # Ubuntu distro of the multipass machine to run tests
#              # within. Defaults to bionic.
#
##############################################################################

# Configuration and checks
set -e

export PATH=/snap/bin:$PATH

UPGRADE_FROM="none"
FORCE_QEMU=false
PREFIX=""
DISTRO="bionic"
HORIZON_IP="10.20.20.1"

while getopts u:d:mq option
do
    case "${option}"
    in
        u) UPGRADE_FROM=${OPTARG};;
        q) FORCE_QEMU=true;;
        m) PREFIX="multipass";;
    esac
done

if [ ! -f microstack_ussuri_amd64.snap ]; then
   echo "microstack_ussuri_amd64.snap not found."
   echo "Please run snapcraft before executing the tests."
   exit 1
fi

# Functions
dump_logs () {
    export DUMP_DIR=/tmp
    if [ $(whoami) == 'zuul' ]; then
        export DUMP_DIR="/home/zuul/zuul-output/logs";
    fi
    $PREFIX sudo journalctl -xe --no-pager > /tmp/journalctl.output
    $PREFIX sudo tar cvzf $DUMP_DIR/dump.tar.gz \
         /var/snap/microstack/common/log \
         /var/log/syslog \
         /tmp/journalctl.output
    if [[ $PREFIX == *"multipass"* ]]; then
        multipass copy-files $MACHINE:/tmp/dump.tar.gz .
    fi
}

# Setup
echo "++++++++++++++++++++++++++++++++++++++++++++++++++"
echo "++    Starting tests on localhost               ++"
echo "++      Upgrade from: $UPGRADE_FROM             ++"
echo "++++++++++++++++++++++++++++++++++++++++++++++++++"

# Possibly run in a multipass machine
if [ "$PREFIX" == "multipass" ]; then
    sudo snap install --classic --edge multipass
    which petname || sudo snap install petname
    MACHINE=$(petname)
    PREFIX="multipass exec $MACHINE --"

    multipass launch --cpus 2 --mem 16G $DISTRO --name $MACHINE
    multipass copy-files microstack_ussuri_amd64.snap $MACHINE:

    HORIZON_IP=`multipass info $MACHINE | grep IPv4 | cut -d":" -f2 \
        | tr -d '[:space:]'`
fi

# Possibly install a release of the snap before running a test.
if [ "${UPGRADE_FROM}" != "none" ]; then
    $PREFIX sudo snap install --${UPGRADE_FROM} microstack
fi

# Install the snap under test -- try again if the machine is not yet ready.
$PREFIX sudo snap install --dangerous microstack*.snap
$PREFIX sudo snap connect microstack:libvirt
$PREFIX sudo snap connect microstack:netlink-audit
$PREFIX sudo snap connect microstack:firewall-control
$PREFIX sudo snap connect microstack:hardware-observe
$PREFIX sudo snap connect microstack:kernel-module-observe
$PREFIX sudo snap connect microstack:kvm
$PREFIX sudo snap connect microstack:log-observe
$PREFIX sudo snap connect microstack:mount-observe
$PREFIX sudo snap connect microstack:netlink-connector
$PREFIX sudo snap connect microstack:network-observe
$PREFIX sudo snap connect microstack:openvswitch-support
$PREFIX sudo snap connect microstack:process-control
$PREFIX sudo snap connect microstack:system-observe
$PREFIX sudo snap connect microstack:network-control
$PREFIX sudo snap connect microstack:system-trace
$PREFIX sudo snap connect microstack:block-devices
$PREFIX sudo snap connect microstack:raw-usb
$PREFIX sudo snap connect microstack:hugepages-control
# $PREFIX sudo snap connect microstack:microstack-support


$PREFIX sudo /snap/bin/microstack.init --auto

# Comment out the above and uncomment below to install the version of
# the snap from the store.
# TODO: add this as a flag.
# $PREFIX sudo snap install --classic --edge microstack

# If kvm processor extensions not supported, switch to qemu
# TODO: just do this in the install step of the snap
if ! [ $($PREFIX egrep "vmx|svm" /proc/cpuinfo | wc -l) -gt 0 ]; then
    FORCE_QEMU=true;
fi
if [ "$FORCE_QEMU" == "true" ]; then
    cat<<EOF > /tmp/hypervisor.conf
[DEFAULT]
compute_driver = libvirt.LibvirtDriver

[workarounds]
disable_rootwrap = True

[libvirt]
virt_type = qemu
cpu_mode = host-model
EOF
    if [[ $PREFIX == *"multipass"* ]]; then
        multipass copy-files /tmp/hypervisor.conf $MACHINE:/tmp/hypervisor.conf
    fi
    $PREFIX sudo cp /tmp/hypervisor.conf \
         /var/snap/microstack/common/etc/nova/nova.conf.d/hypervisor.conf
    $PREFIX sudo snap restart microstack
fi

# Run microstack.launch
$PREFIX /snap/bin/microstack.launch breakfast || (dump_logs && exit 1)

# Verify that endpoints are setup correctly
# List of endpoints should contain 10.20.20.1
if ! $PREFIX /snap/bin/microstack.openstack endpoint list | grep "10.20.20.1"; then
    echo "Endpoints are not set to 10.20.20.1!";
    exit 1;
fi
# List of endpoints should not contain localhost
if $PREFIX /snap/bin/microstack.openstack endpoint list | grep "localhost"; then
    echo "Endpoints are not set to 10.20.20.1!";
    exit 1;
fi


# Verify that microstack.launch completed
IP=$($PREFIX /snap/bin/microstack.openstack server list | grep breakfast | cut -d" " -f9)
echo "Waiting for ping..."
PINGS=1
MAX_PINGS=40  # We might sometimes be testing qemu emulation, so we
              # want to give this some time ...
until $PREFIX ping -c 1 $IP &>/dev/null; do
    PINGS=$(($PINGS + 1));
    if test $PINGS -gt $MAX_PINGS; then
        echo "Unable to ping machine!";
        exit 1;
    fi
done;

ATTEMPTS=1
MAX_ATTEMPTS=40  # See above for note about qemu
USERNAME=$($PREFIX whoami | tr -d '\r')  # Possibly get username from
                                         # remote host, for use in
                                         # composing home dir below.
until $PREFIX ssh -oStrictHostKeyChecking=no -i \
          /home/$USERNAME/.ssh/id_microstack cirros@$IP -- \
          ping -c 1 91.189.94.250; do
    ATTEMPTS=$(($ATTEMPTS + 1));
    if test $ATTEMPTS -gt $MAX_ATTEMPTS; then
        echo "Unable to access Internet from machine!";
        exit 1;
    fi
    sleep 5
done;

echo "++++++++++++++++++++++++++++++++++++++++++++++++++"
echo "++   Running Horizon GUI tests                  ++"
echo "++++++++++++++++++++++++++++++++++++++++++++++++++"

export HORIZON_IP
if [[ $PREFIX == *"multipass"* ]]; then
    echo "Opening $HORIZON_IP:80 up to the outside world."
    cat<<EOF > /tmp/_10_hosts.py
# Allow all hosts to connect to this machine
ALLOWED_HOSTS = ['*',]
EOF
    multipass copy-files /tmp/_10_hosts.py $MACHINE:/tmp/_10_hosts.py
    $PREFIX sudo cp /tmp/_10_hosts.py \
         /var/snap/microstack/common/etc/horizon/local_settings.d/
    $PREFIX sudo snap restart microstack
fi
tests/test_horizonlogin.py
echo "Horizon tests complete!."
unset HORIZON_IP

# Cleanup
echo "++++++++++++++++++++++++++++++++++++++++++++++++++"
echo "++   Completed tests. Cleaning up               ++"
echo "++++++++++++++++++++++++++++++++++++++++++++++++++"
unset IP
if [[ $PREFIX == *"multipass"* ]]; then
    sudo multipass delete $MACHINE
    sudo multipass purge
else
    sudo snap remove --purge microstack
fi
