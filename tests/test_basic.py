#!/usr/bin/env python
"""
basic_test.py

This is a basic test of microstack functionality. We verify that:

1) We can install the snap.
2) We can launch a cirros image.
3) Horizon is running, and we can hit the landing page.
4) We can login to Horizon successfully.

The Horizon testing bits were are based on code generated by the Selinum
Web IDE.

"""

import os
import sys
import unittest

sys.path.append(os.getcwd())

from tests.framework import Framework  # noqa E402


class TestBasics(Framework):

    def test_basics(self):
        """Basic test

        Install microstack, and verify that we can launch a machine and
        open the Horizon GUI.

        """
        self._localhost.install_microstack(path='microstack_ussuri_amd64.snap')
        self._localhost.init_microstack([
            '--auto',
            '--control',
            '--setup-loop-based-cinder-lvm-backend',
            '--loop-device-file-size=24'
            ])
        endpoints = self._localhost.check_output(
            ['/snap/bin/microstack.openstack', 'endpoint', 'list']
        ).decode('utf-8')

        control_ip = self._localhost.check_output(
            ['sudo', 'snap', 'get', 'microstack', 'config.network.control-ip'],
        ).decode('utf-8')

        # Endpoints should contain the control IP.
        self.assertTrue(control_ip in endpoints)

        # Endpoints should not contain localhost
        self.assertFalse("localhost" in endpoints)

        # We should be able to launch an instance
        instance_name = 'test-instance'
        print("Testing microstack.launch ...")
        self._localhost.check_output(
            ['/snap/bin/microstack.launch', 'cirros',
             '--name', instance_name, '--retry']
        )
        self.verify_instance_networking(self._localhost, instance_name)

        # The Horizon Dashboard should function
        self.verify_gui(self._localhost)

        # Verify that we can uninstall the snap cleanly, and that the
        # ovs bridge goes away.

        # Check to verify that our bridge is there.
        self.assertTrue(
            'br-ex' in self._localhost.check_output(
                ['ip', 'a']).decode('utf-8'))

        self._localhost.setup_tempest_verifier()
        # Make sure there are no verification failures in the report.
        failures = self._localhost.run_verifications()
        self.assertEqual(failures, 0, 'Verification tests had failure.')

        # Try to remove the snap without sudo.
        self.assertEqual(self._localhost.call([
            'snap', 'remove', '--purge', 'microstack']), 1)

        # Retry with sudo (should succeed).
        self._localhost.check_call(
            ['sudo', 'snap', 'remove', '--purge', 'microstack'])

        # Verify that MicroStack is gone.
        self.assertEqual(self._localhost.call(
            ['snap', 'list', 'microstack']), 1)

        # Verify that bridge is gone.
        self.assertFalse(
            'br-ex' in self._localhost.check_output(
                ['ip', 'a']).decode('utf-8'))

        # We made it to the end. Set passed to True!
        self.passed = True


if __name__ == '__main__':
    # Run our tests, ignoring deprecation warnings and warnings about
    # unclosed sockets. (TODO: setup a selenium server so that we can
    # move from PhantomJS, which is deprecated, to to Selenium headless.)
    unittest.main(warnings='ignore')
