#
# Copyright 2012 New Dream Network, LLC (DreamHost)
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
"""Storage backend management
"""

from oslo_config import cfg
from oslo_log import log
import six.moves.urllib.parse as urlparse
from stevedore import driver
import tenacity


LOG = log.getLogger(__name__)


OPTS = [
    cfg.IntOpt('event_time_to_live',
               default=-1,
               help=("Number of seconds that events are kept "
                     "in the database for (<= 0 means forever).")),
    cfg.StrOpt('event_connection',
               secret=True,
               help='The connection string used to connect to the event '
               'database. (if unset, connection is used)'),
]


class StorageUnknownWriteError(Exception):
    """Error raised when an unknown error occurs while recording."""


class StorageBadVersion(Exception):
    """Error raised when the storage backend version is not good enough."""


class StorageBadAggregate(Exception):
    """Error raised when an aggregate is unacceptable to storage backend."""
    code = 400


class InvalidMarker(Exception):
    """Invalid pagination marker parameters"""


def get_connection_from_config(conf):
    retries = conf.database.max_retries

    @tenacity.retry(
        wait=tenacity.wait_fixed(conf.database.retry_interval),
        stop=(tenacity.stop_after_attempt(retries) if retries >= 0
              else tenacity.stop_never)
    )
    def _inner():
        url = (getattr(conf.database, 'event_connection') or
               conf.database.connection)
        return get_connection(url, conf)

    return _inner()


def get_connection(url, conf):
    """Return an open connection to the database."""
    connection_scheme = urlparse.urlparse(url).scheme
    # SqlAlchemy connections specify may specify a 'dialect' or
    # 'dialect+driver'. Handle the case where driver is specified.
    engine_name = connection_scheme.split('+')[0]
    # NOTE: translation not applied bug #1446983
    LOG.debug('looking for %(name)r driver in panko.event.storage',
              {'name': engine_name})
    mgr = driver.DriverManager('panko.event.storage', engine_name)
    return mgr.driver(url, conf)
