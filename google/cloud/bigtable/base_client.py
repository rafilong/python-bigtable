# Copyright 2015 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Parent client for calling the Google Cloud Bigtable API.

This is the base from which all interactions with the API occur.

In the hierarchy of API concepts

* a :class:`~google.cloud.bigtable.client.Client` owns an
  :class:`~google.cloud.bigtable.instance.Instance`
* an :class:`~google.cloud.bigtable.instance.Instance` owns a
  :class:`~google.cloud.bigtable.table.Table`
* a :class:`~google.cloud.bigtable.table.Table` owns a
  :class:`~.column_family.ColumnFamily`
* a :class:`~google.cloud.bigtable.table.Table` owns a
  :class:`~google.cloud.bigtable.row.Row` (and all the cells in the row)
"""
import os
import warnings
import grpc

from google.api_core.gapic_v1 import client_info

from google.cloud import bigtable_v2
from google.cloud import bigtable_admin_v2

from google.cloud.bigtable import __version__

from google.cloud.client import ClientWithProject

from google.cloud.bigtable_admin_v2 import enums
from google.cloud.environment_vars import BIGTABLE_EMULATOR


INSTANCE_TYPE_PRODUCTION = enums.Instance.Type.PRODUCTION
INSTANCE_TYPE_DEVELOPMENT = enums.Instance.Type.DEVELOPMENT
INSTANCE_TYPE_UNSPECIFIED = enums.Instance.Type.TYPE_UNSPECIFIED
_CLIENT_INFO = client_info.ClientInfo(client_library_version=__version__)
SPANNER_ADMIN_SCOPE = "https://www.googleapis.com/auth/spanner.admin"
ADMIN_SCOPE = "https://www.googleapis.com/auth/bigtable.admin"
"""Scope for interacting with the Cluster Admin and Table Admin APIs."""
DATA_SCOPE = "https://www.googleapis.com/auth/bigtable.data"
"""Scope for reading and writing table data."""
READ_ONLY_SCOPE = "https://www.googleapis.com/auth/bigtable.data.readonly"
"""Scope for reading table data."""


def _create_gapic_client(client_class, client_options=None):
    def inner(self):
        if self._emulator_host is None:
            return client_class(
                credentials=self._credentials,
                client_info=self._client_info,
                client_options=client_options,
            )
        else:
            return client_class(
                channel=self._emulator_channel, client_info=self._client_info
            )

    return inner


class BaseClient(ClientWithProject):
    """Client for interacting with Google Cloud Bigtable API.

    .. note::

        Since the Cloud Bigtable API requires the gRPC transport, no
        ``_http`` argument is accepted by this class.

    :type project: :class:`str` or :func:`unicode <unicode>`
    :param project: (Optional) The ID of the project which owns the
                    instances, tables and data. If not provided, will
                    attempt to determine from the environment.

    :type credentials: :class:`~google.auth.credentials.Credentials`
    :param credentials: (Optional) The OAuth2 Credentials to use for this
                        client. If not passed, falls back to the default
                        inferred from the environment.

    :type read_only: bool
    :param read_only: (Optional) Boolean indicating if the data scope should be
                      for reading only (or for writing as well). Defaults to
                      :data:`False`.

    :type admin: bool
    :param admin: (Optional) Boolean indicating if the client will be used to
                  interact with the Instance Admin or Table Admin APIs. This
                  requires the :const:`ADMIN_SCOPE`. Defaults to :data:`False`.

    :type: client_info: :class:`google.api_core.gapic_v1.client_info.ClientInfo`
    :param client_info:
        The client info used to send a user-agent string along with API
        requests. If ``None``, then default info will be used. Generally,
        you only need to set this if you're developing your own library
        or partner tool.

    :type client_options: :class:`~google.api_core.client_options.ClientOptions`
        or :class:`dict`
    :param client_options: (Optional) Client options used to set user options
        on the client. API Endpoint should be set through client_options.

    :type admin_client_options:
        :class:`~google.api_core.client_options.ClientOptions` or :class:`dict`
    :param admin_client_options: (Optional) Client options used to set user
        options on the client. API Endpoint for admin operations should be set
        through admin_client_options.

    :type channel: :instance: grpc.Channel
    :param channel (grpc.Channel): (Optional) DEPRECATED:
            A ``Channel`` instance through which to make calls.
            This argument is mutually exclusive with ``credentials``;
            providing both will raise an exception. No longer used.

    :raises: :class:`ValueError <exceptions.ValueError>` if both ``read_only``
             and ``admin`` are :data:`True`
    """

    _table_data_client = None
    _table_admin_client = None
    _instance_admin_client = None

    def __init__(
        self,
        project=None,
        credentials=None,
        read_only=False,
        admin=False,
        client_info=_CLIENT_INFO,
        client_options=None,
        admin_client_options=None,
        channel=None,
    ):
        if read_only and admin:
            raise ValueError(
                "A read-only client cannot also perform" "administrative actions."
            )

        # NOTE: We set the scopes **before** calling the parent constructor.
        #       It **may** use those scopes in ``with_scopes_if_required``.
        self._read_only = bool(read_only)
        self._admin = bool(admin)
        self._client_info = client_info
        self._emulator_host = os.getenv(BIGTABLE_EMULATOR)
        self._emulator_channel = None

        if self._emulator_host is not None:
            self._emulator_channel = grpc.insecure_channel(self._emulator_host)

        if channel is not None:
            warnings.warn(
                "'channel' is deprecated and no longer used.",
                DeprecationWarning,
                stacklevel=2,
            )

        self._client_options = client_options
        self._admin_client_options = admin_client_options
        self._channel = channel
        self.SCOPE = self._get_scopes()
        super(BaseClient, self).__init__(project=project, credentials=credentials)

    def _get_scopes(self):
        """Get the scopes corresponding to admin / read-only state.

        Returns:
            Tuple[str, ...]: The tuple of scopes.
        """
        if self._read_only:
            scopes = (READ_ONLY_SCOPE,)
        else:
            scopes = (DATA_SCOPE,)

        if self._admin:
            scopes += (ADMIN_SCOPE,)

        return scopes

    @property
    def project_path(self):
        """Project name to be used with Instance Admin API.

        .. note::

            This property will not change if ``project`` does not, but the
            return value is not cached.

        For example:

        .. literalinclude:: snippets.py
            :start-after: [START bigtable_project_path]
            :end-before: [END bigtable_project_path]

        The project name is of the form

            ``"projects/{project}"``

        :rtype: str
        :returns: Return a fully-qualified project string.
        """
        return self.instance_admin_client.project_path(self.project)

    @property
    def table_data_client(self):
        """Getter for the gRPC stub used for the Table Admin API.

        For example:

        .. literalinclude:: snippets.py
            :start-after: [START bigtable_table_data_client]
            :end-before: [END bigtable_table_data_client]

        :rtype: :class:`.bigtable_v2.BigtableClient`
        :returns: A BigtableClient object.
        """
        if self._table_data_client is None:
            klass = _create_gapic_client(
                bigtable_v2.BigtableClient, client_options=self._client_options
            )
            self._table_data_client = klass(self)
        return self._table_data_client

    @property
    def table_admin_client(self):
        """Getter for the gRPC stub used for the Table Admin API.

        For example:

        .. literalinclude:: snippets.py
            :start-after: [START bigtable_table_admin_client]
            :end-before: [END bigtable_table_admin_client]

        :rtype: :class:`.bigtable_admin_pb2.BigtableTableAdmin`
        :returns: A BigtableTableAdmin instance.
        :raises: :class:`ValueError <exceptions.ValueError>` if the current
                 client is not an admin client or if it has not been
                 :meth:`start`-ed.
        """
        if self._table_admin_client is None:
            if not self._admin:
                raise ValueError("Client is not an admin client.")
            klass = _create_gapic_client(
                bigtable_admin_v2.BigtableTableAdminClient,
                client_options=self._admin_client_options,
            )
            self._table_admin_client = klass(self)
        return self._table_admin_client

    @property
    def instance_admin_client(self):
        """Getter for the gRPC stub used for the Table Admin API.

        For example:

        .. literalinclude:: snippets.py
            :start-after: [START bigtable_instance_admin_client]
            :end-before: [END bigtable_instance_admin_client]

        :rtype: :class:`.bigtable_admin_pb2.BigtableInstanceAdmin`
        :returns: A BigtableInstanceAdmin instance.
        :raises: :class:`ValueError <exceptions.ValueError>` if the current
                 client is not an admin client or if it has not been
                 :meth:`start`-ed.
        """
        if self._instance_admin_client is None:
            if not self._admin:
                raise ValueError("Client is not an admin client.")
            klass = _create_gapic_client(
                bigtable_admin_v2.BigtableInstanceAdminClient,
                client_options=self._admin_client_options,
            )
            self._instance_admin_client = klass(self)
        return self._instance_admin_client

    def instance(self, instance_id, display_name=None, instance_type=None, labels=None):
        raise NotImplementedError

    def list_instances(self):
        raise NotImplementedError

    def list_clusters(self):
        raise NotImplementedError