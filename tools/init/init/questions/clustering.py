import logging
import msgpack
import re
import netaddr
import sys

from cryptography.hazmat.primitives import hashes
from typing import Tuple

from init.questions.question import Question, InvalidAnswer
from init.shell import (
    default_source_address,
    config_get,
    config_set,
)


from oslo_serialization import (
    base64,
    msgpackutils
)

logger = logging.getLogger(__name__)


class Role(Question):
    _type = 'string'
    config_key = 'config.cluster.role'
    _question = ('Which role would you like to use for this node:'
                 ' "control" or "compute"?')
    _valid_roles = ('control', 'compute')
    interactive = True

    def _input_func(self, prompt):
        if not self.interactive:
            return

        for _ in range(0, 3):
            role = input("{} > ".format(self._question))
            if role in self._valid_roles:
                return role

            print('The role must be either "control" or "compute".',
                  file=sys.stderr)

        raise InvalidAnswer('Too many failed attempts.')


class ConnectionString(Question):
    _type = 'string'
    config_key = 'config.cluster.connection-string.raw'
    _question = ('Please enter a connection string returned by the'
                 ' add-compute command > ')
    interactive = True

    def _validate(self, answer: str) -> Tuple[str, bool]:
        try:
            conn_str_bytes = base64.decode_as_bytes(
                answer.encode('ascii'))
        except TypeError:
            print('The connection string contains non-ASCII'
                  ' characters please make sure you entered'
                  ' it as returned by the add-compute command.',
                  file=sys.stderr)
            return answer, False

        try:
            conn_info = msgpackutils.loads(conn_str_bytes)
        except msgpack.exceptions.ExtraData:
            print('The connection string contains extra data'
                  ' characters please make sure you entered'
                  ' it as returned by the add-compute command.',
                  file=sys.stderr)
            return answer, False
        except ValueError:
            print('The connection string contains extra data'
                  ' characters please make sure you entered'
                  ' it as returned by the add-compute command.',
                  file=sys.stderr)
            return answer, False
        except msgpack.exceptions.FormatError:
            print('The connection string format is invalid'
                  ' please make sure you entered'
                  ' it as returned by the add-compute command.',
                  file=sys.stderr)
            return answer, False
        except Exception:
            print('An unexpeted error has occured while trying'
                  ' to decode the connection string. Please'
                  ' make sure you entered it as returned by'
                  ' the add-compute command and raise an'
                  ' issue if the error persists',
                  file=sys.stderr)
            return answer, False

        # Perform token field validation as well so that the rest of
        # the code-base can assume valid input.
        # The input can be either an IPv4 or IPv6 address or a hostname.
        hostname = conn_info.get('hostname')
        try:
            is_valid_address = self._validate_address(hostname)
            is_valid_address = True
        except ValueError:
            logger.debug('The hostname specified in the connection string is'
                         ' not an IPv4 or IPv6 address - treating it as'
                         ' a hostname.')
            is_valid_address = False
        if not is_valid_address:
            try:
                self._validate_hostname(hostname)
            except ValueError as e:
                print(f'The hostname {hostname} provided in the connection'
                      f' string is invalid: {str(e)}', file=sys.stderr)
                return answer, False

        fingerprint = conn_info.get('fingerprint')
        try:
            self._validate_fingerprint(fingerprint)
        except ValueError as e:
            print('The clustering service TLS certificate fingerprint provided'
                  f' in the connection string is invalid: {str(e)}',
                  file=sys.stderr)
            return answer, False

        credential_id = conn_info.get('id')
        try:
            self._validate_credential_id(credential_id)
        except ValueError as e:
            print('The credential id provided in the connection string is'
                  f' invalid: {str(e)}', file=sys.stderr)
            return answer, False

        credential_secret = conn_info.get('secret')
        try:
            self._validate_credential_secret(credential_secret)
        except ValueError as e:
            print('The credential secret provided in the connection string is'
                  f' invalid: {str(e)}', file=sys.stderr)
            return answer, False

        self._conn_info = conn_info
        return answer, True

    def _validate_hostname(self, hostname):
        if hostname is None:
            raise ValueError('A hostname has not been provided.')
        if len(hostname) == 0:
            raise ValueError('An empty hostname is invalid.')
        # Remove the trailing dot as it does not count to the following
        # length limit check.
        if hostname.endswith('.'):
            name = hostname[:-1]
        else:
            name = hostname
        # See https://tools.ietf.org/html/rfc1035#section-3.1
        # 255 - octet limit, 253 - visible hostname limit (without
        # a trailing dot. The limit is also documented in hostname(7).
        if len(name) > 253:
            raise ValueError('The specified hostname is too long.')

        allowed = re.compile('(?!-)[A-Z0-9-]{1,63}(?<!-)$', re.IGNORECASE)
        if not re.search('[a-zA-Z-]', name.split(".")[-1]):
            raise ValueError(f'{hostname} contains no non-numeric characters'
                             ' in the top-level domain part of the hostname.')
        if any((not allowed.match(x)) for x in name.split('.')):
            raise ValueError('{hostname} is an invalid hostname.')

    def _validate_address(self, address):
        if address is None:
            raise ValueError('An address has not been provided.')
        if not (netaddr.valid_ipv4(address, netaddr.core.INET_PTON) or
                netaddr.valid_ipv6(address, netaddr.core.INET_PTON)):
            raise ValueError(f'{address} is not a valid IPv4 or IPv6 address.')

    def _validate_fingerprint(self, fingerprint):
        # We expect a byte sequence equal to the SHA256 hash of the cert.
        actual_len = len(fingerprint)
        expected_len = hashes.SHA256.digest_size
        if not actual_len == expected_len:
            raise ValueError('The provided fingerprint has an invalid '
                             f'length: {actual_len}, expected: {expected_len}')

    def _validate_credential_id(self, credential_id):
        if credential_id is None:
            raise ValueError('A credential id has not been provided.')

        # We expect a UUID (rfc4122) without dashes.
        UUID_LEN = 32
        actual_len = len(credential_id)
        if actual_len != UUID_LEN:
            raise ValueError('The credential length is not equal to a length'
                             'of a UUID without dashes:'
                             f'actual: {actual_len}, expected: {UUID_LEN}')

    def _validate_credential_secret(self, credential_secret):
        if credential_secret is None:
            raise ValueError('A credential secret has not been provided.')

        # The artificial secret length controlled by the MicroStack code-base.
        # https://docs.python.org/3/library/secrets.html#how-many-bytes-should-tokens-use
        SECRET_LEN = 32
        actual_len = len(credential_secret)
        if actual_len != SECRET_LEN:
            raise ValueError('The credential secret has an unexpected length:'
                             f'actual: {actual_len}, expected: {SECRET_LEN}')

    def after(self, answer: str) -> None:
        # Store the individual parts of the connection string in the snap
        # config for easy access and avoidance of extra parsing.
        prefix = 'config.cluster'
        config_set(**{
            f'{prefix}.hostname': self._conn_info['hostname'],
            f'{prefix}.fingerprint': self._conn_info['fingerprint'].hex(),
            f'{prefix}.credential-id': self._conn_info['id'],
            f'{prefix}.credential-secret': self._conn_info['secret'],
        })

    def ask(self):
        # Skip this question for a control node since we are not connecting
        # to ourselves.
        role = config_get(Role.config_key)
        if role == 'control':
            return
        return super().ask()


class ControlIp(Question):
    _type = 'string'
    config_key = 'config.network.control-ip'
    _question = 'Please enter the ip address of the control node'
    interactive = True

    def _load(self):
        if config_get(Role.config_key) == 'control':
            return default_source_address() or super()._load()
        return super()._load()

    def ask(self):
        # Skip this question for a compute node since the control IP
        # address is taken from the connection string instead.
        role = config_get(Role.config_key)
        if role == 'compute':
            return
        return super().ask()


class ComputeIp(Question):
    _type = 'string'
    config_key = 'config.network.compute-ip'
    _question = 'Please enter the ip address of this node'
    interactive = True

    def _load(self):
        role = config_get(Role.config_key)
        if role == 'compute':
            return default_source_address() or super().load()

        return super()._load()

    def ask(self):
        # If we are a control node, skip this question.
        role = config_get(Role.config_key)
        if role == 'control':
            ip = config_get(ControlIp.config_key)
            config_set(**{self.config_key: ip})
            return

        return super().ask()
