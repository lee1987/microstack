#!/bin/bash
##############################################################################
#
# Make a microstack!
#
# This is a tool to very quickly spin up a multipass vm, install
# microstack (from the compiled local .snap), and get a shell in
# microstack's environment.
#
# It requires that you have installed petname.
#
##############################################################################

set -ex

DISTRO=18.04
MACHINE=$(petname)

# Make a vm
multipass launch --cpus 2 --mem 16G $DISTRO --name $MACHINE

# Install the snap
multipass copy-files microstack_ussuri_amd64.snap $MACHINE:
multipass exec $MACHINE -- \
          sudo snap install --dangerous microstack*.snap

multipass exec $MACHINE -- \
	  sudo snap connect microstack:libvirt
multipass exec $MACHINE -- \
	  sudo snap connect microstack:netlink-audit
multipass exec $MACHINE -- \
	  sudo snap connect microstack:firewall-control
multipass exec $MACHINE -- \
	  sudo snap connect microstack:hardware-observe
multipass exec $MACHINE -- \
	  sudo snap connect microstack:kernel-module-observe
multipass exec $MACHINE -- \
	  sudo snap connect microstack:kvm
multipass exec $MACHINE -- \
	  sudo snap connect microstack:log-observe
multipass exec $MACHINE -- \
	  sudo snap connect microstack:mount-observe
multipass exec $MACHINE -- \
	  sudo snap connect microstack:netlink-connector
multipass exec $MACHINE -- \
	  sudo snap connect microstack:network-observe
multipass exec $MACHINE -- \
	  sudo snap connect microstack:openvswitch-support
multipass exec $MACHINE -- \
	  sudo snap connect microstack:process-control
multipass exec $MACHINE -- \
	  sudo snap connect microstack:system-observe
multipass exec $MACHINE -- \
	  sudo snap connect microstack:network-control
multipass exec $MACHINE -- \
	  sudo snap connect microstack:system-trace
multipass exec $MACHINE -- \
	  sudo snap connect microstack:block-devices
multipass exec $MACHINE -- \
	  sudo snap connect microstack:raw-usb
multipass exec $MACHINE -- \
	  sudo snap connect microstack:hugepages-control
# TODO: add the below once the interface is merge into snapd.
# multipass exec $MACHINE -- \
#	  sudo snap connect microstack:microstack-support

# Drop the user into a snap shell, as root.
multipass exec $MACHINE -- \
          sudo snap run --shell microstack.init

