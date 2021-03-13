#!/usr/bin/env python3

import sys
import uuid
import secrets
import argparse

from datetime import datetime
from datetime import timezone
from dateutil.relativedelta import relativedelta

from oslo_serialization import (
    base64,
    msgpackutils
)

from cluster.shell import config_get

from keystoneauth1.identity import v3
from keystoneauth1 import session
from keystoneclient.v3 import client


VALIDITY_PERIOD = relativedelta(minutes=20)


def _create_credential():
    project_name = 'service'
    domain_name = 'default'
    # TODO: add support for TLS-terminated Keystone once this is supported.
    auth = v3.password.Password(
        auth_url="http://localhost:5000/v3",
        username='nova',
        password=config_get('config.credentials.nova-password'),
        user_domain_name=domain_name,
        project_domain_name=domain_name,
        project_name=project_name
    )
    sess = session.Session(auth=auth)
    keystone_client = client.Client(session=sess)

    # Only allow this credential to list the Keystone catalog. After it
    # expires, Keystone will return Unauthorized for requests made with tokens
    # issued from that credential.
    access_rules = [{
        'method': 'GET',
        'path': '/v3/auth/catalog',
        'service': 'identity'
    }]
    # TODO: make the expiration time customizable since this may be used by
    # automation or during live demonstrations where the lag between issuance
    # and usage may be more than the expiration time.
    # NOTE(wolsen): LP#1903208 expiration stamps passed to keystone without
    # timezone information are assumed to be UTC. Explicitly use UTC to get
    # an expiration at the right time.
    expires_at = datetime.now(tz=timezone.utc) + VALIDITY_PERIOD

    # Role objects themselves are not tied to a specific domain by default
    # - this does not affect role assignments themselves which are scoped.
    reader_role = keystone_client.roles.find(name='reader', domain_id=None)

    return keystone_client.application_credentials.create(
        name=f'cluster-join-{uuid.uuid4().hex}',
        expires_at=expires_at,
        access_rules=access_rules,
        # Do not allow this app credential to create new app credentials.
        unrestricted=False,
        roles=[reader_role.id],
        # Make the secret shorter than the default but secure enough.
        secret=secrets.token_urlsafe(32)[:32]
    )


def add_compute():
    """Generates connection string for adding a compute node to the cluster.

    Steps:
    * Make sure we are running in the clustered mode and this is a control
      node which is an initial node in the cluster;
    * Generate an application credential via Keystone scoped to the service
      project with restricted capabilities (reader role and only able to list
      the service catalog) and a short expiration time enough for a user to
      copy the connection string to the compute node;
    * Get an FQDN that will be used by the client to establish a connection to
      the clustering service;
    * Serialize the above data into a base64-encoded string.
    """

    role = config_get('config.cluster.role')
    if role != 'control':
        raise Exception('Running add-compute is only supported on a'
                        ' control node.')
    app_cred = _create_credential()
    data = {
        # TODO: we do not use hostname verification, however, using
        # an FQDN might be useful here since the host may be behind NAT
        # with a split-horizon DNS implemented where a hostname would point
        # us to a different IP.
        'hostname': config_get('config.network.control-ip'),
        # Store bytes since the representation will be shorter than with hex.
        'fingerprint': bytes.fromhex(config_get('config.cluster.fingerprint')),
        'id': app_cred.id,
        'secret': app_cred.secret,
    }
    connection_string = base64.encode_as_text(msgpackutils.dumps(data))

    # Print the connection string and an expiration notice to the user.
    print('Use the following connection string to add a new compute node'
          f' to the cluster (valid for {VALIDITY_PERIOD.minutes} minutes from'
          f' this moment):', file=sys.stderr)
    print(connection_string)


def main():
    parser = argparse.ArgumentParser(
            description='add-compute',
            usage='''add-compute

This command does not have subcommands - just run it to get a connection string
to be used when joining a node to the cluster.
''')
    parser.parse_args()

    add_compute()


if __name__ == '__main__':
    main()
