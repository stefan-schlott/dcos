
"""
Download and unpack use example

from utils import *

url = "https://wintesting.s3.amazonaws.com/testing/packages/adminrouter/adminrouter--19c887e02f1a8325cabd980f039015b70ab19cee.tar.xz"
path = "./tmp/"
if is_downloadable(url):
  archive =  download(url, path)
else:
    print("{} \nis not downloadable!!!".format(url))

print("this is {}".format(archive))
unpack(archive, "./tmp/Arc/")

"""
import os
from pathlib import Path
from pprint import pprint as pp
import random
import subprocess
import tarfile
import time

from pySmartDL import SmartDL

from common import logger
from common import exceptions as cm_exc


LOG = logger.get_logger(__name__)


# TODO: Needs refactoring
def download(url, location):
    """
    Downloads from url to location
    uses  pySmartDL from https://pypi.org/project/pySmartDL/
    """
    _location = os.path.abspath(location)
    dl = SmartDL(url, _location)
    dl.start()
    path = os.path.abspath(dl.get_dest())
    # print("Downloaded to {} ".format(path), " from {}".format(url),sep='\n')
    return path

# TODO: Needs refactoring
def unpack(tarpath, location):
    """
    unpacks tar.xz to  location
    """

    _location = os.path.abspath(location)

    if  not os.path.exists(_location):
        print("no Directory exist creating...\n{}".format(_location))
        os.mkdir(_location)

    with tarfile.open(tarpath) as tar:
        tar.extractall(_location)
        print("extracted to {}".format(_location))
        pp({tarinfo.name:tarinfo.size for tarinfo in tar})
    return _location


def rmdir(path, recursive=False):
    """Remove a directory.

    :param path:      str, target directory path. It must be a direct directory
                      path. Symlinks won't be processed.
    :param recursive: bool, perform recursive removal, if True. Otherwise fail,
                      if a nested directory encountered.
    """
    path_ = Path(str(path))
    path_ = path_ if path_.is_absolute() else Path(Path('.').resolve(), path_)
    LOG.debug(f'rmdir(): Target path: {path_}')

    if path_.exists():
        if path_.is_symlink():
            raise OSError(f'Symlink conflict: {path_}')
        if path_.is_reserved():
            raise OSError(f'Reserved name conflict: {path_}')
        elif not path_.is_dir():
            raise OSError(f'Not a directory: {path_}')
        else:
            # Remove content of a directory
            for sub_path in path_.iterdir():
                if sub_path.is_dir():
                    if recursive is True:
                        rmdir(path_.joinpath(sub_path), recursive=True)
                    else:
                        raise RuntimeError(f'Nested directory: {sub_path}')
                else:
                    sub_path.unlink()
                    LOG.debug(f'rmdir(): Remove file: {sub_path}')
            # Remove a directory itself
            path_.rmdir()
            LOG.debug(f'rmdir(): Remove directory: {path_}')
    else:
        LOG.debug(f'rmdir(): Path not found: {path_}')


def run_external_command(cl_elements, timeout=30):
    """Run external command.

    :param cl_elements: str|list, string, representing a whole command line, or
                        list of individual elements of command line, beginning
                        with executable name
    :param timeout:     int|float, forcibly terminate execution, if this number
                        of seconds passed since execution was started
    :return:            subprocess.CompletedProcess, results of sub-process
                        execution
    """
    try:
        subproc_run = subprocess.run(
            cl_elements, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=timeout, check=True, universal_newlines=True
        )
    except subprocess.SubprocessError as e:
        raise cm_exc.ExternalCommandError(
            '{}: {}: Exit code[{}]: {}'.format(
                cl_elements, type(e).__name__, e.returncode,
                e.stderr.replace('\n', ' ')
            )
        )
    except (OSError, ValueError) as e:
        raise cm_exc.ExternalCommandError(
            f'{cl_elements}: {type(e).__name__}: {e}'
        )

    return subproc_run


def get_retry_interval(attempt, retry_interval_base, retry_interval_cap):
    """Calculate interval before the next retry of an operation put into
    retrying loop.

    :param attempt:             int, attempt number
    :param retry_interval_base: float, lower limit of the retry interval
    :param retry_interval_cap:  float, upper limit of the retry interval

    :return:                    float, retry interval in seconds
    """
    # Implementation of the 'Exponential Backoff' with 'Full Jitter'.
    # Ref: http://www.awsarchitectureblog.com/2015/03/backoff.html
    return random.uniform(
        retry_interval_base,
        min(retry_interval_cap, pow(2, attempt) * retry_interval_base)
    )


def retry_on_exc(exceptions=(Exception,), max_attempts=0,
                 retry_interval_base=0.5, retry_interval_cap=5.0):
    """Apply retrying logic to a function/method being decorated.
    """
    def decorator(func):
        """"""
        def call_proxy(*args, **kwargs):
            """"""
            exc_ = None
            result = None

            op_name = func.__name__

            for attempt in range(1, max_attempts + 1):
                try:
                    result = func(*args, **kwargs)
                except exceptions as e:
                    exc_ = e
                    retry_interval = get_retry_interval(
                        attempt, retry_interval_base, retry_interval_cap
                    )
                    LOG.debug(f'Retrying {op_name}: ERROR: attempt[{attempt}]'
                              f' cause[{type(e).__name__}: {e}]'
                              f' next_attempt_in[{retry_interval}]')
                    time.sleep(retry_interval)
                else:
                    LOG.debug(f'Retrying {op_name}: OK:'
                              f' attempts_spent[{attempt}]')
                    exc_ = None
                    break

            if exc_:
                LOG.error(f'Retrying {op_name}: FAILED:'
                          f' attempts_spent[{max_attempts}]')
                raise exc_
            else:
                return result

        return call_proxy

    return decorator

