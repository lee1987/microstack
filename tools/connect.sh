#!/bin/bash
#
# Utility script for connecting all the interfaces that MicroStack
# wants. Useful for testing strict confinement. Not useful for use in
# the deployed snap, as it can run from within a snap.

set -e

for i in `sudo snap connections microstack`; do
    if [[ $i =~ ^microstack:.* ]]; then
        echo $i;
        sudo snap connect $i;
    fi
done

