#!/bin/bash
##############################################################################
#
# Make a dev box for microstack!
#
# This is a tool to quickly spin up a multipass vm and set it up for
# developing MicroStack.
#
##############################################################################

set -e

DISTRO=18.04

MACHINE=$(petname) || :
if [ -z "$MACHINE" ]; then
    echo -n "Please enter a machine name: "
    read MACHINE
fi

NAME=$(git config --global user.name)
if [ -z "$NAME" ]; then
    echo -n "Please enter your name: "
    read NAME
fi

EMAIL=$(git config --global user.email)
if [ -z "$EMAIL" ]; then
    echo -n "Please enter your email address: "
    read EMAIL
fi

# Make a vm
multipass launch --cpus 2 --mem 16G $DISTRO --name $MACHINE --disk 100G

PREFIX="multipass exec $MACHINE --  "

$PREFIX sudo apt update
$PREFIX sudo apt upgrade -y
$PREFIX sudo apt install tox git-review -y
$PREFIX git clone https://opendev.org/x/microstack.git

$PREFIX sudo snap install lxd
$PREFIX sudo /snap/bin/lxd.migrate -yes

$PREFIX git config --global user.name "$NAME"
$PREFIX git config --global user.email "$EMAIL"

multipass connect $MACHINE
