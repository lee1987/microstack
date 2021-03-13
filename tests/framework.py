import logging
import json
import unittest
import subprocess
import yaml

import petname
import tenacity
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By


# Setup logging
logger = logging.getLogger("microstack_test")
logger.setLevel(logging.DEBUG)
stream = logging.StreamHandler()
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
stream.setFormatter(formatter)
logger.addHandler(stream)


def gui_wrapper(func):
    """Start up selenium drivers, run a test, then tear them down."""

    def wrapper(cls, *args, **kwargs):

        # Setup Selenium Driver
        options = FirefoxOptions()
        options.add_argument("-headless")
        cls.driver = webdriver.Firefox(options=options)

        # Run function
        try:
            return func(cls, *args, **kwargs)

        finally:
            # Tear down driver
            cls.driver.quit()

    return wrapper


class TestHost:

    def __init__(self):
        pass

    def destroy(self):
        raise NotImplementedError

    def check_output(self, args, **kwargs):
        raise NotImplementedError

    def call(self, args, **kwargs):
        raise NotImplementedError

    def check_call(self, args, **kwargs):
        raise NotImplementedError

    def install_snap(self, name, options):
        self.check_output(['sudo', 'snap', 'install', name, *options])

    def remove_snap(self, name, options):
        self.check_output(['sudo', 'snap', 'remove', name, *options])

    def snap_connect(self, snap_name, plug_name):
        self.check_output(['sudo', 'snap', 'connect',
                          f'{snap_name}:{plug_name}'])

    def install_microstack(self, *, channel='edge', path=None):
        """Install MicroStack at this host and connect relevant plugs.
        """
        if path is not None:
            self.install_snap(path, ['--devmode'])
        else:
            self.install_snap('microstack', [f'--{channel}', '--devmode'])

        # TODO: add microstack-support once it is merged into snapd.
        plugs = [
                'libvirt', 'netlink-audit',
                'firewall-control', 'hardware-observe',
                'kernel-module-observe', 'kvm',
                'log-observe', 'mount-observe',
                'netlink-connector', 'network-observe',
                'openvswitch-support', 'process-control',
                'system-observe', 'network-control',
                'system-trace', 'block-devices',
                'raw-usb'
        ]
        for plug in plugs:
            self.snap_connect('microstack', plug)

    def init_microstack(self, args=['--auto']):
        self.check_call(['sudo', 'microstack', 'init', *args])

    def setup_tempest_verifier(self):
        self.check_call(['sudo', 'snap', 'install', 'microstack-test'])
        self.check_call(['sudo', 'mkdir', '-p',
                        '/tmp/snap.microstack-test/tmp'])
        self.check_call(['sudo', 'cp',
                         '/var/snap/microstack/common/etc/microstack.json',
                         '/tmp/snap.microstack-test/tmp/microstack.json'])
        self.check_call(['microstack-test.rally', 'db', 'recreate'])
        self.check_call([
            'microstack-test.rally', 'deployment', 'create',
            '--filename', '/tmp/microstack.json',
            '--name', 'snap_generated'])
        self.check_call(['microstack-test.tempest-init'])

    def run_verifications(self):
        """Run a set of verification tests on MicroStack from this host."""
        self.check_call([
            'microstack-test.rally', 'verify', 'start',
            '--load-list',
            '/snap/microstack-test/current/2020.06-test-list.txt',
            '--detailed', '--concurrency', '2'])
        self.check_call([
            'microstack-test.rally', 'verify', 'report',
            '--type', 'json', '--to',
            '/tmp/verification-report.json'])
        report = json.loads(self.check_output([
            'sudo', 'cat',
            '/tmp/snap.microstack-test/tmp/verification-report.json']))
        # Make sure there are no verification failures in the report.
        failures = list(report['verifications'].values())[0]['failures']
        return failures


class LocalTestHost(TestHost):

    def __init__(self):
        super().__init__()
        self.install_snap('multipass', ['--stable'])
        self.install_snap('lxd', ['--stable'])
        self.check_call(['sudo', 'lxd', 'init', '--auto'])

        try:
            self.run(['sudo', 'lxc', 'profile', 'show', 'microstack'],
                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                     check=True)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.decode('utf-8')
            if 'No such object' in stderr:
                self._create_microstack_profile()
                return
            else:
                raise RuntimeError(
                    'An unexpected exception has occurred '
                    f'while trying to query the profile, stderr: {stderr}'
                ) from e
        self.run(['sudo', 'lxc', 'profile', 'delete', 'microstack'],
                 check=True)
        self._create_microstack_profile()

    def _create_microstack_profile(self):
        self.run(['sudo', 'lxc', 'profile', 'create', 'microstack'],
                 stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE,
                 check=True)
        profile_conf = {
            'config': {'linux.kernel_modules':
                       'iptable_nat, ip6table_nat, ebtables, openvswitch,'
                       'tap, vhost, vhost_net, vhost_scsi, vhost_vsock',
                       'security.nesting': 'true',
                       'limits.kernel.memlock': 'unlimited'
                       },
            'devices':
            {
                'tun': {'path': '/dev/net/tun', 'type': 'unix-char'},
                'vhost-net': {'path': '/dev/vhost-net', 'type': 'unix-char'},
                'vhost-scsi': {'path': '/dev/vhost-scsi', 'type': 'unix-char'},
                'vhost-vsock': {'path': '/dev/vhost-vsock',
                                'type': 'unix-char'}
            }
        }
        self.run(['sudo', 'lxc', 'profile', 'edit', 'microstack'],
                 stdout=subprocess.PIPE,
                 stderr=subprocess.PIPE,
                 check=True,
                 input=yaml.dump(profile_conf).encode('utf-8'))

    def destroy(self):
        self.remove_snap('microstack', ['--purge'])

    def check_output(self, args, **kwargs):
        return subprocess.check_output(args, **kwargs).strip()

    def call(self, args, **kwargs):
        return subprocess.call(args, **kwargs)

    def check_call(self, args, **kwargs):
        subprocess.check_call(args, **kwargs)

    def run(self, args, **kwargs):
        subprocess.run(args, **kwargs)


class MultipassTestHost(TestHost):
    """A virtual host set up via Multipass on a local machine."""

    def __init__(self, distribution):
        self.distribution = distribution
        self.name = petname.generate()
        self._launch()

    def check_output(self, args, **kwargs):
        prefix = ['sudo', 'multipass', 'exec', self.name, '--']
        cmd = []
        cmd.extend(prefix)
        cmd.extend(args)
        return subprocess.check_output(cmd, **kwargs).strip()

    def call(self, args, **kwargs):
        prefix = ['sudo', 'multipass', 'exec', self.name, '--']
        cmd = []
        cmd.extend(prefix)
        cmd.extend(args)
        return subprocess.call(cmd, **kwargs)

    def check_call(self, args, **kwargs):
        prefix = ['sudo', 'multipass', 'exec', self.name, '--']
        cmd = []
        cmd.extend(prefix)
        cmd.extend(args)
        subprocess.check_call(cmd, **kwargs)

    def run(self, args, **kwargs):
        prefix = ['sudo', 'multipass', 'exec', self.name, '--']
        cmd = []
        cmd.extend(prefix)
        cmd.extend(args)
        subprocess.run(cmd, **kwargs)

    def _launch(self):
        # Possible upstream CI resource allocation is documented here:
        # https://docs.opendev.org/opendev/infra-manual/latest/testing.html
        # >= 8GiB of RAM
        # 40-80 GB of storage (possibly under /opt)
        # Swap is not guaranteed.
        # With m1.tiny flavor the compute node needs slightly less than 3G of
        # RAM and 2.5G of disk space.
        subprocess.check_call(['sudo', 'sync'])
        subprocess.check_call(['sudo', 'sh', '-c',
                               'echo 3 > /proc/sys/vm/drop_caches'])
        subprocess.check_call(['sudo', 'multipass', 'launch', '--cpus', '2',
                               '--mem', '3G', '--disk', '4G',
                               self.distribution, '--name', self.name])

        info = json.loads(subprocess.check_output(
            ['sudo', 'multipass', 'info', self.name,
             '--format', 'json']))
        self.address = info['info'][self.name]['ipv4'][0]

    def copy_to(self, source_path, target_path=''):
        """Copy a file from the local machine to the Multipass VM.
        """
        subprocess.check_call(['sudo', 'multipass', 'copy-files', source_path,
                               f'{self.name}:{target_path}'])

    def copy_from(self, source_path, target_path):
        """Copy a file from the Multipass VM to the local machine.
        """
        subprocess.check_call(['sudo', 'multipass', 'copy-files',
                               f'{self.name}:{source_path}',
                               target_path])

    def destroy(self):
        subprocess.check_call(['sudo', 'multipass', 'delete', self.name])


class LXDTestHost(TestHost):
    """A container test host set up via LXD on a local machine."""

    def __init__(self, distribution):
        self.distribution = distribution
        self.name = petname.generate()
        self._launch()

    def check_output(self, args, **kwargs):
        prefix = ['sudo', 'lxc', 'exec', self.name, '--']
        cmd = []
        cmd.extend(prefix)
        cmd.extend(args)
        return subprocess.check_output(cmd, **kwargs).strip()

    def call(self, args, **kwargs):
        prefix = ['sudo', 'lxc', 'exec', self.name, '--']
        cmd = []
        cmd.extend(prefix)
        cmd.extend(args)
        return subprocess.call(cmd, **kwargs)

    def check_call(self, args, **kwargs):
        prefix = ['sudo', 'lxc', 'exec', self.name, '--']
        cmd = []
        cmd.extend(prefix)
        cmd.extend(args)
        subprocess.check_call(cmd, **kwargs)

    def run(self, args, **kwargs):
        prefix = ['sudo', 'lxc', 'exec', self.name, '--']
        cmd = []
        cmd.extend(prefix)
        cmd.extend(args)
        subprocess.check_call(cmd, **kwargs)

    def _launch(self):
        subprocess.check_call(['sudo', 'lxc', 'launch',
                               f'ubuntu:{self.distribution}', self.name,
                               '--profile', 'default',
                               '--profile', 'microstack'])

        @tenacity.retry(wait=tenacity.wait_fixed(3))
        def fetch_addr_info():
            info = json.loads(subprocess.check_output(
                ['sudo', 'lxc', 'query', f'/1.0/instances/{self.name}/state']))
            addrs = info['network']['eth0']['addresses']
            addr_info = next(filter(lambda a: a['family'] == 'inet', addrs),
                             None)
            if addr_info is None:
                raise RuntimeError('The container interface does'
                                   ' not have an IPv4 address which'
                                   ' is unexpected')
            return addr_info
        self.address = fetch_addr_info()['address']

    def copy_to(self, source_path, target_path=''):
        """Copy file or directory to the container.
        """
        subprocess.check_call(['sudo', 'lxc', 'file', 'push', source_path,
                               f'{self.name}/{target_path}',
                               '--recursive', '--create-dirs'])

    def copy_from(self, source_path, target_path):
        """Copy file or directory from the container.
        """
        subprocess.check_call(['sudo', 'lxc', 'file', 'pull'
                               f'{self.name}/{source_path}', target_path,
                               '--recursive', '--create-dirs'])

    def destroy(self):
        subprocess.check_call(['sudo', 'lxc', 'delete', self.name, '--force'])


class Framework(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._test_hosts = []

    def setUp(self):
        self._localhost = LocalTestHost()

    def tearDown(self):
        for host in self._test_hosts:
            host.destroy()

    @property
    def localhost(self):
        return self._localhost

    def add_multipass_host(self, distribution):
        new_test_host = MultipassTestHost(distribution)
        self._test_hosts.append(new_test_host)
        return new_test_host

    def add_lxd_host(self, distribution):
        new_test_host = LXDTestHost(distribution)
        self._test_hosts.append(new_test_host)
        return new_test_host

    def verify_instance_networking(self, test_host, instance_name):
        """Verify that we have networking on an instance

        We should be able to ping the instance.

        And we should be able to reach the Internet.

        :param :class:`TestHost` test_host: The host to run the test from.
        :param str instance_name: The name of the Nova instance to connect to.
        """
        logger.debug("Testing ping ...")
        ip = None
        servers = test_host.check_output([
            '/snap/bin/microstack.openstack',
            'server', 'list', '--format', 'json'
        ])
        servers = json.loads(servers)
        for server in servers:
            if server['Name'] == instance_name:
                ip = server['Networks'].split(",")[1].strip()
                break

        self.assertTrue(ip)

        test_host.call(['ping', '-i1', '-c10', '-w11', ip])

    @gui_wrapper
    def verify_gui(self, test_host):
        """Verify Horizon Dashboard operation by logging in."""
        control_ip = test_host.check_output([
            'sudo', 'snap', 'get', 'microstack', 'config.network.control-ip',
        ]).decode('utf-8')
        logger.debug('Verifying GUI for (IP: {})'.format(control_ip))
        dashboard_port = test_host.check_output([
            'sudo', 'snap', 'get',
            'microstack',
            'config.network.ports.dashboard']).decode('utf-8')
        keystone_password = test_host.check_output([
            'sudo', 'snap', 'get',
            'microstack',
            'config.credentials.keystone-password'
        ]).decode('utf-8')
        self.driver.get(f'http://{control_ip}:{dashboard_port}/')
        # Login to horizon!
        self.driver.find_element(By.ID, "id_username").click()
        self.driver.find_element(By.ID, "id_username").send_keys("admin")
        self.driver.find_element(By.ID, "id_password").send_keys(
            keystone_password)
        self.driver.find_element(By.CSS_SELECTOR, "#loginBtn > span").click()
        # Verify that we can click something on the dashboard -- e.g.,
        # we're still not sitting at the login screen.
        self.driver.find_element(By.LINK_TEXT, "Images").click()
