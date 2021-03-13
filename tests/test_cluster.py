#!/usr/bin/env python
"""
cluster_test.py

This is a test to verify that we can setup a small, two node cluster.

The host running this test must have at least 16GB of RAM, four cpu
cores, a large amount of disk space, and the ability to run multipass
vms.

"""

import json
import os
import sys
import unittest
import netifaces
import tenacity
import logging

sys.path.append(os.getcwd())

from tests.framework import Framework  # noqa E402

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
stream = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stream.setFormatter(formatter)
logger.addHandler(stream)


class TestCluster(Framework):

    def test_cluster(self):
        openstack_cmd = '/snap/bin/microstack.openstack'
        control_host = self._localhost
        control_host.install_microstack(path='microstack_ussuri_amd64.snap')

        # Get an IP address on the lxdbr0 bridge and use it for the
        # control IP so that the tunnel ports of the compute node target the
        # IP on the lxdbr0 subnet. Using netifaces only work for the
        # localhost control node scenario.
        ifaddrs = netifaces.ifaddresses('lxdbr0')[netifaces.AF_INET]
        # We expect only one address on this interface, if multiple are present
        # there is something wrong and we should fail the test and reassess.
        self.assertEqual(len(ifaddrs), 1)
        control_ip = ifaddrs[0]['addr']

        control_host.init_microstack(['--auto', '--control',
                                      f'--default-source-ip={control_ip}'])

        compute_host = self.add_lxd_host('focal')
        compute_host.copy_to('microstack_ussuri_amd64.snap', '/root/')

        # snapd does not come up immediately in the container.
        @tenacity.retry(wait=tenacity.wait_fixed(1),
                        stop=tenacity.stop_after_attempt(10))
        def wait_snapd():
            compute_host.check_call(['sudo', 'snap', 'list'])

        wait_snapd()

        # wait for an IPv4 address to appear on the container interface
        @tenacity.retry(wait=tenacity.wait_fixed(1),
                        stop=tenacity.stop_after_attempt(10))
        def wait_addr():
            logger.debug('Checking for an eth0 interface addresses presence'
                         ' in the container.')
            cmd = ['ip', '-4', '-o', 'addr', 'show', 'eth0']
            ip_out = compute_host.check_output(cmd).decode('utf-8')
            logger.debug(f'{" ".join(cmd)} output:\n{ip_out}')

        wait_addr()

        compute_host.install_microstack(path='microstack_ussuri_amd64.snap')

        # TODO add the following to args for init
        compute_host.check_call([
            'sudo', 'snap', 'set', 'microstack',
            f'config.network.control-ip={control_ip}'])

        connection_string = control_host.check_output([
            'sudo', 'microstack', 'add-compute'
        ]).decode('utf-8')
        self.assertTrue(connection_string)

        compute_host.check_call([
            'sudo', 'microstack.init', '--auto',
            '--compute', '--join', connection_string, '--debug'
        ])

        # Verify that our services look setup properly on compute node.
        services = compute_host.check_output([
            'systemctl', 'status', 'snap.microstack.*',
            '--no-page']).decode('utf-8')

        self.assertTrue('nova-compute' in services)
        self.assertFalse('keystone-' in services)

        compute_fqdn = compute_host.check_output([
            'hostname', '-f']).decode('utf-8')

        instance_name = 'test-instance'
        # Launch from the control host but schedule to the compute host.
        control_host.check_call([
            '/snap/bin/microstack.launch', 'cirros',
            '--name', instance_name, '--retry',
            '--availability-zone', f'nova:{compute_fqdn}'])

        # Verify endpoints
        compute_ip = compute_host.check_output([
            'sudo', 'snap',
            'get', 'microstack',
            'config.network.compute-ip'
        ]).decode('utf-8')
        self.assertFalse(compute_ip == control_ip)

        # Ping the instance
        ip = None
        servers = compute_host.check_output([
            openstack_cmd,
            'server', 'list', '--format', 'json'
        ]).decode('utf-8')
        servers = json.loads(servers)
        for server in servers:
            if server['Name'] == instance_name:
                ip = server['Networks'].split(",")[1].strip()
                break

        self.assertTrue(ip)

        control_host.check_call(['ping', '-c10', '-w11', ip])
        self.passed = True


if __name__ == '__main__':
    unittest.main(warnings='ignore')
