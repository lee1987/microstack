import argparse
import json
import os
import subprocess
import time
import sys

from typing import List


def check(*args: List[str]) -> int:
    """Execute a shell command, raising an error on failed excution.

    :param args: strings to be composed into the bash call.

    """
    return subprocess.check_call(args, env=os.environ)


def check_output(*args: List[str]) -> str:
    """Execute a shell command, returning the output of the command.

    :param args: strings to be composed into the bash call.

    Include our env; pass in any extra keyword args.
    """
    return subprocess.check_output(args, universal_newlines=True,
                                   env=os.environ).strip()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('image',
                        help='The name of the openstack image to use.')
    parser.add_argument('-n', '--name', help='The name of the instance')
    parser.add_argument('-k', '--key', help='ssh key to use',
                        default='microstack')
    parser.add_argument('-f', '--flavor', help='Flavor to use.',
                        default='m1.tiny')
    parser.add_argument('-t', '--net-id', help='Network', default='test')
    parser.add_argument('-w', '--wait', action='store_true',
                        help='Wait for server to become active before exiting')
    parser.add_argument('-r', '--retry', action='store_true',
                        help='Retry failed launch attempts')
    # TODO: add a passthrough for other openstack 'server create'
    # args. Manually specifying them here is a bit silly.  For now, we
    # need to specify availability zone in some tests, so we add it
    # here.
    parser.add_argument('--availability-zone',
                        help='passthrough to avail zone')

    args = parser.parse_args()
    return args


def check_keypair():
    """
    Check for the microstack keypair's existence, creating it if it doesn't.

    """
    key_path = check_output(
        'snapctl', 'get', 'config.credentials.key-pair').format(**os.environ)

    if os.path.exists(key_path):
        return key_path

    print('Creating local "microstack" ssh key at {}'.format(key_path))
    # TODO: make sure that we get rid of this path on snap
    # uninstall. If we don't, check to make sure that MicroStack
    # has a microstack ssh key, in addition to checking for the
    # existence of the file.
    key_dir = os.sep.join(key_path.split(os.sep)[:-1])
    check('mkdir', '-p', key_dir)
    check('chmod', '700', key_dir)

    id_ = check_output('openstack', 'keypair', 'create', 'microstack')

    with open(key_path, 'w') as file_:
        file_.write(id_)
        check('chmod', '600', key_path)

    return key_path


def create_server(name, args):

    cmd = [
        'openstack', 'server', 'create',
        '--flavor', args.flavor,
        '--image', args.image,
        '--nic', 'net-id={}'.format(args.net_id),
        '--key-name', args.key,
        name, '--format', 'json'
    ]
    if args.availability_zone:
        cmd += ['--availability-zone', args.availability_zone]

    ret = json.loads(check_output(*cmd))
    return ret['id']


def delete_server(server_id):
    check('openstack', 'server', 'delete', server_id)


def check_server(name, server_id, args):
    status = 'Unknown'

    retries = 0
    max_retries = 10

    waits = 0
    max_waits = 1000  # 100 seconds + ~1000 calls to `openstack server list`.

    while True:
        status_ = check_output('openstack', 'server', 'list',
                               '--format', 'json')
        status_ = json.loads(status_)
        for server in status_:
            if server['ID'] == server_id:
                status = server['Status']

        if not status:
            # Something went wrong ...
            break

        if not args.wait and not args.retry:
            # Just return BUILD or ACTIVE or Unknown.
            break

        if waits < 1:
            print("Waiting for server to build ...")

        if status == 'BUILD':
            if waits <= max_waits:
                waits += 1
                time.sleep(0.1)
                continue
            # Looks like we're stuck! Fall through to ERROR check
            # below.
            status = 'BUILD (stuck)'

        if status in ['ERROR', 'BUILD (stuck)']:
            if not args.retry or retries > max_retries:
                break

            print('Ran into an error launching server. Retrying ...')
            delete_server(server_id)
            server_id = create_server(name, args)
            waits = 0  # Reset waits
            retries += 1
            continue

        if status == 'ACTIVE':
            break

    return (status, server_id)


def launch(name, args):
    """Launch a server!"""

    if args.key == 'microstack':
        # Make sure that we have a default ssh key to hand off to the
        # instance.
        key_path = check_keypair()
    else:
        # We've been passed an ssh key with an unknown path. Drop in
        # some placeholder text for the message at the end of this
        # routine, but don't worry about verifying it. We trust the
        # caller to have created it!
        key_path = '/path/to/ssh/key'

    print("Launching server ...")
    server_id = create_server(name, args)

    status, server_id = check_server(name, server_id, args)
    if status not in ['BUILD', 'ACTIVE']:
        print('Uh-oh. Something went wrong launching {}. Status is {}.'.format(
            name, status))
        sys.exit(1)

    print('Allocating floating ip ...')
    ip = check_output('openstack', 'floating', 'ip', 'create', '-f', 'value',
                      '-c', 'floating_ip_address', 'external')
    check('openstack', 'server', 'add', 'floating', 'ip', server_id, ip)

    # We've launched! Make some guesses about usernames and the
    # location of the ssh key in the operator's system, so we can tell
    # the them how to access their new server.  TODO: is it possible
    # to make this logic more sophisticated?
    username = '<username>'
    if 'fedora' in args.image.lower():
        username = 'fedora'
    if 'ubuntu' in args.image.lower():
        username = 'ubuntu'
    if 'cirros' in args.image.lower():
        username = 'cirros'

    print("""\
Server {name} launched! (status is {status})

Access it with `ssh -i {key_path} {username}@{ip}`\
""".format(name=name, status=status, key_path=key_path,
           username=username, ip=ip))

    gate = check_output('snapctl', 'get', 'config.network.ext-gateway')
    port = check_output('snapctl', 'get', 'config.network.ports.dashboard')

    print('You can also visit the OpenStack dashboard at http://{}:{}'.format(
        gate, port))


def main():
    args = parse_args()
    # Call petname via bash, due to
    # https://bugs.launchpad.net/snapcraft/+bug/1860768
    name = args.name or check_output(
        'petname', '-d', '{}/usr/share/petname'.format(
            os.environ.get('SNAP', '')))

    # Parse microstack.rc
    # TODO: we need a share lib that does this in a more robust way.
    mstackrc = '{SNAP_COMMON}/etc/microstack.rc'.format(**os.environ)
    with open(mstackrc, 'r') as rc_file:
        for line in rc_file.readlines():
            if not line.startswith('export'):
                continue
            key, val = line[7:].split('=')
            os.environ[key.strip()] = val.strip()

    return launch(name, args)


if __name__ == '__main__':
    main()
