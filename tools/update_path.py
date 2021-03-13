#!/usr/bin/python3
"""Update LD_LIBRARY_PATH and PATH snapcraft.yaml in the current
working directory.

Editing the lines in question directly in snapcraft.yaml is pretty
terrible, as the lines are long, and we cannot break them up into a
normal yaml string w/ a | and still get snapcraft's variable
expansion. (Or, if we can, I don't know what magic invocation will do
so.)

This script will not check in the new snapcraft.yaml. You should
inspect the updates and check in the file yourself!

"""

import os
import shutil
import sys


LD_LIBRARY_PATH = (
    '$SNAP/lib',
    '$SNAP/lib/$SNAPCRAFT_ARCH_TRIPLET',
    '$SNAP/usr/lib',
    '$SNAP/usr/lib/$SNAPCRAFT_ARCH_TRIPLET',
    '$SNAP/usr/lib/$SNAPCRAFT_ARCH_TRIPLET/pulseaudio',)
PATH = (
    '$SNAP/usr/sbin',
    '$SNAP/usr/bin',
    '$SNAP/sbin',
    '$SNAP/bin',
    '$PATH')


def main():
    """Replace PATH and LD_LIBRARY_PATH with lists above.

    This is dead simple code that relies on there being one setting
    for LD_LIBRARY_PATH and PATH. It needs to be updated to be made
    smarter if more instances are added.

    Note that it would be nice if we could just read and write the
    yaml, but we'd chomp comments if we did so. And we like our
    comments!

    """
    if not os.path.isfile('./snapcraft.yaml'):
        print('Cannot file snapcraft.yaml in the current working dir!')
        print('Exiting.')
        sys.exit(1)

    print('snapcraft.yaml found in the current working dir. '
          'Updating LD_LIBRARY_PATH and PATH ...')

    libs = ':'.join(LD_LIBRARY_PATH)
    path_ = ':'.join(PATH)

    with open('./snapcraft.yaml', 'r') as source:
        with open('./snapcraft.yaml.updated', 'w') as dest:
            lines = source.readlines()
            for line in lines:
                if line.startswith('  LD_LIBRARY_PATH: '):
                    line = '  LD_LIBRARY_PATH: {}\n'.format(libs)
                if line.startswith('  PATH: '):
                    line = '  PATH: {}\n'.format(path_)

                dest.write(line)

    shutil.move('./snapcraft.yaml.updated', './snapcraft.yaml')

    print('File updated! Please manually inspect the changes '
          'and commit them via git.')


if __name__ == '__main__':
    main()
