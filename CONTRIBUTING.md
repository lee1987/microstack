# Contributing

## Building MicroStack

MicroStack builds are tested on an Ubuntu 18.04 LTS machine with 16G
of RAM, two cpu cores, and 50G of free disk space. You should be able
to build MicroStack on any machine matching those minimum specs, as
long as it is capable of running bash and snapd. If you run into any
snags doing so, please file bugs at
https://bugs.launchpad.net/microstack

To build MicroStack on a capable machine, run:

    git clone https://opendev.org/x/microstack.git
    cd microstack
    tox

This will run tools/multipass_build.sh, which installs some
dependencies on your system, and then run some tests. If you want to
have more control over the build process and installed dependencies,
replace the tox line with:

    snapcraft

or

    snapcraft --use-lxd

(You may have to install snapcraft and lxd or multipass on your system
first if you go this route -- inspect tools/multipass_build.sh and
tools/lxd_build.sh for tips.)

## How the code is structured

MicroStack is a Snap, which means that, after it has been built, it
contains all the code and dependencies that it needs, destined to be
mounted in a read only file system on a host.

Before contributing, you probably want to read the general Snap
Documentation here: https://docs.snapcraft.io/snap-documentation/3781

There are several important files and directories in MicroStack, some
of which are like those in other snaps, some of which are unique to
MicroStack:

### The Snapcraft yaml

    ./snapcraft.yaml

This is the core of the snap. You'll want to start here when it comes
to adding code. And you may not need to leave this file at all.

### Snap overlay

    ./snap-overlay

Any files you add to snap-overlay will get written to the
corresponding place in the file hierarchy under
`/snap/microstack/common/`. Drop files in here if you want to insert a
file or directory that does not come bundled by default with the
OpenStack source tarballs.

### Snap-openstack yaml

    ./snap-overlay/snap-openstack.yaml

This is a yaml file unique to Snaps created by the OpenStack team at
Canonical. It creates a command called `snap-openstack`, which wraps
OpenStack daemons and scripts.

Documentation for this helper lives here:
https://github.com/openstack/snap.openstack

It's installed by the openstack-projects part.

If you're adding an OpenStack component to the snap, you may find it
useful to take a look at the parts and apps that take advantage of
snap-openstack, and add your own section to `snap-openstack.yaml`.

### Filing bugs and submitting pull requests

We track bugs and features on Launchpad, at
https://bugs.launchpad.net/microstack

To submit a bugfix or feature, please create a Merge Proposal against
the OpenDev repository. See the OpenStack Developer's Guide for more
detail: https://docs.openstack.org/infra/manual/developers.html
