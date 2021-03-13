#!/usr/bin/env python3

import argparse
import sys

import launch.main
import cluster.add_compute
import init.main


def main():
    '''Implements a proxy command called "microstack"'''

    parser = argparse.ArgumentParser(
        description='microstack',
        usage='''microstack <command> [<args>]

Available commands:
   init         initialize a MicroStack node
   add-compute  generate a connection string for a node to join the cluster
   launch       launch a virtual machine
''')
    parser.add_argument('command',
                        help='A subcommand to run:\n'
                        ' {init, launch, add-compute}')
    args = parser.parse_args(sys.argv[1:2])

    COMMANDS = {
        'init': init.main.init,
        'add-compute': cluster.add_compute.main,
        'launch': launch.main.main
    }

    cmd = COMMANDS.get(args.command, None)
    if cmd is None:
        parser.print_help()
        raise Exception('Unrecognized command')

    # TODO: Implement this properly via subparsers and get rid of
    # extra modules.
    sys.argv[0] = sys.argv[1]
    # Get rid of the command name in the args and call the actual command.
    del(sys.argv[1])
    cmd()


if __name__ == '__main__':
    main()
