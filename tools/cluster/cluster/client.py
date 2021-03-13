#!/usr/bin/env python3

import sys
import urllib3
import json

from cluster import shell

CLUSTER_SERVICE_PORT = 10002


class UnauthorizedRequestError(Exception):
    pass


def join():
    """Join an existing cluster as a compute node."""

    cluster_config = shell.config_get('config.cluster')
    control_hostname = cluster_config['hostname']
    fingerprint = cluster_config['fingerprint']
    credential_id = cluster_config['credential-id']
    credential_secret = cluster_config['credential-secret']

    request_body = json.dumps({
        'credential-id': credential_id,
        'credential-secret': credential_secret
    })

    # Create a connection pool and override the TLS certificate
    # verification method to use the certificate fingerprint instead
    # of hostname validation + validation via CA cert and expiration time.
    # This avoids relying on any kind of PKI and DNS assumptions in the
    # installation environment.
    # If the fingerprint does not match, MaxRetryError will be raised
    # with SSLError as a cause even with the rest of the checks disabled.
    conn_pool = urllib3.HTTPSConnectionPool(
        control_hostname, CLUSTER_SERVICE_PORT,
        assert_fingerprint=fingerprint, assert_hostname=False,
        cert_reqs='CERT_NONE',
    )

    try:
        resp = conn_pool.urlopen(
            'POST', '/join', retries=0, preload_content=True,
            headers={
                'API-VERSION': '1.0.0',
                'Content-Type': 'application/json',
            }, body=request_body)
    except urllib3.exceptions.MaxRetryError as e:
        if isinstance(e.reason, urllib3.exceptions.SSLError):
            raise Exception(
                'The actual clustering service certificate fingerprint'
                ' did not match the expected one, please make sure that: '
                '(1) that a correct token was specified during initialization;'
                ' (2) a MITM attacks are not performed against HTTPS requests'
                ' (including transparent proxies).'
            ) from e.reason
        raise Exception('Could not retrieve a response from the clustering'
                        ' service.') from e

    if resp.status == 401:
        response_data = resp.data.decode('utf-8')
        # TODO: this should be more bulletproof in case a proxy server
        # returns this response - it will not have the expected format.
        print('An authorization failure has occurred while joining the'
              ' the cluster: please make sure the connection string'
              ' was entered as returned by the "add-compute" command'
              ' and that it was used before its expiration time.',
              file=sys.stderr)
        if response_data:
            message = json.loads(response_data)['message']
            raise UnauthorizedRequestError(message)
        raise UnauthorizedRequestError()
    if resp.status != 200:
        raise Exception('Unexpected response status received from the'
                        f' clustering service: {resp.status}')

    try:
        response_data = resp.data.decode('utf-8')
    except UnicodeDecodeError:
        raise Exception('The response from the clustering service contains'
                        ' bytes invalid for UTF-8')
    if not response_data:
        raise Exception('The response from the clustering service is empty'
                        ' which is unexpected: please check its status'
                        ' and file an issue if the problem persists')

    # Load the response assuming it has the correct format. API versioning
    # should rule out inconsistencies, otherwise we will get an error here.
    response_dict = json.loads(response_data)
    credentials = response_dict['config']['credentials']
    control_creds = {f'config.credentials.{k}': v
                     for k, v in credentials.items()}
    shell.config_set(**control_creds)
    # TODO: use the hostname from the connection string instead to
    # resolve an IP address (requires a valid DNS setup).
    control_ip = response_dict['config']['network']['control-ip']
    shell.config_set(**{'config.network.control-ip': control_ip})


if __name__ == '__main__':
    join()
