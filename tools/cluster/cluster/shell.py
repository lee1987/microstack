import os
import pymysql
import subprocess
import json


def sql(cmd) -> None:
    """Execute some SQL!

    Really simply wrapper around a pymysql connection, suitable for
    passing the limited CREATE and GRANT commands that we need to pass
    here.

    :param cmd: sql to execute.

    # TODO: move this into a shared shell library.

    """
    mysql_conf = '${SNAP_USER_COMMON}/etc/mysql/my.cnf'.format(**os.environ)
    root_pasword = config_get('config.credentials.mysql-root-password')
    connection = pymysql.connect(host='localhost', user='root',
                                 password=root_pasword,
                                 read_default_file=mysql_conf)

    with connection.cursor() as cursor:
        cursor.execute(cmd)


def check_output(*args):
    """Execute a shell command, returning the output of the command."""
    return subprocess.check_output(args, env=os.environ,
                                   universal_newlines=True).strip()


def check(*args):
    """Execute a shell command, raising an error on failed excution.

    :param args: strings to be composed into the bash call.

    """
    return subprocess.check_call(args, env=os.environ)


def config_get(*keys):
    """Get snap config keys via snapctl.

    :param keys list[str]: Keys to retrieve from the snap configuration.
    """
    return json.loads(check_output('snapctl', 'get', '-t', *keys))


def config_set(**kwargs):
    """Get snap config keys via snapctl.

    :param kwargs dict[str, str]: Values to set in the snap configuration.
    """
    check_output('snapctl', 'set', *[f'{k}={v}' for k, v in kwargs.items()])
