#    (c) Copyright 2026 Hewlett Packard Enterprise Development LP
#    All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
"""Volume driver common utilities for HPE Alletra MP Storage array.

The drivers requires the use of the san_ip, san_login,
san_password settings for ssh connections into the Alletra MP
array. It also requires the setting of
hpe3par_api_url, hpe3par_username, hpe3par_password
for credentials to talk to the REST service on the Alletra MP
array.
"""

import ast
import json
import math
import pprint
import re
import uuid
import time

from oslo_config import cfg
from oslo_log import log as logging
from oslo_log import versionutils
from oslo_serialization import base64
from oslo_service import loopingcall
from oslo_utils import excutils
from oslo_utils.excutils import save_and_reraise_exception
from oslo_utils import units
import taskflow.engines
from taskflow.patterns import linear_flow

from cinder import context
from cinder import exception
from cinder import flow_utils
from cinder.i18n import _
from cinder import objects
from cinder.objects import fields
from cinder import utils
from cinder.volume import configuration
from cinder.volume import driver
from cinder.volume import qos_specs
from cinder.volume import volume_types
from cinder.volume import volume_utils

LOG = logging.getLogger(__name__)

import sys
sys.path.append("/opt/stack/cinder/cinder/volume/drivers/hpe")

try:
    from hpe_storage_flowkit_py.v1.src.core.session import SessionManager
    from hpe_storage_flowkit_py.v1.src.core.rest_client import RESTClient
    from hpe_storage_flowkit_py.v1.src.workflows.volume import VolumeWorkflow
    from hpe_storage_flowkit_py.v1.src.workflows.snapshot import SnapshotWorkflow
    from hpe_storage_flowkit_py.v1.src.workflows.system import SystemWorkflow
    from hpe_storage_flowkit_py.v1.src.workflows.cpg import CPGWorkflow
    from hpe_storage_flowkit_py.v1.src.workflows.task_manager import TaskManager
    from hpe_storage_flowkit_py.v1.src.workflows.remote_copy import RemoteCopyGroupWorkflow
    from hpe_storage_flowkit_py.v1.src.workflows.volumeset import VolumeSetWorkflow
    from hpe_storage_flowkit_py.v1.src.workflows.qos import QOSWorkflow
    from hpe_storage_flowkit_py.v1.src.workflows.host import HostWorkflow
    from hpe_storage_flowkit_py.v1.src.workflows.vlun import VLUNWorkflow
    from hpe_storage_flowkit_py.v1.src.core import exceptions as flowkit_exceptions
    from hpe_storage_flowkit_py.v1.src.utils import constants
except ImportError as ie:
    msg = "Unable to import flowkit modules: %s" % ie
    LOG.error(msg)
    raise exception.InvalidInput(reason=msg) from ie


hpe3par_opts = [
    cfg.StrOpt('hpe3par_api_url',
               default='',
               help="WSAPI Server URL. "
                    "This setting applies to: 3PAR, Primera, Alletra 9k and "
                    "Alletra MP"
                    "\n       Example 1: for 3PAR, URL is: "
                    "\n       https://<3par ip>:8080/api/v1 "
                    "\n       Example 2: for Primera/Alletra 9k/Alletra MP, "
                    "URL is: "
                    "\n       https://<primera ip>:443/api/v1"),
    cfg.StrOpt('hpe3par_username',
               default='',
               help="3PAR/Primera/Alletra 9k/Alletra MP username with the "
                    "'edit' role"),
    cfg.StrOpt('hpe3par_password',
               default='',
               help="3PAR/Primera/Alletra 9k/Alletra MP password for the "
                    "user specified in hpe3par_username",
               secret=True),
    cfg.ListOpt('hpe3par_cpg',
                default=["OpenStack"],
                help="List of the 3PAR/Primera/Alletra 9k/Alletra MP CPG(s) "
                     "to use for volume creation"),
    cfg.StrOpt('hpe3par_cpg_snap',
               default="",
               help="The 3PAR/Primera/Alletra 9k/Alletra MP CPG to use for "
                    "snapshots of volumes. If empty the userCPG will be used"),
    cfg.StrOpt('hpe3par_snapshot_retention',
               default="",
               help="The time in hours to retain a snapshot.  "
                    "You can't delete it before this expires."),
    cfg.StrOpt('hpe3par_snapshot_expiration',
               default="",
               help="The time in hours when a snapshot expires "
                    " and is deleted.  This must be larger than expiration"),
    cfg.BoolOpt('hpe3par_debug',
                default=False,
                help="Enable HTTP debugging to 3PAR/Primera/Alletra 9k/"
                     "Alletra MP"),
    cfg.ListOpt('hpe3par_iscsi_ips',
                default=[],
                help="List of target iSCSI addresses to use."),
    cfg.ListOpt('hpe3par_nvme_ips',
                default=[],
                help="List of target nvme addresses to use."),
    cfg.BoolOpt('hpe3par_iscsi_chap_enabled',
                default=False,
                help="Enable CHAP authentication for iSCSI connections."),
    cfg.StrOpt('hpe3par_target_nsp',
               default="",
               help="The nsp of 3PAR/Primera/Alletra 9k/Alletra MP backend to "
                    "be used when: (1) multipath is not enabled in cinder.conf"
                    ". (2) Fiber Channel Zone Manager is not used. "
                    "(3) the backend is prezoned with this "
                    "specific nsp only. For example if nsp is 2 1 2, the "
                    "format of the option's value is 2:1:2"),
]


CONF = cfg.CONF
CONF.register_opts(hpe3par_opts, group=configuration.SHARED_CONF_GROUP)

class InvalidDomain(exception.VolumeDriverException):
    message = _("Invalid Domain: %(err)s")


class CinderClient(SystemWorkflow,
                   CPGWorkflow,
                   VolumeWorkflow, 
                   SnapshotWorkflow, 
                   HostWorkflow, 
                   VLUNWorkflow, 
                   RemoteCopyGroupWorkflow, 
                   VolumeSetWorkflow, 
                   QOSWorkflow, 
                   TaskManager):
    """Class that contains common code for the 3PAR drivers.

    Version history:

    .. code-block:: none

        1.0 - Initial driver


    """

    VERSION = "1.0"

    stats = {}

    def __init__(self, config, active_backend_id=None):
        self.config = config
        self.client = None
        self.id = None
        self.uuid = uuid.uuid4()
        self._client_conf = {}
        self._replication_targets = []
        self._replication_enabled = False
        self._active_backend_id = active_backend_id
        self.session_mgr = None
        self.API_VERSION = None

        self._get_3par_config(array_id=active_backend_id)
        try:
            LOG.debug("Connecting to array")
            api_url = self._client_conf['hpe3par_api_url']
            username = self._client_conf['hpe3par_username']
            password = self._client_conf['hpe3par_password']
            self.session_mgr = SessionManager(api_url, username, password)

            SystemWorkflow.__init__(self, self.session_mgr)
            CPGWorkflow.__init__(self, self.session_mgr)
            VolumeWorkflow.__init__(self, self.session_mgr)
            SnapshotWorkflow.__init__(self, self.session_mgr)
            HostWorkflow.__init__(self, self.session_mgr)
            VLUNWorkflow.__init__(self, self.session_mgr)
            RemoteCopyGroupWorkflow.__init__(self, self.session_mgr, None)
            VolumeSetWorkflow.__init__(self, self.session_mgr)
            QOSWorkflow.__init__(self, self.session_mgr)
            TaskManager.__init__(self,self.session_mgr)
        except Exception as ex:
            msg = (_("Failed to Login to array (%(url)s) because %(err)s") %
                   {'url': self._client_conf['hpe3par_api_url'], 'err': ex})
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg) from ex

    def get_version(self):
        return self.VERSION

    @classmethod
    def get_driver_options(cls):
        additional_opts = driver.BaseVD._get_oslo_driver_opts(
            'san_ip', 'san_login', 'san_password', 'reserved_percentage',
            'max_over_subscription_ratio', 'replication_device', 'target_port',
            'san_ssh_port', 'ssh_conn_timeout', 'san_private_key',
            'target_ip_address', 'unique_fqdn_network')
        return hpe3par_opts + additional_opts

    def check_flags(self, options, required_flags):
        for flag in required_flags:
            if not getattr(options, flag, None):
                msg = _('%s is not set') % flag
                LOG.error(msg)
                raise exception.InvalidInput(reason=msg)

    def check_replication_flags(self, options, required_flags):
        for flag in required_flags:
            if not options.get(flag, None):
                msg = (_('%s is not set and is required for the replication '
                         'device to be valid.') % flag)
                LOG.error(msg)
                raise exception.InvalidInput(reason=msg)

    def client_login(self):
        try:
            LOG.debug("Connecting to array")
            api_url = self._client_conf['hpe3par_api_url']
            username = self._client_conf['hpe3par_username']
            password = self._client_conf['hpe3par_password']
            self.session_mgr = SessionManager(api_url, username, password)
        except Exception as ex:
            msg = (_("Failed to Login to array (%(url)s) because %(err)s") %
                   {'url': self._client_conf['hpe3par_api_url'], 'err': ex})
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg) from ex

    def client_logout(self):
        if self.session_mgr:
            LOG.debug("Disconnect from array")
            # not deleting session key for now since session.get_token() not working correctly
            #self.session_mgr.delete_session()

    def _create_replication_client(self, remote_array):
        try:
            LOG.debug("Connecting to replication array")
            remote_api_url = remote_array['hpe3par_api_url']
            remote_username = remote_array['hpe3par_username']
            remote_password = remote_array['hpe3par_password']
            LOG.debug("remote_api_url: %(remote_api_url)s", {'remote_api_url': remote_api_url})
            LOG.debug("remote_username: %(remote_username)s", {'remote_username': remote_username})
            LOG.debug("remote_password: %(remote_password)s", {'remote_password': remote_password})
            repl_session_mgr = SessionManager(remote_api_url, remote_username, remote_password)
        except Exception as ex:
            msg = (_("Failed to Login to remote array (%(url)s) because %(err)s") %
                   {'url': remote_array['hpe3par_api_url'], 'err': ex})
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg) from ex
        
        return repl_session_mgr


    def _destroy_replication_client(self, repl_session_mgr):
        if repl_session_mgr is not None:
            # not deleting session key for now since session.get_token() not working correctly
            repl_session_mgr.delete_session()


    def do_setup(self, context, timeout=None, stats=None, array_id=None):
        LOG.debug("do_setup - get api version and system info")
        try:
            # This will set self._client_conf with the proper credentials
            # to communicate with the 3PAR array. It will contain either
            # the values for the primary array or secondary array in the
            # case of a fail-over.
            LOG.info("Session token %(token)s",
                                {'token': self.session_mgr.token})
            wsapi_version = super().get_ws_api_version()
            self.API_VERSION = wsapi_version['build']
            LOG.info("Found storagesystem version %(version)s",
                                {'version': self.API_VERSION})
        except flowkit_exceptions.HPEStorageException as ex:
            LOG.error("Exception during get api version: %s", ex)
            raise exception.InvalidInput(ex) from ex
        finally:
            self.client_logout()
        # Get the client ID for provider_location. We only need to retrieve
        # the ID directly from the array if the driver stats are not provided.
        if not stats or 'array_id' not in stats:
            try:
                # this is required since in finally above we are deleting the session token
                self.session_mgr.ensure_session()
                LOG.info("Session token after finally %(token)s",
                                {'token': self.session_mgr.token})
                info = super().get_storage_system_info()
                self.id = str(info['id'])
                LOG.info("Found storagesystem id %(id)s",
                                {'id': self.id})
            except Exception as ex:
                LOG.error("Exception during get system info: %s", ex)
                self.id = 0
            finally:
                self.client_logout()
        else:
            self.id = stats['array_id']


    def get_volume_stats(self,
                         refresh,
                         filter_function=None,
                         goodness_function=None):
        if refresh:
            self._update_volume_stats(
                filter_function=filter_function,
                goodness_function=goodness_function)

        return self.stats


    def _update_volume_stats(self,
                             filter_function=None,
                             goodness_function=None):
        # const to convert MiB to GB
        const = 0.0009765625

        # storage_protocol and volume_backend_name are
        # set in the child classes

        pools = []
        try:
            self.session_mgr.ensure_session()
            LOG.info("Session token in vol stats %(token)s",
                                {'token': self.session_mgr.token})
            info = super().get_storage_system_info()
            LOG.info("Found storagesystem info %(info)s",
                                {'info': info})
            backend_state = 'up'
        except Exception as ex:
            info = {}
            backend_state = 'down'
            LOG.warning("Exception at get_storage_system_info() "
                        "Reason: '%(reason)s'", {'reason': ex})

        qos_support = True
        thin_support = True
        remotecopy_support = True
        compression_support = True

        for cpg_name in self._client_conf['hpe3par_cpg']:
            try:
                stat_capabilities = {
                    constants.THROUGHPUT: None,
                    constants.BANDWIDTH: None,
                    constants.LATENCY: None,
                    constants.IO_SIZE: None,
                    constants.QUEUE_LENGTH: None,
                    constants.AVG_BUSY_PERC: None
                }
                LOG.info("Session token for cpg %(token)s",
                                {'token': self.session_mgr.token})
                cpg = super().get_cpg(cpg_name)
                LOG.info("Found cpg %(cpg)s",
                                {'cpg': cpg})
                try:
                    stat_capabilities = super().get_cpg_stat_data(cpg_name)
                    LOG.info("Found cpg stat_capabilities %(stat_capabilities)s",
                                {'stat_capabilities': stat_capabilities})
                except Exception as ex:
                    LOG.warning("Exception at getCPGStatData() "
                                "for cpg: '%(cpg_name)s' "
                                "Reason: '%(reason)s'",
                                {'cpg_name': cpg_name, 'reason': ex})
                if 'numTDVVs' in cpg:
                    total_volumes = int(
                        cpg['numFPVVs'] + cpg['numTPVVs'] + cpg['numTDVVs']
                    )
                else:
                    total_volumes = int(
                        cpg['numFPVVs'] + cpg['numTPVVs']
                    )

                if 'limitMiB' not in cpg['SDGrowth']:
                    # cpg usable free space
                    cpg_avail_space = (
                        super().get_available_space(cpg_name))
                    LOG.info("Found cpg_avail_space %(cpg_avail_space)s",
                                {'cpg_avail_space': cpg_avail_space})
                    # total_capacity is the best we can do for a limitless cpg
                    total_capacity = int(
                        (cpg['SDUsage']['usedMiB'] +
                         cpg['UsrUsage']['usedMiB'] +
                         cpg_avail_space['usableFreeMiB']) * const)
                else:
                    total_capacity = int(cpg['SDGrowth']['limitMiB'] * const)

                provisioned_capacity = int((cpg['UsrUsage']['totalMiB'] +
                                            cpg['SAUsage']['totalMiB'] +
                                            cpg['SDUsage']['totalMiB']) *
                                           const)
                free_capacity = total_capacity - provisioned_capacity
                capacity_utilization = (
                    (float(total_capacity - free_capacity) /
                     float(total_capacity)) * 100)

            except flowkit_exceptions.HTTPNotFound as ex:
                err = (_("CPG (%s) doesn't exist on array")
                       % cpg_name)
                LOG.error(err)
                raise exception.InvalidInput(reason=err) from ex

            pool = {'pool_name': cpg_name,
                    'total_capacity_gb': total_capacity,
                    'free_capacity_gb': free_capacity,
                    'provisioned_capacity_gb': provisioned_capacity,
                    'QoS_support': qos_support,
                    'thin_provisioning_support': thin_support,
                    'thick_provisioning_support': True,
                    'max_over_subscription_ratio': (
                        self.config.safe_get('max_over_subscription_ratio')),
                    'reserved_percentage': (
                        self.config.safe_get('reserved_percentage')),
                    'location_info': ('HPE3PARDriver:%(sys_id)s:%(dest_cpg)s' %
                                      {'sys_id': info.get('serialNumber'),
                                       'dest_cpg': cpg_name}),
                    'total_volumes': total_volumes,
                    'capacity_utilization': capacity_utilization,
                    constants.THROUGHPUT: stat_capabilities[constants.THROUGHPUT],
                    constants.BANDWIDTH: stat_capabilities[constants.BANDWIDTH],
                    constants.LATENCY: stat_capabilities[constants.LATENCY],
                    constants.IO_SIZE: stat_capabilities[constants.IO_SIZE],
                    constants.QUEUE_LENGTH: stat_capabilities[constants.QUEUE_LENGTH],
                    constants.AVG_BUSY_PERC: stat_capabilities[constants.AVG_BUSY_PERC],
                    'filter_function': filter_function,
                    'goodness_function': goodness_function,
                    'multiattach': True,
                    'consistent_group_snapshot_enabled': True,
                    'compression': compression_support,
                    'consistent_group_replication_enabled':
                        self._replication_enabled,
                    'backend_state': backend_state
                    }

            if remotecopy_support:
                pool['replication_enabled'] = self._replication_enabled
                pool['replication_type'] = ['sync', 'periodic']
                pool['replication_count'] = len(self._replication_targets)

            pools.append(pool)

        self.stats = {'driver_version': '4.0',
                      'storage_protocol': None,
                      'vendor_name': 'Hewlett Packard Enterprise',
                      'volume_backend_name': None,
                      'array_id': info.get('id'),
                      'replication_enabled': self._replication_enabled,
                      'replication_targets': self._get_replication_targets(),
                      'pools': pools}
        

    """ def check_for_setup_error(self):
        if not all((hpe3parclient, client, hpeexceptions)):
            msg = _('HPE driver setup error: some required '
                    'libraries (hpe3parclient, client.*) not found.')
            LOG.error(msg)
            raise exception.VolumeDriverException(message=msg)
        if self.client:
            self.client_login()
            try:
                cpg_names = self._client_conf['hpe3par_cpg']
                for cpg_name in cpg_names:
                    self.validate_cpg(cpg_name)

            finally:
                self.client_logout() """

    def validate_cpg(self, cpg_name):
        try:
            cpg = super().get_cpg(cpg_name)
        except flowkit_exceptions.HTTPNotFound as ex:
            err = (_("CPG (%s) doesn't exist on array") % cpg_name)
            LOG.error(err)
            raise exception.InvalidInput(reason=err) from ex

    def get_domain(self, cpg_name):
        try:
            cpg = super().get_cpg(cpg_name)
        except flowkit_exceptions.HTTPNotFound as ex:
            err = (_("Failed to get domain because CPG (%s) doesn't "
                     "exist on array.") % cpg_name)
            LOG.error(err)
            raise exception.InvalidInput(reason=err) from ex

        if 'domain' in cpg:
            return cpg['domain']
        return None

    def extend_volume(self, volume, new_size):
        self.session_mgr.ensure_session()            
        volume_name = self._get_3par_vol_name(volume)
        old_size = volume['size']
        growth_size = int(new_size) - old_size
        LOG.debug("Extending Volume %(vol)s from %(old)s to %(new)s, "
                  " by %(diff)s GB.",
                  {'vol': volume_name, 'old': old_size, 'new': new_size,
                   'diff': growth_size})
        growth_size_mib = growth_size * units.Ki
        self._extend_volume(volume, volume_name, growth_size_mib)

    def _get_existing_volume_ref_name(self, existing_ref, is_snapshot=False):
        """Returns the volume name of an existing reference.

        Checks if an existing volume reference has a source-name or
        source-id element. If source-name or source-id is not present an
        error will be thrown.
        """
        vol_name = None
        if 'source-name' in existing_ref:
            vol_name = existing_ref['source-name']
        elif 'source-id' in existing_ref:
            if is_snapshot:
                vol_name = self._get_3par_ums_name(existing_ref['source-id'])
            else:
                vol_name = self._get_3par_unm_name(existing_ref['source-id'])
        else:
            reason = _("Reference must contain source-name or source-id.")
            raise exception.ManageExistingInvalidReference(
                existing_ref=existing_ref,
                reason=reason)

        return vol_name

    def _extend_volume(self, volume, volume_name, growth_size_mib,
                       _convert_to_base=False):
        model_update = None
        try:
            if _convert_to_base:
                LOG.debug("Converting to base volume prior to growing.")
                model_update = self._convert_to_base_volume(volume)

            LOG.debug("volume_name: %(var)s", {'var': volume_name})
            LOG.debug("growth_size_mib: %(var)s", {'var': growth_size_mib})
            super().grow_volume(volume_name, growth_size_mib)

        except Exception as ex:
            ex_str = str(ex)
            LOG.debug("Exception while extending volume: %s", ex_str)

            with excutils.save_and_reraise_exception() as ex_ctxt:
                if (not _convert_to_base and
                    isinstance(ex, flowkit_exceptions.HTTPForbidden) and
                    str(constants.API_ERROR_150) in ex_str):
                    # Error code 150 means 'invalid operation: Cannot grow
                    # this type of volume'.
                    # Suppress raising this exception because we can
                    # resolve it by converting it into a base volume.
                    # Afterwards, extending the volume should succeed, or
                    # fail with a different exception/error code.
                    ex_ctxt.reraise = False
                    model_update = self._extend_volume(
                        volume, volume_name,
                        growth_size_mib,
                        _convert_to_base=True)
                else:
                    LOG.error("Error extending volume: %(vol)s. "
                              "Exception: %(ex)s",
                              {'vol': volume_name, 'ex': ex})
        return model_update

    @classmethod
    def _get_3par_vol_name(cls, volume_id, temp_vol=False):
        """Get converted 3PAR volume name.

        Converts the openstack volume id from
        ecffc30f-98cb-4cf5-85ee-d7309cc17cd2
        to
        osv-7P.DD5jLTPWF7tcwnMF80g

        We convert the 128 bits of the uuid into a 24character long
        base64 encoded string to ensure we don't exceed the maximum
        allowed 31 character name limit on 3Par

        We strip the padding '=' and replace + with .
        and / with -

        volume_id is a polymorphic parameter and can be either a string or a
        volume (OVO or dict representation).
        """
        # Accept OVOs (what we should only receive), dict (so we don't have to
        # change all our unit tests), and ORM (because we some methods still
        # pass it, such as terminate_connection).
        if isinstance(volume_id, (objects.Volume, objects.Volume.model, dict)):
            volume_id = volume_id.get('_name_id') or volume_id['id']
        volume_name = cls._encode_name(volume_id)
        if temp_vol:
            # is this a temporary volume
            # this is done during migration
            prefix = "tsv-%s"
        else:
            prefix = "osv-%s"
        return prefix % volume_name

    def _get_3par_snap_name(self, snapshot_id, temp_snap=False):
        snapshot_name = self._encode_name(snapshot_id)
        if temp_snap:
            # is this a temporary snapshot
            # this is done during cloning
            prefix = "tss-%s"
        else:
            prefix = "oss-%s"
        return prefix % snapshot_name

    def _get_3par_ums_name(self, snapshot_id):
        ums_name = self._encode_name(snapshot_id)
        return "ums-%s" % ums_name

    def _get_3par_vvs_name(self, volume_id):
        vvs_name = self._encode_name(volume_id)
        return "vvs-%s" % vvs_name

    def _get_3par_unm_name(self, volume_id):
        unm_name = self._encode_name(volume_id)
        return "unm-%s" % unm_name

    # v2 replication conversion
    def _get_3par_rcg_name(self, volume):
        # if non-replicated volume is retyped or migrated to replicated vol,
        # then rcg_name is different. Try to get that new rcg_name.
        if volume['migration_status'] == 'success':
            vol_name = self._get_3par_vol_name(volume)
            vol_details = super().get_volume(vol_name)

            rcg_name = vol_details.get('rcopyGroup')

            LOG.debug("new rcg_name: %(name)s",
                      {'name': rcg_name})
            return rcg_name
        else:
            # by default, rcg_name is similar to volume name
            rcg_name = self._encode_name(volume.get('_name_id')
                                         or volume['id'])
            rcg = "rcg-%s" % rcg_name
            return rcg[:22]

    def _get_3par_remote_rcg_name(self, volume, provider_location):
        return self._get_3par_rcg_name(volume) + ".r" + (
            str(provider_location))

    @staticmethod
    def _encode_name(name):
        uuid_str = name.replace("-", "")
        vol_uuid = uuid.UUID('urn:uuid:%s' % uuid_str)
        vol_encoded = base64.encode_as_text(vol_uuid.bytes)

        # 3par doesn't allow +, nor /
        vol_encoded = vol_encoded.replace('+', '.')
        vol_encoded = vol_encoded.replace('/', '-')
        # strip off the == as 3par doesn't like those.
        vol_encoded = vol_encoded.replace('=', '')
        return vol_encoded

    def _capacity_from_size(self, vol_size):
        # because 3PAR volume sizes are in Mebibytes.
        if int(vol_size) == 0:
            capacity = units.Gi  # default: 1GiB
        else:
            capacity = vol_size * units.Gi

        capacity = int(math.ceil(capacity / units.Mi))
        return capacity

    def _get_volume_type(self, type_id):
        ctxt = context.get_admin_context()
        return volume_types.get_volume_type(ctxt, type_id)

    def _get_key_value(self, hpe3par_keys, key, default=None):
        if hpe3par_keys is not None and key in hpe3par_keys:
            return hpe3par_keys[key]
        else:
            return default

    def _get_boolean_key_value(self, hpe3par_keys, key, default=False):
        value = self._get_key_value(
            hpe3par_keys, key, default)
        if isinstance(value, str):
            if value.lower() == 'true':
                value = True
            else:
                value = False
        return value

    def _is_alletra_mp(self):
        """Check if the backend is AlletraMP based on WSAPI version.

        AlletraMP uses WSAPI version >= 100500000 (API_VERSION_R5).

        :returns: True if AlletraMP, False otherwise
        """
        return self.API_VERSION >= constants.API_VERSION_R5

    def _get_qos_value(self, qos, key, default=None):
        if key in qos:
            return qos[key]
        else:
            return default

    def _get_qos_by_volume_type(self, volume_type):
        qos = {}
        qos_specs_id = volume_type.get('qos_specs_id')
        specs = volume_type.get('extra_specs')

        # NOTE(kmartin): We prefer the qos_specs association
        # and override any existing extra-specs settings
        # if present.
        if qos_specs_id is not None:
            kvs = qos_specs.get_qos_specs(context.get_admin_context(),
                                          qos_specs_id)['specs']
        else:
            kvs = specs

        for key, value in kvs.items():
            if 'qos:' in key:
                fields = key.split(':')
                key = fields[1]
            if key in constants.hpe_qos_keys:
                qos[key] = value
        return qos

    def _get_keys_by_volume_type(self, volume_type):
        hpe3par_keys = {}
        specs = volume_type.get('extra_specs')
        for key, value in specs.items():
            if ':' in key:
                fields = key.split(':')
                key = fields[1]
            if key in constants.hpe3par_valid_keys:
                hpe3par_keys[key] = value
        return hpe3par_keys

    def _set_qos_rule(self, qos, vvs_name):
        min_io = self._get_qos_value(qos, 'minIOPS')
        max_io = self._get_qos_value(qos, 'maxIOPS')
        min_bw = self._get_qos_value(qos, 'minBWS')
        max_bw = self._get_qos_value(qos, 'maxBWS')
        latency = self._get_qos_value(qos, 'latency')
        priority = self._get_qos_value(qos, 'priority', 'normal')

        # Check if backend is AlletraMP
        is_alletra_mp = self._is_alletra_mp()

        qosRule = {}

        # For Alletra MP, ioMinGoal, bwMinGoalKB, latencyGoal, and priority
        # are deprecated. Only use max limits.
        if is_alletra_mp:
            # For Alletra MP, at least one of maxIOPS or maxBWS must be
            # provided.
            if max_io is None and max_bw is None:
                err = _(
                    "For Alletra MP, at least one of maxIOPS or maxBWS "
                    "QoS parameters must be provided.")
                LOG.error(err)
                raise exception.InvalidInput(reason=err)
            # Alletra MP: Only set max limits, min goals are deprecated
            if max_io:
                qosRule['ioMaxLimit'] = int(max_io)
            if max_bw:
                qosRule['bwMaxLimitKB'] = int(max_bw) * units.k
            if min_io:
                LOG.warning(
                    "minIOPS QoS parameter is deprecated for "
                    "Alletra MP and will be ignored.")
            if min_bw:
                LOG.warning(
                    "minBWS QoS parameter is deprecated for "
                    "Alletra MP and will be ignored.")
            if latency:
                LOG.warning("latency QoS parameter is deprecated for "
                            "Alletra MP and will be ignored.")
            if priority:
                LOG.warning("priority QoS parameter is deprecated for "
                            "Alletra MP and will be ignored.")
        else:
            # for older Alletra MP (10.1 to 10.4): Use traditional QoS parameters
            if min_io:
                qosRule['ioMinGoal'] = int(min_io)
                if max_io is None:
                    qosRule['ioMaxLimit'] = int(min_io)
            if max_io:
                qosRule['ioMaxLimit'] = int(max_io)
                if min_io is None:
                    qosRule['ioMinGoal'] = int(max_io)
            if min_bw:
                qosRule['bwMinGoalKB'] = int(min_bw) * units.k
                if max_bw is None:
                    qosRule['bwMaxLimitKB'] = int(min_bw) * units.k
            if max_bw:
                qosRule['bwMaxLimitKB'] = int(max_bw) * units.k
                if min_bw is None:
                    qosRule['bwMinGoalKB'] = int(max_bw) * units.k
            if latency:
                # latency could be values like 2, 5, etc or
                # small values like 0.1, 0.02, etc.
                # we are converting to float so that 0.1 doesn't become 0
                latency = float(latency)
                if latency >= 1:
                    # by default, latency in millisecs
                    qosRule['latencyGoal'] = int(latency)
                else:
                    # latency < 1 Eg. 0.1, 0.02, etc
                    # convert latency to microsecs
                    qosRule['latencyGoaluSecs'] = int(latency * 1000)
            if priority:
                qosRule['priority'] = constants.qos_priority_level.get(priority.lower())

        qosRule['name'] = vvs_name
        qosRule['type'] = 1
        LOG.debug("qosRule %(qosRule)s", {'qosRule': qosRule})

        try:
            super().create_qos(qosRule)
        except Exception:
            with excutils.save_and_reraise_exception():
                LOG.error("Error creating QOS rule %s", qosRule)

    def get_flash_cache_policy(self, hpe3par_keys):
        if hpe3par_keys is not None:
            # First check list of extra spec keys
            val = self._get_key_value(hpe3par_keys, 'flash_cache', None)
            if val is not None:
                if val.lower() == 'true':
                    return 1
                else:
                    return 2

        return None

    def get_compression_policy(self, hpe3par_keys):
        if hpe3par_keys is not None:
            # here it should return true/false/None
            val = self._get_key_value(hpe3par_keys, 'compression', None)
            if val is not None:
                if val.lower() == 'true':
                    return True
                else:
                    return False

        return None

    def get_cpg(self, volume, allowSnap=False):
        volume_name = self._get_3par_vol_name(volume)
        vol = super().get_volume(volume_name)
        # Search for 'userCPG' in the get volume REST API,
        # if found return userCPG , else search for snapCPG attribute
        # when allowSnap=True. For the cases where REST call for
        # get volume doesn't have either userCPG or snapCPG ,
        # take the default value of cpg from 'host' attribute from volume param
        LOG.debug("get volume response is: %s", vol)
        if 'userCPG' in vol:
            return vol['userCPG']
        elif allowSnap and 'snapCPG' in vol:
            return vol['snapCPG']
        else:
            return volume_utils.extract_host(volume['host'], 'pool')

    def _get_3par_vol_comment(self, volume_name):
        vol = super().get_volume(volume_name)
        if 'comment' in vol:
            return vol['comment']
        return None

    def validate_persona(self, persona_value):
        """Validate persona value.

        If the passed in persona_value is not valid, raise InvalidInput,
        otherwise return the persona ID.

        :param persona_value:
        :raises exception.InvalidInput:
        :returns: persona ID
        """
        if persona_value not in constants.valid_persona_values:
            err = (_("Must specify a valid persona %(valid)s,"
                     "value '%(persona)s' is invalid.") %
                   {'valid': constants.valid_persona_values,
                   'persona': persona_value})
            LOG.error(err)
            raise exception.InvalidInput(reason=err)
        # persona is set by the id so remove the text and return the id
        # i.e for persona '1 - Generic' returns 1
        persona_id = persona_value.split(' ')
        return persona_id[0]

    def get_persona_type(self, volume, hpe3par_keys=None):
        default_persona = constants.valid_persona_values[0]
        type_id = volume.get('volume_type_id', None)
        if type_id is not None:
            volume_type = self._get_volume_type(type_id)
            if hpe3par_keys is None:
                hpe3par_keys = self._get_keys_by_volume_type(volume_type)
        persona_value = self._get_key_value(hpe3par_keys, 'persona',
                                            default_persona)
        return self.validate_persona(persona_value)

    def get_type_info(self, type_id):
        """Get 3PAR type info for the given type_id.

        Reconciles VV Set, old-style extra-specs, and QOS specs
        and returns commonly used info about the type.

        :returns: hpe3par_keys, qos, volume_type, vvs_name
        """
        volume_type = None
        vvs_name = None
        hpe3par_keys = {}
        qos = {}
        if type_id is not None:
            volume_type = self._get_volume_type(type_id)
            hpe3par_keys = self._get_keys_by_volume_type(volume_type)
            vvs_name = self._get_key_value(hpe3par_keys, 'vvs')
            if vvs_name is None:
                qos = self._get_qos_by_volume_type(volume_type)
        return hpe3par_keys, qos, volume_type, vvs_name

    def get_volume_settings_from_type_id(self, type_id, pool):
        """Get 3PAR volume settings given a type_id.

        Combines type info and config settings to return a dictionary
        describing the 3PAR volume settings.  Does some validation (CPG).
        Uses pool as the default cpg (when not specified in volume type specs).

        :param type_id: id of type to get settings for
        :param pool: CPG to use if type does not have one set
        :returns: dict
        """

        hpe3par_keys, qos, volume_type, vvs_name = self.get_type_info(type_id)

        # Default to pool extracted from host.
        # If that doesn't work use the 1st CPG in the config as the default.
        default_cpg = pool or self._client_conf['hpe3par_cpg'][0]

        cpg = self._get_key_value(hpe3par_keys, 'cpg', default_cpg)
        if cpg is not default_cpg:
            # The cpg was specified in a volume type extra spec so it
            # needs to be validated that it's in the correct domain.
            # log warning here
            msg = ("'hpe3par:cpg' is not supported as an extra spec "
                   "in a volume type.  CPG's are chosen by "
                   "the cinder scheduler, as a pool, from the "
                   "cinder.conf entry 'hpe3par_cpg', which can "
                   "be a list of CPGs.")
            versionutils.report_deprecated_feature(LOG, msg)
            LOG.info("Using pool %(pool)s instead of %(cpg)s",
                     {'pool': pool, 'cpg': cpg})

            cpg = pool
            self.validate_cpg(cpg)
        # Look to see if the snap_cpg was specified in volume type
        # extra spec, if not use hpe3par_cpg_snap from config as the
        # default.
        snap_cpg = self.config.hpe3par_cpg_snap
        snap_cpg = self._get_key_value(hpe3par_keys, 'snap_cpg', snap_cpg)
        # If it's still not set or empty then set it to the cpg.
        if not snap_cpg:
            snap_cpg = cpg

        # Check group level replication
        hpe3par_tiramisu = (
            self._get_key_value(hpe3par_keys, 'group_replication'))

        # by default, set convert_to_base to False
        convert_to_base = self._get_boolean_key_value(
            hpe3par_keys, 'convert_to_base')

        # if provisioning is not set use thin
        default_prov = constants.valid_prov_values[0]
        prov_value = self._get_key_value(hpe3par_keys, 'provisioning',
                                         default_prov)
        # check for valid provisioning type
        if prov_value not in constants.valid_prov_values:
            err = (_("Must specify a valid provisioning type %(valid)s, "
                     "value '%(prov)s' is invalid.") %
                   {'valid': constants.valid_prov_values,
                    'prov': prov_value})
            LOG.error(err)
            raise exception.InvalidInput(reason=err)

        tpvv = True
        tdvv = False
        if prov_value == "full":
            tpvv = False
        elif prov_value == "dedup":
            tpvv = False
            tdvv = True

        return {'hpe3par_keys': hpe3par_keys,
                'cpg': cpg, 'snap_cpg': snap_cpg,
                'vvs_name': vvs_name, 'qos': qos,
                'tpvv': tpvv, 'tdvv': tdvv,
                'volume_type': volume_type,
                'group_replication': hpe3par_tiramisu,
                'convert_to_base': convert_to_base}

    def get_volume_settings_from_type(self, volume, host=None):
        """Get 3PAR volume settings given a volume.

        Combines type info and config settings to return a dictionary
        describing the 3PAR volume settings.  Does some validation (CPG and
        persona).

        :param volume:
        :param host: Optional host to use for default pool.
        :returns: dict
        """

        type_id = volume.get('volume_type_id', None)

        pool = None
        if host:
            pool = volume_utils.extract_host(host['host'], 'pool')
        else:
            pool = volume_utils.extract_host(volume['host'], 'pool')

        volume_settings = self.get_volume_settings_from_type_id(type_id, pool)

        # check for valid persona even if we don't use it until
        # attach time, this will give the end user notice that the
        # persona type is invalid at volume creation time
        self.get_persona_type(volume, volume_settings['hpe3par_keys'])

        return volume_settings

    def create_volume(self, volume, perform_replica=True):
        LOG.debug('CREATE VOLUME (%(disp_name)s: %(vol_name)s %(id)s on '
                  '%(host)s)',
                  {'disp_name': volume['display_name'],
                   'vol_name': volume['name'],
                   'id': self._get_3par_vol_name(volume),
                   'host': volume['host']})
        
        self.session_mgr.ensure_session()

        try:
            comments = {'volume_id': volume['id'],
                        'name': volume['name'],
                        'type': 'OpenStack'}
            self._add_name_id_to_comment(comments, volume)

            # This flag denotes group level replication on
            # hpe 3par.
            hpe_tiramisu = False
            name = volume.get('display_name', None)
            if name:
                comments['display_name'] = name

            # get the options supported by volume types
            type_info = self.get_volume_settings_from_type(volume)
            volume_type = type_info['volume_type']
            vvs_name = type_info['vvs_name']
            qos = type_info['qos']
            cpg = type_info['cpg']
            snap_cpg = type_info['snap_cpg']
            tpvv = type_info['tpvv']
            tdvv = type_info['tdvv']
            flash_cache = self.get_flash_cache_policy(
                type_info['hpe3par_keys'])
            compression = self.get_compression_policy(
                type_info['hpe3par_keys'])

            consis_group_snap_type = False
            if volume_type is not None:
                consis_group_snap_type = self.is_volume_group_snap_type(
                    volume_type)

            cg_id = volume.get('group_id', None)
            group = volume.get('group', None)
            if cg_id and consis_group_snap_type:
                vvs_name = self._get_3par_vvs_name(cg_id)

            type_id = volume.get('volume_type_id', None)
            if type_id is not None:
                comments['volume_type_name'] = volume_type.get('name')
                comments['volume_type_id'] = type_id
                if vvs_name is not None:
                    comments['vvs'] = vvs_name
                else:
                    comments['qos'] = qos

            extras = {'comment': json.dumps(comments),
                      'tpvv': tpvv}

            LOG.debug("self.API_VERSION: %(version)s",
                      {'version': self.API_VERSION})

            # set the reduce option if both are specified in extra-specs
            if tdvv and compression:
                extras['reduce'] = tdvv

            capacity = self._capacity_from_size(volume['size'])
            volume_name = self._get_3par_vol_name(volume)

            response = super().create_volume(volume_name, cpg, capacity,
                                        extras)

            # v2 replication check
            replication_flag = False

            if consis_group_snap_type:
                if (self._volume_of_hpe_tiramisu_type(volume)):
                    hpe_tiramisu = True

            # Add volume to remote group.
            if (group is not None and hpe_tiramisu):
                if group.is_replicated:
                    self._check_rep_status_enabled_on_group(group)
                    self._add_vol_to_remote_group(group, volume)
                    replication_flag = True

            if qos or vvs_name or flash_cache is not None:
                try:
                    self._add_volume_to_volume_set(volume, volume_name,
                                                   cpg, vvs_name, qos,
                                                   flash_cache)
                except exception.InvalidInput as ex:
                    # Delete the volume if unable to add it to the volume set
                    super().delete_volume(volume_name)
                    LOG.error("Exception: %s", ex)
                    raise exception.CinderException(ex) from ex
                
            LOG.debug("perform replica: %(flag)s", {'flag': perform_replica})
            if perform_replica:
                if (self._volume_of_replicated_type(volume,
                                                    hpe_tiramisu_check=True)
                   and self._do_volume_replication_setup(volume)):
                    replication_flag = True

        except Exception as ex:
            LOG.error("Exception: %s", ex)
            raise exception.CinderException(ex) from ex

        return self._get_model_update(volume['host'], cpg,
                                      replication=replication_flag,
                                      provider_location=self.id,
                                      hpe_tiramisu=hpe_tiramisu)
    

    def _copy_volume(self, src_name, dest_name, cpg, snap_cpg=None,
                     tpvv=True, tdvv=False, compression=None, comment=None):
        # Virtual volume sets are not supported with the -online option
        LOG.debug('Creating clone of a volume %(src)s to %(dest)s with cpg %(cpg)s.',
                  {'src': src_name, 'dest': dest_name, 'cpg': cpg})
        
        optional = {'tpvv': tpvv, 'online': True}

        if tdvv and compression:
            optional['reduce'] = tdvv

        # note: comment is not supported for clone vol

        body = super().copy_volume(src_name, dest_name, cpg, optional)
        return body['taskid']

    def get_next_word(self, s, search_string):
        """Return the next word.

        Search 's' for 'search_string', if found return the word preceding
        'search_string' from 's'.
        """
        word = re.search(search_string.strip(' ') + ' ([^ ]*)', s)
        return word.groups()[0].strip(' ')

    def _get_3par_vol_comment_value(self, vol_comment, key):
        comment_dict = dict(ast.literal_eval(vol_comment))
        if key in comment_dict:
            return comment_dict[key]
        return None

    def _get_model_update(self, volume_host, cpg, replication=False,
                          provider_location=None, hpe_tiramisu=None):
        """Get model_update dict to use when we select a pool.

        The pools implementation uses a volume['host'] suffix of :poolname.
        When the volume comes in with this selected pool, we sometimes use
        a different pool (e.g. because the type says to use a different pool).
        So in the several places that we do this, we need to return a model
        update so that the volume will have the actual pool name in the host
        suffix after the operation.

        Given a volume_host, which should (might) have the pool suffix, and
        given the CPG we actually chose to use, return a dict to use for a
        model update iff an update is needed.

        :param volume_host: The volume's host string.
        :param cpg: The actual pool (cpg) used, for example from the type.
        :returns: dict Model update if we need to update volume host, else None
        """
        model_update = {}
        host = volume_utils.extract_host(volume_host, 'backend')
        host_and_pool = volume_utils.append_host(host, cpg)
        if volume_host != host_and_pool:
            # Since we selected a pool based on type, update the model.
            model_update['host'] = host_and_pool
        if replication:
            model_update['replication_status'] = 'enabled'
        if (replication or hpe_tiramisu) and provider_location:
            model_update['provider_location'] = provider_location
        if not model_update:
            model_update = None
        return model_update

    def delete_volume(self, volume):
        vol_id = volume.id
        name_id = volume.get('_name_id')
        LOG.debug("DELETE volume vol_id: %(vol_id)s, name_id: %(name_id)s",
                  {'vol_id': vol_id, 'name_id': name_id})

        @utils.retry(exception.VolumeIsBusy, interval=2, retries=10)
        def _try_remove_volume(volume_name):
            try:
                super().delete_volume(volume_name)
            except Exception:
                msg = _("The volume is currently busy on the 3PAR "
                        "and cannot be deleted at this time. "
                        "You can try again later.")
                raise exception.VolumeIsBusy(message=msg)

        # v2 replication check
        # If the volume type is replication enabled, we want to call our own
        # method of deconstructing the volume and its dependencies
        if self._volume_of_replicated_type(volume, hpe_tiramisu_check=True):
            LOG.debug("volume is of replicated_type")
            replication_status = volume.get('replication_status', None)
            LOG.debug("replication_status: %(status)s",
                      {'status': replication_status})
            if replication_status:
                if replication_status == "failed-over":
                    self._delete_replicated_failed_over_volume(volume)
                else:
                    self._do_volume_replication_destroy(volume)
                return

        volume_name = self._get_3par_vol_name(volume)

        # during retype/migrate
        if (self._volume_of_replicated_type(volume, hpe_tiramisu_check=True)
           and volume['migration_status'] == 'deleting'):
            # don't use current osv_name (which was from name_id)
            # get new osv_name from id
            LOG.debug("get osv_name from volume id")
            volume_name = self._encode_name(volume.id)
            volume_name = "osv-" + volume_name

        LOG.debug("volume_name: %(name)s", {'name': volume_name})
        try:
            # Try and delete the volume, it might fail here because
            # the volume is part of a volume set which will have the
            # volume set name in the error.
            try:
                super().delete_volume(volume_name)
            except flowkit_exceptions.HTTPBadRequest as ex:
                ex_str = str(ex)
                LOG.debug("flowkit HPEStorageException: %s", ex_str)
                if str(constants.API_ERROR_29) in ex_str:
                    if self.isOnlinePhysicalCopy(volume_name):
                        LOG.debug("Found an online copy for %(volume)s",
                                  {'volume': volume_name})
                        # the volume is in process of being cloned.
                        # stopOnlinePhysicalCopy will also delete
                        # the volume once it stops the copy.
                        self.stopOnlinePhysicalCopy(volume_name)
                    else:
                        LOG.error("Exception: %s", ex)
                        raise
            except flowkit_exceptions.HTTPConflict as ex:
                ex_str = str(ex)
                if str(constants.API_ERROR_34) in ex_str:
                    # This is a special case which means the
                    # volume is part of a volume set.
                    self._delete_vvset(volume)
                    super().delete_volume(volume_name)
                if str(constants.API_ERROR_151) in ex_str:
                    if self.isOnlinePhysicalCopy(volume_name):
                        LOG.debug("Found an online copy for %(volume)s",
                                  {'volume': volume_name})
                        # the volume is in process of being cloned.
                        # stopOnlinePhysicalCopy will also delete
                        # the volume once it stops the copy.
                        self.stopOnlinePhysicalCopy(volume_name)
                    else:
                        # the volume is being operated on in a background
                        # task on the 3PAR.
                        _try_remove_volume(volume_name)
                if str(constants.API_ERROR_32) in ex_str:
                    # Error 32 means that the volume has children

                    # see if we have any temp snapshots
                    snaps = super().getVolumeSnapshots(volume_name)
                    for snap in snaps:
                        if snap.startswith('tss-'):
                            # looks like we found a temp snapshot.
                            LOG.info(
                                "Found a temporary snapshot %(name)s",
                                {'name': snap})
                            try:
                                super().delete_volume(snap)
                            except flowkit_exceptions.HTTPNotFound:
                                # if the volume is gone, it's as good as a
                                # successful delete
                                pass
                            except Exception as ex:
                                msg = _("Volume has a temporary snapshot that "
                                        "can't be deleted at this time.")
                                raise exception.VolumeIsBusy(message=msg) from ex

                    try:
                        self.delete_volume(volume)
                    except Exception as ex:
                        msg = _("Volume has children and cannot be deleted!")
                        raise exception.VolumeIsBusy(message=msg) from ex
            except flowkit_exceptions.HTTPNotFound as ex:
                ex_str = str(ex)
                if str(constants.API_ERROR_23) in ex_str:
                    LOG.warning("Delete volume id not found. Removing from "
                                "cinder: %(id)s Ex: %(msg)s",
                                {'id': volume['id'], 'msg': ex})
        except Exception as ex:
            LOG.error("Exception: %s", ex)
            raise exception.CinderException(ex) from ex

    def create_volume_from_snapshot(self, volume, snapshot, snap_name=None,
                                    vvs_name=None):
        """Creates a volume from a snapshot."""
        LOG.debug("Create Volume from Snapshot\n%(vol_name)s\n%(ss_name)s",
                  {'vol_name': pprint.pformat(volume['display_name']),
                   'ss_name': pprint.pformat(snapshot['display_name'])})

        self.session_mgr.ensure_session()
        model_update = {}

        try:
            if not snap_name:
                snap_name = self._get_3par_snap_name(snapshot['id'])
            volume_name = self._get_3par_vol_name(volume)

            extra = {'volume_id': volume['id'],
                     'snapshot_id': snapshot['id']}
            self._add_name_id_to_comment(extra, volume)

            type_id = volume.get('volume_type_id', None)

            hpe3par_keys, qos, _volume_type, vvs = self.get_type_info(
                type_id)
            if vvs:
                vvs_name = vvs

            name = volume.get('display_name', None)
            if name:
                extra['display_name'] = name

            description = volume.get('display_description', None)
            if description:
                extra['description'] = description

            optional = {'comment': json.dumps(extra),
                        'readOnly': False}

            LOG.debug("snap_name: %(name)s", {'name': snap_name})
            LOG.debug("volume_name: %(name)s", {'name': volume_name})
            super().create_snapshot(snap_name, volume_name, optional)

            # by default, set convert_to_base to False
            convert_to_base = self._get_boolean_key_value(
                hpe3par_keys, 'convert_to_base')

            LOG.debug("convert_to_base: %(convert)s",
                      {'convert': convert_to_base})

            growth_size = volume['size'] - snapshot['volume_size']
            LOG.debug("growth_size: %(size)s", {'size': growth_size})
            if growth_size > 0 or convert_to_base:
                # Convert snapshot volume to base volume type
                LOG.debug('Converting to base volume type: %(id)s.',
                          {'id': volume['id']})
                model_update = self._convert_to_base_volume(volume)
            else:
                LOG.debug("volume is created as child of snapshot")

            if growth_size > 0:
                try:
                    growth_size_mib = growth_size * units.Gi / units.Mi
                    LOG.debug('Growing volume: %(id)s by %(size)s GiB.',
                              {'id': volume['id'], 'size': growth_size})
                    super().grow_volume(volume_name, growth_size_mib)
                except Exception as ex:
                    LOG.error("Error extending volume %(id)s. "
                              "Ex: %(ex)s",
                              {'id': volume['id'], 'ex': ex})
                    # Delete the volume if unable to grow it
                    super().delete_volume(volume_name)
                    raise exception.CinderException(ex) from ex

            # Check for flash cache setting in extra specs
            flash_cache = self.get_flash_cache_policy(hpe3par_keys)

            if qos or vvs_name or flash_cache is not None:
                cpg_names = self._get_key_value(
                    hpe3par_keys, 'cpg', self._client_conf['hpe3par_cpg'])
                try:
                    self._add_volume_to_volume_set(volume, volume_name,
                                                   cpg_names[0], vvs_name,
                                                   qos, flash_cache)
                except Exception as ex:
                    # Delete the volume if unable to add it to the volume set
                    super().delete_volume(volume_name)
                    LOG.error("Exception: %s", ex)
                    raise exception.CinderException(ex) from ex

            if self._volume_of_hpe_tiramisu_type(volume):
                model_update['provider_location'] = self.id

            # v2 replication check
            if (self._volume_of_replicated_type(volume,
                                                hpe_tiramisu_check=True)
               and self._do_volume_replication_setup(volume)):
                model_update['replication_status'] = 'enabled'
                model_update['provider_location'] = self.id

        except Exception as ex:
            LOG.error("Exception: %s", ex)
            raise exception.CinderException(ex) from ex

        return model_update

    def create_snapshot(self, snapshot):
        LOG.debug("Create Snapshot\n%s", pprint.pformat(snapshot))
        try:
            self.session_mgr.ensure_session()            
            snap_name = self._get_3par_snap_name(snapshot['id'])
            # Don't use the "volume_id" from the snapshot directly in case the
            # volume has been migrated and uses a different ID in the backend.
            # This may trigger OVO lazy loading.  Use dict compatibility to
            # avoid changing all the unit tests.
            vol_name = self._get_3par_vol_name(snapshot['volume'])

            extra = {'volume_name': snapshot['volume_name'],
                     'volume_id': snapshot.get('volume_id')}
            self._add_name_id_to_comment(extra, snapshot['volume'])

            try:
                extra['display_name'] = snapshot['display_name']
            except AttributeError:
                pass

            try:
                extra['description'] = snapshot['display_description']
            except AttributeError:
                pass

            optional = {'comment': json.dumps(extra),
                        'readOnly': True}
            if self.config.hpe3par_snapshot_expiration:
                optional['expirationHours'] = (
                    int(self.config.hpe3par_snapshot_expiration))

            if self.config.hpe3par_snapshot_retention:
                optional['retentionHours'] = (
                    int(self.config.hpe3par_snapshot_retention))

            super().create_snapshot(vol_name, snap_name, optional)
        except flowkit_exceptions.HTTPForbidden as ex:
            LOG.error("Exception: %s", ex)
            raise exception.NotAuthorized() from ex
        except flowkit_exceptions.HTTPNotFound as ex:
            LOG.error("Exception: %s", ex)
            raise exception.NotFound() from ex
        except Exception as ex:
            LOG.error("Exception: %s", ex)
            raise exception.CinderException(ex) from ex

    def delete_snapshot(self, snapshot):
        LOG.debug("Delete Snapshot id %(id)s %(name)s",
                  {'id': snapshot['id'], 'name': pprint.pformat(snapshot)})

        self.session_mgr.ensure_session()            
        try:
            snap_name = self._get_3par_snap_name(snapshot['id'])
            super().delete_snapshot(snap_name)
        except flowkit_exceptions.HTTPForbidden as ex:
            LOG.error("Exception: %s", ex)
            raise exception.NotAuthorized() from ex
        except flowkit_exceptions.HTTPNotFound as ex:
            # We'll let this act as if it worked
            # it helps clean up the cinder entries.
            LOG.warning("Delete Snapshot id not found. Removing from "
                        "cinder: %(id)s Ex: %(msg)s",
                        {'id': snapshot['id'], 'msg': ex})
        except flowkit_exceptions.HTTPConflict as ex:
            ex_str = str(ex)
            LOG.debug("flowkit HTTPConflict: %s", ex_str)
            if str(constants.API_ERROR_32) in ex_str:
                # Error 32 means that the snapshot has children
                # see if we have any temp snapshots
                snaps = super().getVolumeSnapshots(snap_name)
                for snap in snaps:
                    if snap.startswith('tss-'):
                        LOG.info(
                            "Found a temporary snapshot %(name)s",
                            {'name': snap})
                        try:
                            super().delete_snapshot(snap)
                        except flowkit_exceptions.HTTPNotFound:
                            # if the volume is gone, it's as good as a
                            # successful delete
                            pass
                        except Exception as ex:
                            msg = _("Snapshot has a temporary snapshot that "
                                    "can't be deleted at this time.")
                            raise exception.SnapshotIsBusy(message=msg) from ex

                    if snap.startswith('osv-'):
                        LOG.info(
                            "Found a volume %(name)s",
                            {'name': snap})

                        # Get details of original volume v1
                        # These details would be required to form v2
                        s1_detail = super().get_volume(snap_name)
                        v1_name = s1_detail.get('copyOf')
                        v1 = super().get_volume(v1_name)

                        # Get details of volume v2,
                        # which is child of snapshot s1
                        v2_name = snap
                        v2 = super().get_volume(v2_name)

                        # Update v2 object as required for
                        # _convert_to_base function
                        v2['volume_type_id'] = (
                            self._get_3par_vol_comment_value(
                                v1['comment'], 'volume_type_id'))

                        v2['id'] = self._get_3par_vol_comment_value(
                        v2['comment'], 'volume_id')
                        v2['_name_id'] = self._get_3par_vol_comment_value(
                        v2['comment'], '_name_id')

                        v2['host'] = '#' + v1['userCPG']

                        LOG.debug('Converting to base volume type: '
                            '%(id)s.', {'id': v2['id']})
                        self._convert_to_base_volume(v2)
                try:
                    super().delete_snapshot(snap_name)
                except Exception as ex:
                    msg = _("Snapshot has children and cannot be deleted!")
                    raise exception.SnapshotIsBusy(message=msg) from ex
            else:
                LOG.error("Exception: %s", ex)
                raise exception.SnapshotIsBusy(message=ex_str) from ex
            
    def revert_to_snapshot(self, volume, snapshot):
        """Revert volume to snapshot.

        :param volume: A dictionary describing the volume to revert
        :param snapshot: A dictionary describing the latest snapshot
        """
        self.session_mgr.ensure_session()
        volume_name = self._get_3par_vol_name(volume)
        snapshot_name = self._get_3par_snap_name(snapshot['id'])
        rcg_name = self._get_3par_rcg_name(volume)
        volume_part_of_group = (
            self._volume_of_hpe_tiramisu_type_and_part_of_group(volume))
        if volume_part_of_group:
            group = volume.get('group')
            rcg_name = self._get_3par_rcg_name_of_group(group.id)

        optional = {}
        replication_flag = self._volume_of_replicated_type(
            volume, hpe_tiramisu_check=True)
        
        if replication_flag or volume_part_of_group:
            LOG.debug("Found replicated volume: %(volume)s.",
                      {'volume': volume_name})
            optional['allowRemoteCopyParent'] = True
            try:
                super().stop_remote_copy_group(rcg_name)
            except Exception as ex:
                msg = (_("There was an error stopping remote copy: %s.") %
                       str(ex))
                LOG.error(msg)
                raise exception.VolumeBackendAPIException(data=msg) from ex

        if self.isOnlinePhysicalCopy(volume_name):
            LOG.debug("Found an online copy for %(volume)s.",
                      {'volume': volume_name})
            optional['online'] = True

        body = super().promote_virtual_copy(snapshot_name, optional=optional)

        task_id = body.get('taskid')

        task_status = self._wait_for_task_completion(task_id)
        if task_status['status'] is not constants.TASK_DONE:
            dbg = {'status': task_status, 'id': volume['id']}
            msg = _('Promote virtual copy failed: '
                    'id=%(id)s, status=%(status)s.') % dbg
            raise exception.CinderException(msg)
        else:
            LOG.debug('Promote virtual copy completed: '
                      'id=%s.', volume['id'])

        if replication_flag or volume_part_of_group:
            try:
                super().start_remote_copy_group(rcg_name)
            except Exception as ex:
                msg = (_("There was an error starting remote copy: %s.") %
                       str(ex))
                LOG.error(msg)
                raise exception.VolumeBackendAPIException(data=msg) from ex

        LOG.info("Volume %(volume)s succesfully reverted to %(snap)s.",
                 {'volume': volume_name, 'snap': snapshot_name})

    def create_group_snapshot(self, context, group_snapshot, snapshots):
        """Creates a group snapshot."""
        self.session_mgr.ensure_session()
        if not volume_utils.is_group_a_cg_snapshot_type(group_snapshot):
            raise NotImplementedError()

        cg_id = group_snapshot.group_id
        snap_shot_name = self._get_3par_snap_name(group_snapshot.id) + (
            "-@count@")
        copy_of_name = self._get_3par_vvs_name(cg_id)

        extra = {'group_snapshot_id': group_snapshot.id}
        extra['group_id'] = cg_id
        extra['description'] = group_snapshot.description

        optional = {'comment': json.dumps(extra),
                    'readOnly': False}
        if self.config.hpe3par_snapshot_expiration:
            optional['expirationHours'] = (
                int(self.config.hpe3par_snapshot_expiration))

        if self.config.hpe3par_snapshot_retention:
            optional['retentionHours'] = (
                int(self.config.hpe3par_snapshot_retention))

        try:
            super().createSnapshotOfVolumeSet(snap_shot_name, copy_of_name,
                                                  optional=optional)
        except Exception as ex:
            msg = _('There was an error creating the cgsnapshot: %s') % str(ex)
            LOG.error(msg)
            raise exception.InvalidInput(reason=msg) from ex

        snapshot_model_updates = []
        for snapshot in snapshots:
            snapshot_update = {'id': snapshot['id'],
                               'status': fields.SnapshotStatus.AVAILABLE}
            snapshot_model_updates.append(snapshot_update)

        model_update = {'status': fields.GroupSnapshotStatus.AVAILABLE}

        return model_update, snapshot_model_updates
    
    
    def delete_group_snapshot(self, context, group_snapshot, snapshots):
        """Deletes a group snapshot."""
        self.session_mgr.ensure_session()
        if not volume_utils.is_group_a_cg_snapshot_type(group_snapshot):
            raise NotImplementedError()
        cgsnap_name = self._get_3par_snap_name(group_snapshot.id)

        snapshot_model_updates = []
        for i, snapshot in enumerate(snapshots):
            snapshot_update = {'id': snapshot['id']}
            try:
                snap_name = cgsnap_name + "-" + str(i)
                super().delete_snapshot(snap_name)
                snapshot_update['status'] = fields.SnapshotStatus.DELETED
            except flowkit_exceptions.HTTPNotFound as ex:
                # We'll let this act as if it worked
                # it helps clean up the cinder entries.
                LOG.warning("Delete Snapshot id not found. Removing from "
                            "cinder: %(id)s Ex: %(msg)s",
                            {'id': snapshot['id'], 'msg': ex})
                snapshot_update['status'] = fields.SnapshotStatus.DELETED
            except Exception as ex:
                LOG.error("There was an error deleting snapshot %(id)s: "
                          "%(error)s.",
                          {'id': snapshot['id'],
                           'error': str(ex)})
                snapshot_update['status'] = fields.SnapshotStatus.ERROR
            snapshot_model_updates.append(snapshot_update)

        model_update = {'status': fields.GroupSnapshotStatus.DELETED}

        return model_update, snapshot_model_updates
    

    def create_cloned_volume(self, volume, src_vref):
        self.session_mgr.ensure_session()
        try:
            vol_name = self._get_3par_vol_name(volume)
            src_vol_name = self._get_3par_vol_name(src_vref)
            back_up_process = False
            vol_chap_enabled = False
            hpe_tiramisu = False

            # Check whether a volume is ISCSI and CHAP enabled on it.
            if self._client_conf['hpe3par_iscsi_chap_enabled']:
                try:
                    vol_chap_enabled = super().getVolumeMetaData(
                        src_vol_name, 'HPQ-cinder-CHAP-name')['value']
                except flowkit_exceptions.HTTPNotFound:
                    LOG.debug("CHAP is not enabled on volume %(vol)s ",
                              {'vol': src_vref['id']})
                    vol_chap_enabled = False

            # Check whether a process is a backup
            if str(src_vref['status']) == 'backing-up':
                back_up_process = True

            # (i) if the sizes of the 2 volumes are the same and
            # (ii) this is not a backup process for ISCSI volume with chap
            #      enabled on it and
            #  (iii) volume is not replicated
            # we can do an online copy, which is a background process
            # on the 3PAR that makes the volume instantly available.
            # We can't resize a volume, while it's being copied.
            if volume['size'] == src_vref['size'] and not (
               back_up_process and vol_chap_enabled) and not (
                self._volume_of_replicated_type(volume,
                                                hpe_tiramisu_check=True)):
                LOG.debug("Creating a clone of volume, using online copy.")

                type_info = self.get_volume_settings_from_type(volume)
                snapshot = self._create_temp_snapshot(src_vref)
                cpg = type_info['cpg']
                qos = type_info['qos']
                vvs_name = type_info['vvs_name']
                flash_cache = self.get_flash_cache_policy(
                    type_info['hpe3par_keys'])

                compression_val = self.get_compression_policy(
                    type_info['hpe3par_keys'])

                LOG.info("array version: %(ver)s",
                         {'ver': self.API_VERSION})
                comment_line = None
                
                # comment can be added
                comments = {'volume_id': volume['id'],
                            'name': volume['name'],
                            'type': 'OpenStack'}

                volume_type = type_info['volume_type']
                type_id = volume.get('volume_type_id', None)
                if type_id:
                    comments['volume_type_name'] = volume_type.get('name')
                    comments['volume_type_id'] = type_id
                    if vvs_name:
                        comments['vvs'] = vvs_name
                    else:
                        comments['qos'] = qos

                display_name = volume.get('display_name', None)
                if display_name:
                    comments['display_name'] = display_name

                comment_line = json.dumps(comments)
                LOG.debug("comment_line: %(comment)s",
                          {'comment': comment_line})

                # make the array copy the contents.
                # can't delete the original until the copy is done.
                self._copy_volume(snapshot['name'], vol_name, cpg=cpg,
                                  snap_cpg=type_info['snap_cpg'],
                                  tpvv=type_info['tpvv'],
                                  tdvv=type_info['tdvv'],
                                  compression=compression_val,
                                  comment=comment_line)

                if qos or vvs_name or flash_cache is not None:
                    try:
                        self._add_volume_to_volume_set(
                            volume, vol_name, cpg, vvs_name, qos, flash_cache)
                    except exception.InvalidInput as ex:
                        # Delete volume if unable to add it to the volume set
                        super().delete_volume(vol_name)
                        dbg = {'volume': vol_name,
                               'vvs_name': vvs_name,
                               'err': str(ex)}
                        msg = _("Failed to add volume '%(volume)s' to vvset "
                                "'%(vvs_name)s' because '%(err)s'") % dbg
                        LOG.error(msg)
                        raise exception.CinderException(msg) from ex

                if self._volume_of_hpe_tiramisu_type(volume):
                    hpe_tiramisu = True

                return self._get_model_update(volume['host'], cpg,
                                              replication=False,
                                              provider_location=self.id,
                                              hpe_tiramisu=hpe_tiramisu)
            else:
                # The size of the new volume is different, so we have to
                # copy the volume and wait.  Do the resize after the copy
                # is complete.
                LOG.debug("Creating a clone of volume, using non-online copy.")

                # we first have to create the destination volume
                model_update = self.create_volume(volume,
                                                  perform_replica=False)

                optional = {'priority': 1}
                body = super().copy_volume(src_vol_name, vol_name, None,
                                              optional=optional)
                task_id = body['taskid']

                task_status = self._wait_for_task_completion(task_id)
                if task_status['status'] is not constants.TASK_DONE:
                    dbg = {'status': task_status, 'id': volume['id']}
                    msg = _('Copy volume task failed: create_cloned_volume '
                            'id=%(id)s, status=%(status)s.') % dbg
                    raise exception.CinderException(msg)
                else:
                    LOG.debug('Copy volume completed: create_cloned_volume: '
                              'id=%s.', volume['id'])

                # v2 replication check
                LOG.debug("v2 replication check")
                replication_flag = False
                if (self._volume_of_replicated_type(volume,
                                                    hpe_tiramisu_check=True)
                   and self._do_volume_replication_setup(volume)):
                    replication_flag = True
                    type_info = self.get_volume_settings_from_type(volume)
                    cpg = type_info['cpg']
                    model_update = self._get_model_update(
                        volume['host'], cpg,
                        replication=True,
                        provider_location=self.id,
                        hpe_tiramisu=hpe_tiramisu)

                LOG.debug("replication_flag: %(flag)s",
                          {'flag': replication_flag})

                return model_update

        except flowkit_exceptions.HTTPForbidden as ex:
            raise exception.NotAuthorized() from ex
        except flowkit_exceptions.HTTPNotFound as ex:
            raise exception.NotFound() from ex
        except Exception as ex:
            LOG.error("Exception: %s", ex)
            raise exception.CinderException(ex) from ex
        
    
    def enable_replication(self, context, group, volumes):
        """Enable replication for a group.

        :param context: the context
        :param group: the group object
        :param volumes: the list of volumes
        :returns: model_update, None
        """
        LOG.debug("enable_replication called")
        self.session_mgr.ensure_session()
        model_update = {}
        if not group.is_replicated:
            raise NotImplementedError()

        if not volumes:
            # Return if empty group
            return model_update, None

        try:
            vvs_name = self._get_3par_vvs_name(group.id)
            rcg_name = self._get_3par_rcg_name_of_group(group.id)

            # Check VV and RCG exist on 3par,
            # if RCG exist then start RCG
            super().get_volumeset(vvs_name)

            super().start_remote_copy_group(rcg_name)
        except flowkit_exceptions.HTTPNotFound as ex:
            ex_str = str(ex)
            LOG.debug("flowkit HTTPNotFound: %s", ex_str)
            # The remote-copy group does not exist or
            # set does not exist.
            if (str(constants.API_ERROR_187) in ex_str or str(constants.API_ERROR_102) in ex_str):
                raise exception.GroupNotFound(group_id=group.id) from ex
        except flowkit_exceptions.HTTPForbidden as ex:
            ex_str = str(ex)
            LOG.debug("flowkit HTTPForbidden: %s", ex_str)
            # The remote-copy group has already been started.
            if str(constants.API_ERROR_215) in ex_str:
                pass
        except Exception as ex:
            model_update.update({
                'replication_status': fields.ReplicationStatus.ERROR})
            LOG.error("Error enabling replication on group %(group)s. "
                      "Exception received: %(e)s.",
                      {'group': group.id, 'e': ex})

        LOG.debug("enable_replication success")
        return model_update, None
    

    def disable_replication(self, context, group, volumes):
        """Disable replication for a group.

        :param context: the context
        :param group: the group object
        :param volumes: the list of volumes
        :returns: model_update, None
        """

        self.session_mgr.ensure_session()
        model_update = {}
        if not group.is_replicated:
            raise NotImplementedError()

        if not volumes:
            # Return if empty group
            return model_update, None

        try:
            vvs_name = self._get_3par_vvs_name(group.id)
            rcg_name = self._get_3par_rcg_name_of_group(group.id)

            # Check VV and RCG exist on 3par,
            # if RCG exist then stop RCG
            super().get_volumeset(vvs_name)
            super().stop_remote_copy_group(rcg_name)
        except flowkit_exceptions.HTTPNotFound as ex:
            ex_str = str(ex)
            LOG.debug("flowkit HTTPNotFound: %s", ex_str)
            # The remote-copy group does not exist or
            # set does not exist.
            if (str(constants.API_ERROR_187) in ex_str or str(constants.API_ERROR_102) in ex_str):
                raise exception.GroupNotFound(group_id=group.id) from ex

        except Exception as ex:
            model_update.update({
                'replication_status': fields.ReplicationStatus.ERROR})
            LOG.error("Error disabling replication on group %(group)s. "
                      "Exception received: %(e)s.",
                      {'group': group.id, 'e': ex})

        return model_update, None
    
    # v2 replication methods
    def failover_host(self, context, volumes, secondary_backend_id, groups):
        """Force failover to a secondary replication target."""
        self.session_mgr.ensure_session()
        volume_update_list = []
        group_update_list = []

        # Ensure replication is enabled before we try and failover.
        if not self._replication_enabled:
            msg = _("Issuing a fail-over failed because replication is "
                    "not properly configured.")
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg)

        # We are removing volumes which are part of group,
        # So creating volume_copy before doing that.
        # After failover/failback operation,making volumes as like
        # previous with the help of volume_copy.
        volumes_copy = []
        volumes_copy[:] = volumes

        # Check to see if the user requested to failback.
        if (secondary_backend_id and
           secondary_backend_id == constants.FAILBACK_VALUE):
            failover = False
            target_id = None
            group_target_id = constants.FAILBACK_VALUE
        else:
            # Find the failover target.
            failover_target = None
            for target in self._replication_targets:
                if target['backend_id'] == secondary_backend_id:
                    failover_target = target
                    break
            if not failover_target:
                msg = _("A valid secondary target MUST be specified in order "
                        "to failover.")
                LOG.error(msg)
                raise exception.InvalidReplicationTarget(reason=msg)
            failover = True
            target_id = failover_target['backend_id']
            group_target_id = target_id

        if groups:
            for group in groups:
                vol_list = []
                vols_obj = []
                for index, vol in enumerate(volumes):
                    if vol.get('group_id') == group.id:
                        vols_obj.append(vol)
                        vol_list.append(volumes[index])

                for vol_obj in vols_obj:
                    # Remove volumes which are part of a group.
                    volumes.remove(vol_obj)

                grp_update, vol_updates = (
                    self.failover_replication(
                        None, group, vol_list, group_target_id, host=True))
                group_update_list.append({'group_id': group.id,
                                          'updates': grp_update})
                volume_update_list += vol_updates

        # user requested failback.
        if not failover:
            vol_updates = self._replication_failback(volumes)
            volume_update_list += vol_updates

        # user requested failover.
        else:
            # For each volume, if it is replicated, we want to fail it over.
            for volume in volumes:
                if self._volume_of_replicated_type(volume,
                                                   hpe_tiramisu_check=True):
                    repl_session_mgr = None
                    try:
                        # Try and stop remote-copy on main array. We eat the
                        # exception here because when an array goes down, the
                        # groups will stop automatically.
                        rcg_name = self._get_3par_rcg_name(volume)
                        super().stop_remote_copy_group(rcg_name)
                    except Exception:
                        pass

                    try:
                        # Failover to secondary array.
                        remote_rcg_name = self._get_3par_remote_rcg_name(
                            volume, volume['provider_location'])
                        LOG.debug("remote_rcg_name: %(rcg)s", {'rcg': remote_rcg_name})

                        repl_session_mgr = self._create_replication_client(failover_target)
                        LOG.debug("repl_session_mgr: %(session token)s", {'session token': repl_session_mgr.token})

                        rcg_wf = RemoteCopyGroupWorkflow(repl_session_mgr, None)

                        # Check whether this remote copy group has already
                        # been failed over by looking at the target roles.
                        remote_rcg = rcg_wf.get_remote_copy_group(remote_rcg_name)
                        already_failed_over = any(
                            t.get('roleReversed') for t in remote_rcg.get('targets', [])
                        )

                        if already_failed_over:
                            LOG.info("Remote copy group %(rcg)s for volume %(volume)s is "
                                     "already in failed-over state; skipping backend "
                                     "failover action.",
                                     {'rcg': remote_rcg_name, 'volume': volume['id']})
                        else:
                            LOG.debug("Failing over remote copy group %(rcg)s for volume %(volume)s.",
                                      {'rcg': remote_rcg_name, 'volume': volume['id']})
                            rcg_wf.recover_remote_copy_group_from_disaster(
                                remote_rcg_name, constants.RC_ACTION_CHANGE_TO_PRIMARY)
                        volume_update_list.append(
                            {'volume_id': volume['id'],
                             'updates': {'replication_status': 'failed-over',
                                         'replication_driver_data':
                                         failover_target['id']}})
                    except Exception as ex:
                        LOG.error("There was a problem with the failover "
                                  "(%(error)s) and it was unsuccessful. "
                                  "Volume '%(volume)s will not be available "
                                  "on the failed over target.",
                                  {'error': ex,
                                   'volume': volume['id']})
                        volume_update_list.append(
                            {'volume_id': volume['id'],
                             'updates': {'replication_status': 'error'}})
                    finally:
                        if repl_session_mgr is not None:
                            self._destroy_replication_client(repl_session_mgr)
                else:
                    # If the volume is not of replicated type, we need to
                    # force the status into error state so a user knows they
                    # do not have access to the volume.
                    volume_update_list.append(
                        {'volume_id': volume['id'],
                         'updates': {'status': 'error'}})

        volumes[:] = volumes_copy
        return target_id, volume_update_list, group_update_list
    
    def manage_existing_snapshot(self, snapshot, existing_ref):
        """Manage an existing 3PAR snapshot.

        existing_ref is a dictionary of the form:
        {'source-name': <name of the snapshot>}
        """
        self.session_mgr.ensure_session()
        # Potential parent volume for the snapshot
        volume = snapshot['volume']

        # Do not allow for managing of snapshots for 'failed-over' volumes.
        if volume.get('replication_status') == 'failed-over':
            err = (_("Managing of snapshots to failed-over volumes is "
                     "not allowed."))
            raise exception.InvalidInput(reason=err)

        target_snap_name = self._get_existing_volume_ref_name(existing_ref,
                                                              is_snapshot=True)

        # Check for the existence of the snapshot.
        try:
            snap = super().get_volume(target_snap_name)
        except flowkit_exceptions.HTTPNotFound as ex:
            err = (_("Snapshot '%s' doesn't exist on array.") %
                   target_snap_name)
            LOG.error(err)
            raise exception.InvalidInput(reason=err) from ex

        # Make sure the snapshot is being associated with the correct volume.
        parent_vol_name = self._get_3par_vol_name(volume)
        if parent_vol_name != snap['copyOf']:
            err = (_("The provided snapshot '%s' is not a snapshot of "
                     "the provided volume.") % target_snap_name)
            LOG.error(err)
            raise exception.InvalidInput(reason=err)

        new_comment = {}

        # Use the display name from the existing snapshot if no new name
        # was chosen by the user.
        if snapshot['display_name']:
            display_name = snapshot['display_name']
            new_comment['display_name'] = snapshot['display_name']
        elif 'comment' in snap:
            display_name = self._get_3par_vol_comment_value(snap['comment'],
                                                            'display_name')
            if display_name:
                new_comment['display_name'] = display_name
        else:
            display_name = None

        # Generate the new snapshot information based on the new ID.
        new_snap_name = self._get_3par_snap_name(snapshot['id'])
        new_comment['volume_id'] = volume['id']
        new_comment['volume_name'] = 'volume-' + volume['id']
        self._add_name_id_to_comment(new_comment, volume)
        if snapshot.get('display_description', None):
            new_comment['description'] = snapshot['display_description']
        else:
            new_comment['description'] = ""

        new_vals = {'newName': new_snap_name,
                    'comment': json.dumps(new_comment)}

        # Update the existing snapshot with the new name and comments.
        super().modify_volume(target_snap_name, new_vals)

        LOG.info("Snapshot '%(ref)s' renamed to '%(new)s'.",
                 {'ref': existing_ref['source-name'], 'new': new_snap_name})

        updates = {'display_name': display_name}

        LOG.info("Snapshot %(disp)s '%(new)s' is now being managed.",
                 {'disp': display_name, 'new': new_snap_name})

        # Return display name to update the name displayed in the GUI.
        return updates
    
    def manage_existing_snapshot_get_size(self, snapshot, existing_ref):
        """Return size of snapshot to be managed by manage_existing_snapshot.

        existing_ref is a dictionary of the form:
        {'source-name': <name of the snapshot>}
        """
        self.session_mgr.ensure_session()
        target_snap_name = self._get_existing_volume_ref_name(existing_ref,
                                                              is_snapshot=True)

        # Make sure the reference is not in use.
        if re.match('osv-*|oss-*|vvs-*|unm-*', target_snap_name):
            reason = _("Reference must be for an unmanaged snapshot.")
            raise exception.ManageExistingInvalidReference(
                existing_ref=target_snap_name,
                reason=reason)

        # Check for the existence of the snapshot.
        try:
            snap = super().get_volume(target_snap_name)
        except flowkit_exceptions.HTTPNotFound as ex:
            err = (_("Snapshot '%s' doesn't exist on array.") %
                   target_snap_name)
            LOG.error(err)
            raise exception.InvalidInput(reason=err) from ex

        return int(math.ceil(float(snap['sizeMiB']) / units.Ki))
    
    
    def unmanage_snapshot(self, snapshot):
        """Removes the specified snapshot from Cinder management."""
        self.session_mgr.ensure_session()
        # Parent volume for the snapshot
        volume = snapshot['volume']

        # Do not allow unmanaging of snapshots from 'failed-over' volumes.
        if volume.get('replication_status') == 'failed-over':
            err = (_("Unmanaging of snapshots from failed-over volumes is "
                     "not allowed."))
            LOG.error(err)
            # TODO(leeantho) Change this exception to Invalid when the volume
            # manager supports handling that.
            raise exception.SnapshotIsBusy(snapshot_name=snapshot['id'])

        # Rename the snapshots's name to ums-* format so that it can be
        # easily found later.
        snap_name = self._get_3par_snap_name(snapshot['id'])
        new_snap_name = self._get_3par_ums_name(snapshot['id'])
        super().modify_volume(snap_name, {'newName': new_snap_name})

        LOG.info("Snapshot %(disp)s '%(vol)s' is no longer managed. "
                 "Snapshot renamed to '%(new)s'.",
                 {'disp': snapshot['display_name'],
                  'vol': snap_name,
                  'new': new_snap_name})
        

    def get_manageable_snapshots(self, cinder_snapshots, marker, limit, offset,
                                 sort_keys, sort_dirs):
        self.session_mgr.ensure_session()
        already_managed = {}
        for snap_obj in cinder_snapshots:
            cinder_snap_id = snap_obj.id
            snap_name = self._get_3par_snap_name(cinder_snap_id)
            already_managed[snap_name] = cinder_snap_id

        cinder_cpg = self._client_conf['hpe3par_cpg'][0]

        cpg_volumes = []
        all_volumes = super().list_volumes()
        for vol in all_volumes:
            cpg = vol.get('userCPG')
            if cpg == cinder_cpg:
                cpg_volumes.append(vol)

        manageable_snaps = []

        for vol in cpg_volumes:
            size_gb = int(vol['sizeMiB'] / 1024)
            snapshots = super().get_snapshots_of_volume(cinder_cpg,
                                                         vol['name'])
            for snap_name in snapshots:
                if snap_name in already_managed:
                    is_safe = False
                    reason_not_safe = _('Snapshot already managed')
                    cinder_snap_id = already_managed[snap_name]
                else:
                    is_safe = True
                    reason_not_safe = None
                    cinder_snap_id = None

                manageable_snaps.append({
                    'reference': {'name': snap_name},
                    'size': size_gb,
                    'safe_to_manage': is_safe,
                    'reason_not_safe': reason_not_safe,
                    'cinder_id': cinder_snap_id,
                    'source_reference': {'name': vol['name']},
                })

        return volume_utils.paginate_entries_list(
            manageable_snaps, marker, limit, offset, sort_keys, sort_dirs)
    
    
    def _replication_failback(self, volumes):
        # Make sure the proper steps on the backend have been completed before
        # we allow a fail-over.
        if not self._is_host_ready_for_failback(volumes):
            msg = _("The host is not ready to be failed back. Please "
                    "resynchronize the volumes and resume replication on the "
                    "3PAR backends.")
            LOG.error(msg)
            raise exception.InvalidReplicationTarget(reason=msg)

        # Update the volumes status to available.
        volume_update_list = []
        for volume in volumes:
            if self._volume_of_replicated_type(volume,
                                               hpe_tiramisu_check=True):
                volume_update_list.append(
                    {'volume_id': volume['id'],
                     'updates': {'replication_status': 'available',
                                 'replication_driver_data': self.id}})
            else:
                # Upon failing back, we can move the non-replicated volumes
                # back into available state.
                volume_update_list.append(
                    {'volume_id': volume['id'],
                     'updates': {'status': 'available'}})

        return volume_update_list
    
    def _is_host_ready_for_failback(self, volumes):
        """Checks to make sure the volume has been synchronized

        This ensures that all the remote copy targets have been restored
        to their natural direction, and all of the volumes have been
        fully synchronized.
        """
        try:
            for volume in volumes:
                if self._volume_of_replicated_type(volume,
                                                   hpe_tiramisu_check=True):
                    location = volume.get('provider_location')
                    remote_rcg_name = self._get_3par_remote_rcg_name(volume,
                                                                     location)
                    rcg = super().get_remote_copy_group(remote_rcg_name)
                    LOG.debug("rcg_info: %(rcg_info)s", {'rcg_info': rcg})
                    if not self._are_targets_in_their_natural_direction(rcg):
                        LOG.debug("Remote copy group %(rcg)s for volume %(volume)s is "
                                  "not in its natural direction.",
                                  {'rcg': remote_rcg_name, 'volume': volume['id']})
                        return False

        except Exception:
            # If there was a problem, we will return false so we can
            # log an error in the parent function.
            return False

        return True
    

    def failover_replication(self, context, group, volumes,
                             secondary_backend_id=None, host=False):
        """Failover replication for a group.

        :param context: the context
        :param group: the group object
        :param volumes: the list of volumes
        :param secondary_backend_id: the secondary backend id - default None
        :param host: flag to indicate if whole host is being failed over
        :returns: model_update, None
        """

        self.session_mgr.ensure_session()
        model_update = {}
        vol_model_updates = []
        failover_target = None
        failback_target = None
        rep_data = None
        if not group.is_replicated:
            raise NotImplementedError()

        if not volumes:
            # Return if empty group
            return model_update, vol_model_updates

        if not self._replication_enabled:
            msg = _("Issuing a fail-over failed because replication is "
                    "not properly configured.")
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg)
        try:
            provider_location = volumes[0].get('provider_location')
            replication_driver_data = volumes[0].get('replication_driver_data')

            failover = False if secondary_backend_id == 'default' else True

            if failover:
                # Find the failover target.
                for target in self._replication_targets:
                    if target['backend_id'] == secondary_backend_id:
                        failover_target = target
                        break
                if not failover_target:
                    msg = _("A valid secondary target MUST be specified "
                            "in order to failover.")
                    LOG.error(msg)
                    raise exception.InvalidReplicationTarget(reason=msg)

                self._group_failover_replication(failover_target, group,
                                                 provider_location)
                model_update.update({
                    'replication_status':
                        fields.ReplicationStatus.FAILED_OVER})
                vol_rep_status = fields.ReplicationStatus.FAILED_OVER
            else:
                # Find the failback target.
                for target in self._replication_targets:
                    if target['id'] == replication_driver_data:
                        failback_target = target
                        break
                if not failback_target:
                    msg = _("A valid target is not found "
                            "in order to failback.")
                    LOG.error(msg)
                    raise exception.InvalidReplicationTarget(reason=msg)
                self._group_failback_replication(failback_target, group,
                                                 provider_location)
                model_update.update({
                    'replication_status': fields.ReplicationStatus.ENABLED})
                vol_rep_status = fields.ReplicationStatus.ENABLED

        except Exception as ex:
            model_update.update({
                'replication_status': fields.ReplicationStatus.ERROR})
            vol_rep_status = fields.ReplicationStatus.ERROR
            LOG.error("Error failover replication on group %(group)s. "
                      "Exception received: %(e)s.",
                      {'group': group.id, 'e': ex})

        if failover_target:
            rep_data = failover_target.get('id')
        elif failback_target:
            rep_data = failback_target.get('id')
        
        for vol in volumes:
            loc = vol.get('provider_location')
            update = {'id': vol.get('id'),
                      'replication_status': vol_rep_status,
                      'provider_location': loc,
                      'replication_driver_data': rep_data}
            if host:
                update = {'volume_id': vol.get('id'), 'updates': update}
            vol_model_updates.append(update)
        return model_update, vol_model_updates

    def _create_temp_snapshot(self, volume):
        """This creates a temporary snapshot of a volume.

        This is used by cloning a volume so that we can then
        issue extend volume against the original volume.
        """
        vol_name = self._get_3par_vol_name(volume)
        # create a brand new uuid for the temp snap
        snap_uuid = uuid.uuid4().hex

        # this will be named tss-%s
        snap_name = self._get_3par_snap_name(snap_uuid, temp_snap=True)

        extra = {'volume_name': volume['name'],
                 'volume_id': volume['id']}
        self._add_name_id_to_comment(extra, volume)

        optional = {'comment': json.dumps(extra)}

        # let the snapshot die in an hour
        optional['expirationHours'] = 1

        LOG.info("Creating temp snapshot %(snap)s from volume %(vol)s",
                 {'snap': snap_name, 'vol': vol_name})
        
        super().create_snapshot(vol_name, snap_name, optional)

        return super().get_volume(snap_name)
    

    def isOnlinePhysicalCopy(self, name):
        """Is the volume being created by process of online copy?

        :param name: the name of the volume
        :type name: str

        """
        task = self._findTask(name, active=True)
        if task is None:
            return False
        else:
            return True   
        
    
    def _findTask(self, name, active=True):
        body = super().getTasks()

        task_type = {1: 'vv_copy', 2: 'phys_copy_resync', 3: 'move_regions',
                     4: 'promote_sv', 5: 'remote_copy_sync',
                     6: 'remote_copy_reverse', 7: 'remote_copy_failover',
                     8: 'remote_copy_recover', 18: 'online_vv_copy'}

        status = {1: 'done', 2: 'active', 3: 'cancelled', 4: 'failed'}

        priority = {1: 'high', 2: 'med', 3: 'low'}

        for task_obj in body['members']:
            if(task_obj['name'] == name):
                if(active and task_obj['status'] != 2):
                    # if active flag is True, but status of task is not True
                    # then it means task got completed/cancelled/failed
                    return None

                task_details = []
                task_details.append(task_obj['id'])

                value = task_obj['type']
                if value in task_type:
                    type_str = task_type[value]
                else:
                    type_str = 'n/a'
                task_details.append(type_str)

                task_details.append(task_obj['name'])

                value = task_obj['status']
                task_details.append(status[value])

                # Phase and Step feilds are not found
                task_details.append('---')
                task_details.append('---')
                task_details.append(task_obj['startTime'])
                task_details.append(task_obj['finishTime'])

                if('priority' in task_obj):
                    value = task_obj['priority']
                    task_details.append(priority[value])
                else:
                    task_details.append('n/a')

                task_details.append(task_obj['user'])

                return task_details

        return None
    
    
    def stopOnlinePhysicalCopy(self, name):
        """Stopping a online physical copy operation.

        :param name: the name of the volume
        :type name: str

        """
        # first we have to find the active copy
        task = self._findTask(name)
        task_id = None
        if task is None:
            # couldn't find the task
            super().delete_volume(name)
            msg = "Couldn't find the copy task for '%s'" % name
            raise flowkit_exceptions.HTTPNotFound(error={'desc': msg})
        else:
            task_id = task[0]

        # now stop the copy
        if task_id is not None:
            super().cancelTask(task_id)
        else:
            super().delete_volume(name)
            msg = "Couldn't find the copy task for '%s'" % name
            raise flowkit_exceptions.HTTPNotFound(error={'desc': msg})

        # we have to make sure the task is cancelled
        # before moving on. This can sometimes take a while.
        ready = False
        while not ready:
            time.sleep(1)
            task = self._findTask(name, True)
            if task is None:
                ready = True

        # now cleanup the dead snapshots
        vol = super().get_volume(name)
        if vol:
            if 'copyOf' in vol:
                snap1 = super().get_volume(vol['copyOf'])
                snap2 = super().get_volume(snap1['copyOf'])
            super().delete_volume(name)
            if 'copyOf' in vol:
                super().delete_volume(snap1['name'])
                super().delete_volume(snap2['name'])


    @staticmethod
    def _add_name_id_to_comment(comment, volume):
        name_id = volume.get('_name_id')
        if name_id:
            comment['_name_id'] = name_id

    def _get_updated_comment(self, vol_name, **values):
        vol = super().get_volume(vol_name)

        comment = json.loads(vol['comment']) if vol.get('comment') else {}
        comment.update(values)
        return json.dumps(comment)

    def _update_comment(self, vol_name, **values):
        """Update key-value pairs on the comment of a volume in the backend."""
        if not values:
            return

        comment = self._get_updated_comment(vol_name, **values)
        super().modify_volume(vol_name, {'comment': json.dumps(comment)})

    def _wait_for_task_completion(self, task_id):
        """This waits for array background task complete or fail.

        This looks for a task to get out of the 'active' state.
        """
        # Wait for the physical copy task to complete
        def _wait_for_task(task_id, wf):
            details = wf.getTask(task_id)

            status = details['status']
            LOG.debug("3PAR Task id %(id)s status = %(status)s",
                      {'id': task_id,
                       'status': status})
            if status is not constants.TASK_ACTIVE:
                self._task_details = details
                raise loopingcall.LoopingCallDone()

        task_wf = TaskManager(self.session_mgr)
        self._task_details = None
        timer = loopingcall.FixedIntervalLoopingCall(
            _wait_for_task, task_id, task_wf)
        timer.start(interval=1).wait()

        return self._task_details

    def _convert_to_base_volume(self, volume, new_cpg=None):
        try:
            type_info = self.get_volume_settings_from_type(volume)
            if new_cpg:
                cpg = new_cpg
            else:
                cpg = type_info['cpg']

            # Change the name such that it is unique since 3PAR
            # names must be unique across all CPGs
            volume_name = self._get_3par_vol_name(volume)
            temp_vol_name = volume_name.replace("osv-", "omv-")

            compression = self.get_compression_policy(
                type_info['hpe3par_keys'])

            # If volume (osv-) has snapshot, while converting the volume
            # to base volume (omv-), snapshot cannot be transferred to
            # new base volume (omv-) i.e it remain with volume (osv-).
            # So error out for such volume.
            snap_list = super().getVolumeSnapshots(volume_name)
            if snap_list:
                snap_str = ",".join(snap_list)
                msg = (_("Volume %(name)s has dependent snapshots: %(snap)s."
                         " Either flatten or remove the dependent snapshots:"
                         " %(snap)s for the conversion of volume %(name)s to"
                         " succeed." % {'name': volume_name,
                                        'snap': snap_str}))
                raise exception.VolumeIsBusy(message=msg)

            # Create a physical copy of the volume
            task_id = self._copy_volume(volume_name, temp_vol_name,
                                        cpg, cpg, type_info['tpvv'],
                                        type_info['tdvv'],
                                        compression)

            LOG.debug('Copy volume scheduled: convert_to_base_volume: '
                      'id=%s.', volume['id'])

            task_details = self._wait_for_task_completion(task_id)

            if task_details['status'] is not constants.TASK_DONE:
                dbg = {'details': task_details, 'id': volume['id']}
                msg = _('Copy volume task failed: convert_to_base_volume: '
                        'id=%(id)s, details=%(details)s.') % dbg
                raise exception.CinderException(msg)
            else:
                LOG.debug('Copy volume completed: convert_to_base_volume: '
                          'id=%s.', volume['id'])

            comment = self._get_3par_vol_comment(volume_name)
            if comment:
                super().modify_volume(temp_vol_name, {'comment': comment})
                LOG.debug('Assigned the comment: convert_to_base_volume: '
                          'id=%s.', volume['id'])

            # Delete source volume (osv-) after the copy is complete
            super().delete_volume(volume_name)
            LOG.debug('Delete src volume completed: convert_to_base_volume: '
                      'id=%s.', volume['id'])

            # Rename the new volume (omv-) to the original name (osv-)
            super().modify_volume(temp_vol_name, {'newName': volume_name})
            LOG.debug('Volume rename completed: convert_to_base_volume: '
                      'id=%s.', volume['id'])

            LOG.info('Completed: convert_to_base_volume: '
                     'id=%s.', volume['id'])
        except flowkit_exceptions.HTTPConflict:
            msg = _("Volume (%s) already exists on array.") % temp_vol_name
            LOG.error(msg)
            raise exception.Duplicate(msg)
        except flowkit_exceptions.HTTPBadRequest as ex:
            LOG.error("Exception: %s", ex)
            raise exception.Invalid(ex.get_description())
        except exception.CinderException as ex:
            LOG.error("Exception: %s", ex)
            raise
        except Exception as ex:
            LOG.error("Exception: %s", ex)
            raise exception.CinderException(ex)

        return self._get_model_update(volume['host'], cpg)

    def _do_replication_setup(self, array_id=None):
        replication_targets = []
        replication_devices = self.config.replication_device
        if replication_devices:
            for dev in replication_devices:
                remote_array = dict(dev.items())
                # Override and set defaults for certain entries
                remote_array['managed_backend_name'] = (
                    dev.get('managed_backend_name'))
                remote_array['replication_mode'] = (
                    self._get_remote_copy_mode_num(
                        dev.get('replication_mode')))
                remote_array['san_ssh_port'] = (
                    dev.get('san_ssh_port', self.config.san_ssh_port))
                remote_array['ssh_conn_timeout'] = (
                    dev.get('ssh_conn_timeout', self.config.ssh_conn_timeout))
                remote_array['san_private_key'] = (
                    dev.get('san_private_key', self.config.san_private_key))
                # Format iscsi IPs correctly
                iscsi_ips = dev.get('hpe3par_iscsi_ips')
                if iscsi_ips:
                    remote_array['hpe3par_iscsi_ips'] = iscsi_ips.split(' ')
                # Format hpe3par_iscsi_chap_enabled as a bool
                remote_array['hpe3par_iscsi_chap_enabled'] = (
                    dev.get('hpe3par_iscsi_chap_enabled') == 'True')
                array_name = remote_array['backend_id']

                # Make sure we can log into the array, that it has been
                # correctly configured, and its API version meets the
                # minimum requirement.
                try:
                    repl_session_mgr =  self._create_replication_client(remote_array)
                    system_wf = SystemWorkflow(repl_session_mgr)
                    info = system_wf.get_storage_system_info()
                    remote_array['id'] = str(info['id'])
                    if array_id and array_id == info['id']:
                        self._active_backend_id = str(info['name'])

                    if not self._is_valid_replication_array(remote_array):
                        LOG.warning("'%s' is not a valid replication array. "
                                    "In order to be valid, backend_id, "
                                    "replication_mode, "
                                    "hpe3par_api_url, hpe3par_username, "
                                    "hpe3par_password, cpg_map, san_ip, "
                                    "san_login, and san_password "
                                    "must be specified. If the target is "
                                    "managed, managed_backend_name must be "
                                    "set as well.", array_name)
                    else:
                        replication_targets.append(remote_array)
                except Exception:
                    LOG.error("Could not log in to 3PAR array (%s) with the "
                              "provided credentials.", array_name)
                finally:
                    self._destroy_replication_client(repl_session_mgr)

            self._replication_targets = replication_targets
            if self._is_replication_configured_correct():
                self._replication_enabled = True

    def _is_valid_replication_array(self, target):
        required_flags = ['hpe3par_api_url', 'hpe3par_username',
                          'hpe3par_password', 'san_ip', 'san_login',
                          'san_password', 'backend_id',
                          'replication_mode', 'cpg_map']
        try:
            self.check_replication_flags(target, required_flags)
            return True
        except Exception:
            return False

    def _is_replication_configured_correct(self):
        rep_flag = True
        # Make sure there is at least one replication target.
        if len(self._replication_targets) < 1:
            LOG.error("There must be at least one valid replication "
                      "device configured.")
            rep_flag = False
        return rep_flag

    def _is_replication_mode_correct(self, mode, sync_num):
        rep_flag = True
        # Make sure replication_mode is set to either sync|periodic.
        mode = self._get_remote_copy_mode_num(mode)
        if not mode:
            LOG.error("Extra spec replication:mode must be set and must "
                      "be either 'sync' or 'periodic'.")
            rep_flag = False
        else:
            # If replication:mode is periodic, replication_sync_period must be
            # set between 300 - 31622400 seconds.
            if mode == constants.PERIODIC and (
               sync_num < 300 or sync_num > 31622400):
                LOG.error("Extra spec replication:sync_period must be "
                          "greater than 299 and less than 31622401 "
                          "seconds.")
                rep_flag = False
        return rep_flag

    def is_volume_group_snap_type(self, volume_type):
        consis_group_snap_type = False
        if volume_type:
            extra_specs = volume_type.get('extra_specs')
            if 'consistent_group_snapshot_enabled' in extra_specs:
                gsnap_val = extra_specs['consistent_group_snapshot_enabled']
                consis_group_snap_type = (gsnap_val == "<is> True")
        return consis_group_snap_type

    def _volume_of_replicated_type(self, volume, hpe_tiramisu_check=None):
        replicated_type = False
        volume_type_id = volume.get('volume_type_id')
        if volume_type_id:
            volume_type = self._get_volume_type(volume_type_id)

            extra_specs = volume_type.get('extra_specs')
            if extra_specs and 'replication_enabled' in extra_specs:
                rep_val = extra_specs['replication_enabled']
                replicated_type = (rep_val == "<is> True")

            if hpe_tiramisu_check and replicated_type:
                hpe3par_tiramisu = self._get_hpe3par_tiramisu_value(
                    volume_type)
                if hpe3par_tiramisu:
                    replicated_type = False
        
        LOG.debug("replicated_type: %(flag)s", {'flag': replicated_type})
        return replicated_type

    def _volume_of_hpe_tiramisu_type(self, volume):
        hpe_tiramisu_type = False
        replicated_type = False
        volume_type_id = volume.get('volume_type_id')
        if volume_type_id:
            volume_type = self._get_volume_type(volume_type_id)

            extra_specs = volume_type.get('extra_specs')
            if extra_specs and 'replication_enabled' in extra_specs:
                rep_val = extra_specs['replication_enabled']
                replicated_type = (rep_val == "<is> True")

            if replicated_type:
                hpe3par_tiramisu = self._get_hpe3par_tiramisu_value(
                    volume_type)
                if hpe3par_tiramisu:
                    hpe_tiramisu_type = True

        return hpe_tiramisu_type

    def _volume_of_hpe_tiramisu_type_and_part_of_group(self, volume):
        volume_part_of_group = False
        hpe_tiramisu_type = self._volume_of_hpe_tiramisu_type(volume)
        if hpe_tiramisu_type:
            if volume.get('group'):
                volume_part_of_group = True
        return volume_part_of_group

    def _is_volume_type_replicated(self, volume_type):
        replicated_type = False
        extra_specs = volume_type.get('extra_specs')
        if extra_specs and 'replication_enabled' in extra_specs:
            rep_val = extra_specs['replication_enabled']
            replicated_type = (rep_val == "<is> True")

        return replicated_type

    def _is_volume_in_remote_copy_group(self, volume):
        rcg_name = self._get_3par_rcg_name(volume)
        try:
            super().get_remote_copy_group(rcg_name)
            return True
        except flowkit_exceptions.HPEStorageException:
            return False

    def _get_remote_copy_mode_num(self, mode):
        ret_mode = None
        if mode == "sync":
            ret_mode = constants.SYNC
        if mode == "periodic":
            ret_mode = constants.PERIODIC
        return ret_mode

    def _get_3par_config(self, array_id=None):
        self._do_replication_setup(array_id=array_id)
        conf = None
        if self._replication_enabled:
            for target in self._replication_targets:
                if target['backend_id'] == self._active_backend_id:
                    conf = target
                    break
        self._build_3par_config(conf)

    def _build_3par_config(self, conf=None):
        """Build 3PAR client config dictionary.

        self._client_conf will contain values from self.config if the volume
        is located on the primary array in order to properly contact it. If
        the volume has been failed over and therefore on a secondary array,
        self._client_conf will contain values on how to contact that array.
        The only time we will return with entries from a secondary array is
        with unmanaged replication.
        """
        if conf:
            self._client_conf['hpe3par_cpg'] = self._generate_hpe3par_cpgs(
                conf.get('cpg_map'))
            self._client_conf['hpe3par_username'] = (
                conf.get('hpe3par_username'))
            self._client_conf['hpe3par_password'] = (
                conf.get('hpe3par_password'))
            self._client_conf['san_ip'] = conf.get('san_ip')
            self._client_conf['san_login'] = conf.get('san_login')
            self._client_conf['san_password'] = conf.get('san_password')
            self._client_conf['san_ssh_port'] = conf.get('san_ssh_port')
            self._client_conf['ssh_conn_timeout'] = (
                conf.get('ssh_conn_timeout'))
            self._client_conf['san_private_key'] = conf.get('san_private_key')
            self._client_conf['hpe3par_api_url'] = conf.get('hpe3par_api_url')
            self._client_conf['hpe3par_iscsi_ips'] = (
                conf.get('hpe3par_iscsi_ips'))
            self._client_conf['hpe3par_iscsi_chap_enabled'] = (
                conf.get('hpe3par_iscsi_chap_enabled'))
            self._client_conf['iscsi_ip_address'] = (
                conf.get('target_ip_address'))
            self._client_conf['iscsi_port'] = conf.get('iscsi_port')
        else:
            self._client_conf['hpe3par_cpg'] = (
                self.config.hpe3par_cpg)
            self._client_conf['hpe3par_username'] = (
                self.config.hpe3par_username)
            self._client_conf['hpe3par_password'] = (
                self.config.hpe3par_password)
            self._client_conf['san_ip'] = self.config.san_ip
            self._client_conf['san_login'] = self.config.san_login
            self._client_conf['san_password'] = self.config.san_password
            self._client_conf['san_ssh_port'] = self.config.san_ssh_port
            self._client_conf['ssh_conn_timeout'] = (
                self.config.ssh_conn_timeout)
            self._client_conf['san_private_key'] = self.config.san_private_key
            self._client_conf['hpe3par_api_url'] = self.config.hpe3par_api_url
            self._client_conf['hpe3par_iscsi_ips'] = (
                self.config.hpe3par_iscsi_ips)
            self._client_conf['hpe3par_iscsi_chap_enabled'] = (
                self.config.hpe3par_iscsi_chap_enabled)
            self._client_conf['iscsi_ip_address'] = (
                self.config.target_ip_address)
            self._client_conf['iscsi_port'] = self.config.target_port
            self._client_conf['hpe3par_nvme_ips'] = (
                self.config.hpe3par_nvme_ips)

    def _get_cpg_from_cpg_map(self, cpg_map, target_cpg):
        ret_target_cpg = None
        cpg_pairs = cpg_map.split(' ')
        for cpg_pair in cpg_pairs:
            cpgs = cpg_pair.split(':')
            cpg = cpgs[0]
            dest_cpg = cpgs[1]
            if cpg == target_cpg:
                ret_target_cpg = dest_cpg

        return ret_target_cpg

    def _generate_hpe3par_cpgs(self, cpg_map):
        hpe3par_cpgs = []
        cpg_pairs = cpg_map.split(' ')
        for cpg_pair in cpg_pairs:
            cpgs = cpg_pair.split(':')
            hpe3par_cpgs.append(cpgs[1])

        return hpe3par_cpgs

    def _set_flash_cache_policy_in_vvs(self, flash_cache, vvs_name):
        # Update virtual volume set
        if flash_cache:
            try:
                super().modifyVolumeSet(vvs_name,
                                         flashCachePolicy=flash_cache)
                LOG.info("Flash Cache policy set to %s", flash_cache)
            except Exception:
                with excutils.save_and_reraise_exception():
                    LOG.error("Error setting Flash Cache policy "
                              "to %s - exception", flash_cache)

    def _add_volume_to_volume_set(self, volume, volume_name,
                                  cpg, vvs_name, qos, flash_cache):
        if vvs_name is not None:
            # Admin has set a volume set name to add the volume to
            try:
                super().addVolumeToVolumeSet(vvs_name, volume_name)
            except flowkit_exceptions.HTTPNotFound:
                msg = _('VV Set %s does not exist.') % vvs_name
                LOG.error(msg)
                raise exception.InvalidInput(reason=msg)
        else:
            vvs_name = self._get_3par_vvs_name(volume['id'])
            domain = self.get_domain(cpg)
            super().createVolumeSet(vvs_name, domain)
            try:
                self._set_qos_rule(qos, vvs_name)
                self._set_flash_cache_policy_in_vvs(flash_cache, vvs_name)
                super().addVolumeToVolumeSet(vvs_name, volume_name)
            except Exception as ex:
                # Cleanup the volume set if unable to create the qos rule
                # or flash cache policy or add the volume to the volume set
                super().delete_volumeset(vvs_name)
                raise exception.CinderException(ex)

    def find_existing_vlun(self, volume, host, remote_client=None):
        """Finds an existing VLUN for a volume on a host.

        Returns an existing VLUN's information. If no existing VLUN is found,
        None is returned.

        :param volume: A dictionary describing a volume.
        :param host: A dictionary describing a host.
        """
        existing_vlun = None
        try:
            vol_name = self._get_3par_vol_name(volume)
            if remote_client:
                # todo
                host_vluns = remote_client.getHostVLUNs(host['name'])
            else:
                host_vluns = super().getHostVLUNs(host['name'])

            # The first existing VLUN found will be returned.
            for vlun in host_vluns:
                if vlun['volumeName'] == vol_name:
                    existing_vlun = vlun
                    break
        except flowkit_exceptions.HTTPNotFound:
            # ignore, host was not found OR VLUNs were not found
            return None

        return existing_vlun

    def find_existing_vluns(self, volume, host, remote_client=None):
        existing_vluns = []
        try:
            vol_name = self._get_3par_vol_name(volume)
            if remote_client:
                # todo
                host_vluns = remote_client.getHostVLUNs(host['name'])
            else:
                host_vluns = super().getHostVLUNs(host['name'])

            for vlun in host_vluns:
                if vlun['volumeName'] == vol_name:
                    existing_vluns.append(vlun)
        except flowkit_exceptions.HTTPNotFound as ex:
            # ignore, no existing VLUNs were found
            LOG.debug("No existing VLUNs were found for host/volume "
                      "combination: %(host)s, %(vol)s,%(exception)s",
                      {'host': host['name'],
                       'vol': vol_name,
                       'exception': ex})
        return existing_vluns

    def get_ports(self):
        self.session_mgr.ensure_session()
        return super().getPorts()

    def get_active_target_ports(self, remote_client=None):
        if remote_client:
            #client_obj = remote_client
            ports = remote_client.get_ports()
        else:
            #client_obj = self.client
            ports = self.get_ports()

        target_ports = []
        for port in ports['members']:
            if (
                port['mode'] == constants.PORT_MODE_TARGET and
                port['linkState'] == constants.PORT_STATE_READY
            ):
                port['nsp'] = self.build_nsp(port['portPos'])
                target_ports.append(port)

        return target_ports

    def get_active_fc_target_ports(self, remote_client=None):
        ports = self.get_active_target_ports(remote_client)

        fc_ports = []
        for port in ports:
            if port['protocol'] == constants.PORT_PROTO_FC:
                fc_ports.append(port)

        return fc_ports

    def get_active_iscsi_target_ports(self, remote_client=None):
        ports = self.get_active_target_ports(remote_client)

        iscsi_ports = []
        for port in ports:
            if port['protocol'] == constants.PORT_PROTO_ISCSI:
                iscsi_ports.append(port)

        return iscsi_ports

    def build_nsp(self, portPos):
        return '%s:%s:%s' % (portPos['node'],
                             portPos['slot'],
                             portPos['cardPort'])

    def build_portPos(self, nsp):
        split = nsp.split(":")
        portPos = {}
        portPos['node'] = int(split[0])
        portPos['slot'] = int(split[1])
        portPos['cardPort'] = int(split[2])
        return portPos

    def _create_3par_vlun(self, vol_name, hostname, nsp, lun_id=None,
                          remote_client=None):
        self.session_mgr.ensure_session()
        vlun_wf = VLUNWorkflow(self.session_mgr)
        # todo:
        # if remote_client
        # create vlun_wf using secondary array

        try:
            if remote_client:
                client_obj = remote_client
            else:
                client_obj = vlun_wf

            params = {}
            if lun_id is not None:
                params['lun'] = lun_id
            else:
                params['autoLun'] = True
                params['maxAutoLun'] = 0
                params['lun'] = 0

            if nsp is not None:
                port = self.build_portPos(nsp)
                params['portPos'] = port

            client_obj.create_vlun(vol_name, hostname, params)

            vlun_info = {'lun_id': None}
            return vlun_info
        except flowkit_exceptions.HPEStorageException as ex:
            LOG.error("Exception creating VLUN for volume %(vol)s on host %(host)s: %(ex)s",
                      {'vol': vol_name, 'host': hostname, 'ex': ex})
            raise exception.VolumeBackendAPIException(data=("Failed to create VLUN for volume %(vol)s ""on host %(host)s: %(ex)s"% {'vol': vol_name, 'host': hostname, 'ex': ex})) from ex

    def _safe_hostname(self, connector, configuration):
        """We have to use a safe hostname length for 3PAR host names."""
        hostname = connector['host']
        unique_fqdn_network = configuration.unique_fqdn_network
        if not unique_fqdn_network and connector.get('initiator'):
            iqn = connector.get('initiator')
            iqn = iqn.replace(":", "-")
            return iqn[::-1][:31]
        else:
            try:
                index = hostname.index('.')
            except ValueError:
                # couldn't find it
                index = len(hostname)

            # we'll just chop this off for now.
            if index > 31:
                index = 31

            return hostname[:index]

    def _get_3par_host(self, hostname):
        LOG.debug("inside _get_3par_host: hostname: %(var)s", {'var': hostname})
        host_wf = HostWorkflow(self.session_mgr)
        return host_wf.get_host(hostname)

    def _get_vlun(self, volume_name, hostname, lun_id=None, nsp=None,
                  remote_client=None):
        """find a VLUN on a 3PAR host."""
        self.session_mgr.ensure_session()
        vlun_wf = VLUNWorkflow(self.session_mgr)
        # todo:
        # if remote_client
        # create vlun_wf using secondary array

        if remote_client:
            vluns = remote_client.getHostVLUNs(hostname)
        else:
            vluns = vlun_wf.getHostVLUNs(hostname)

        found_vlun = None
        for vlun in vluns:
            if volume_name in vlun['volumeName']:
                if lun_id is not None:
                    if vlun['lun'] == lun_id:
                        if nsp:
                            port = self.build_portPos(nsp)
                            if vlun['portPos'] == port:
                                found_vlun = vlun
                                break
                        else:
                            found_vlun = vlun
                            break
                else:
                    found_vlun = vlun
                    break

        if found_vlun is None:
            LOG.info("3PAR vlun %(name)s not found on host %(host)s",
                     {'name': volume_name, 'host': hostname})
        return found_vlun

    def create_vlun(self, volume, host, nsp=None, lun_id=None,
                    remote_client=None):
        """Create a VLUN.

        In order to export a volume on a 3PAR box, we have to create a VLUN.
        """
        self.session_mgr.ensure_session()
        volume_name = self._get_3par_vol_name(volume)
        vlun_info = self._create_3par_vlun(volume_name, host['name'], nsp,
                                           lun_id=lun_id,
                                           remote_client=remote_client)
        return self._get_vlun(volume_name,
                              host['name'],
                              vlun_info['lun_id'],
                              nsp,
                              remote_client)

    def _delete_vlun(self, host_wf, vlun_wf, volume, hostname, wwn=None, iqn=None):
        volume_name = self._get_3par_vol_name(volume)
        if hostname:
            vluns = vlun_wf.getHostVLUNs(hostname)
        else:
            # In case of 'force detach', hostname is None
            vluns = vlun_wf.getVLUNs()['members']

        # When deleteing VLUNs, you simply need to remove the template VLUN
        # and any active VLUNs will be automatically removed.  The template
        # VLUN are marked as active: False

        modify_host = True
        volume_vluns = []

        for vlun in vluns:
            if volume_name in vlun['volumeName']:
                # template VLUNs are 'active' = False
                if not vlun['active']:
                    volume_vluns.append(vlun)

        if not volume_vluns:
            LOG.warning("3PAR vlun for volume %(name)s not found on host "
                        "%(host)s", {'name': volume_name, 'host': hostname})
            return

        # VLUN Type of MATCHED_SET 4 requires the port to be provided
        for vlun in volume_vluns:
            if hostname is None:
                hostname = vlun.get('hostname')
            if 'portPos' in vlun:
                vlun_wf.delete_vlun(volume_name, vlun['lun'],
                                      hostname=hostname,
                                      port=vlun['portPos'])
            else:
                vlun_wf.delete_vlun(volume_name, vlun['lun'],
                                    hostname=hostname)

        # Determine if there are other volumes attached to the host.
        # This will determine whether we should try removing host from host set
        # and deleting the host.
        vluns = []
        try:
            vluns = vlun_wf.getHostVLUNs(hostname)
        except flowkit_exceptions.HTTPNotFound as ex:
            LOG.debug("All VLUNs removed from host %s, exception: %s", hostname, ex)

        if wwn is not None and not isinstance(wwn, list):
            wwn = [wwn]
        if iqn is not None and not isinstance(iqn, list):
            iqn = [iqn]

        for vlun in vluns:
            if vlun.get('active'):
                if (wwn is not None and vlun.get('remoteName').lower() in wwn)\
                    or (iqn is not None and vlun.get('remoteName').lower() in
                        iqn):
                    # vlun with wwn/iqn exists so do not modify host.
                    LOG.debug("vlun with wwn/iqn exists so do not modify host, marking modify_host = False")
                    modify_host = False
                    break

        if len(vluns) == 0:
            # We deleted the last vlun, so try to delete the host too.
            # This check avoids the old unnecessary try/fail when vluns exist
            # but adds a minor race condition if a vlun is manually deleted
            # externally at precisely the wrong time. Worst case is leftover
            # host, so it is worth the unlikely risk.

            try:
                # TODO(sonivi): since multiattach is not supported for now,
                # delete only single host, if its not exported to volume.
                LOG.debug("try to delete host")
                self._delete_3par_host(hostname, host_wf)
            except Exception as ex:
                # Any exception down here is only logged.  The vlun is deleted.

                # If the host is in a host set, the delete host will fail and
                # the host will remain in the host set.  This is desired
                # because cinder was not responsible for the host set
                # assignment.  The host set could be used outside of cinder
                # for future needs (e.g. export volume to host set).

                # The log info explains why the host was left alone.
                LOG.info("3PAR vlun for volume '%(name)s' was deleted, "
                         "but the host '%(host)s' was not deleted "
                         "because: %(reason)s",
                         {'name': volume_name, 'host': hostname,
                          'reason': str(ex)})
        elif modify_host:
            LOG.debug("modify_host is True. try to modify host")
            if wwn is not None:
                mod_request = {'pathOperation': constants.HOST_EDIT_REMOVE,
                               'FCWWNs': wwn}
            else:
                mod_request = {'pathOperation': constants.HOST_EDIT_REMOVE,
                               'iSCSINames': iqn}
            try:
                host_wf.modify_host(hostname, mod_request)
            except Exception as ex:
                LOG.info("3PAR vlun for volume '%(name)s' was deleted, "
                         "but the host '%(host)s' was not Modified "
                         "because: %(reason)s",
                         {'name': volume_name, 'host': hostname,
                          'reason': str(ex)})

    def delete_vlun(self, volume, hostname, wwn=None, iqn=None,
                    remote_client=None):
        self.session_mgr.ensure_session()
        host_wf = HostWorkflow(self.session_mgr)
        vlun_wf = VLUNWorkflow(self.session_mgr)
        self._delete_vlun(host_wf, vlun_wf, volume, hostname, wwn, iqn)
        if remote_client:
            # todo: create host_wf and vlun_wf objects using secondary array
            self._delete_vlun(remote_client, volume, hostname, wwn, iqn)

    def _delete_3par_host(self, hostname, client_obj):
        client_obj.delete_host(hostname)

    def _get_prioritized_host_on_3par(self, host, hosts, hostname):
        # Check whether host with wwn/iqn of initiator present on 3par
        if hosts and hosts['members'] and 'name' in hosts['members'][0]:
            # Retrieving 'host' and 'hosts' from 3par using hostname
            # and wwn/iqn respectively. Compare hostname of 'host' and 'hosts',
            # if they do not match it means 3par has a pre-existing host
            # with some other name.
            if host['name'] != hosts['members'][0]['name']:
                hostname = hosts['members'][0]['name']
                LOG.info(("Prioritize the host retrieved from wwn/iqn "
                          "Hostname : %(hosts)s  is used instead "
                          "of Hostname: %(host)s"),
                         {'hosts': hostname,
                          'host': host['name']})
                host = self._get_3par_host(hostname)
                return host, hostname

        return host, hostname

    def terminate_connection(self, volume, hostname, wwn=None, iqn=None,
                             remote_client=None):
        """Driver entry point to detach a volume from an instance."""
        self.session_mgr.ensure_session()
        if volume.multiattach:
            attachment_list = volume.volume_attachment
            LOG.debug("Volume attachment list: %(atl)s",
                      {'atl': attachment_list})

            try:
                attachment_list = attachment_list.objects
            except AttributeError:
                pass

            if attachment_list is not None and len(attachment_list) > 1:
                # There are two possibilities: the instances can reside:
                # [1] either on same host.
                # [2] or on different hosts.
                #
                # case [1]:
                # In such case, behaviour is same as earlier i.e vlun is
                # not deleted now i.e skip remainder of terminate volume
                # connection.
                #
                # case [2]:
                # In such case, vlun of that host on 3par array should
                # be deleted now. Otherwise, it remains as stale entry on
                # 3par array; which later leads to error during volume
                # deletion.

                same_host = False
                num_hosts = len(attachment_list)
                all_hostnames = []
                all_hostnames.append(hostname)

                count = 0
                for i in range(num_hosts):
                    hostname_i = str(attachment_list[i].attached_host)
                    if hostname == hostname_i:
                        # current host
                        count = count + 1
                        if count > 1:
                            # volume attached to multiple instances on
                            # current host
                            same_host = True
                    else:
                        # different host
                        all_hostnames.append(hostname_i)

                if same_host:
                    LOG.info("Volume %(volume)s is attached to multiple "
                             "instances on same host %(host_name)s, "
                             "skip terminate volume connection",
                             {'volume': volume.name,
                              'host_name': volume.host.split('@')[0]})
                    return
                else:
                    hostnames = ",".join(all_hostnames)
                    LOG.info("Volume %(volume)s is attached to instances "
                             "on multiple hosts %(hostnames)s. Proceed with "
                             "deletion of vlun on this host.",
                             {'volume': volume.name, 'hostnames': hostnames})

        # does 3par know this host by a different name?
        hosts = None
        if wwn:
            hosts = super().query_host(wwns=wwn)
        elif iqn:
            hosts = super().query_host(iqns=[iqn])

        if hosts is not None:
            if hosts and hosts['members'] and 'name' in hosts['members'][0]:
                hostname = hosts['members'][0]['name']

        try:
            self.delete_vlun(volume, hostname, wwn=wwn, iqn=iqn,
                             remote_client=remote_client)
            return
        except flowkit_exceptions.HTTPNotFound as e:
            if constants.HOST_DOES_NOT_EXISTS in e.message:
                # If a host is failed-over, we want to allow the detach to
                # 'succeed' when it cannot find the host. We can simply
                # return out of the terminate connection in order for things
                # to be updated correctly.
                if self._active_backend_id:
                    LOG.warning("Because the host is currently in a "
                                "failed-over state, the volume will not "
                                "be properly detached from the primary "
                                "array. The detach will be considered a "
                                "success as far as Cinder is concerned. "
                                "The volume can now be attached to the "
                                "secondary target.")
                    return
                else:
                    if hosts is None:
                        # In case of 'force detach', hosts is None
                        LOG.exception("Exception: %s", e)
                        raise
                    else:
                        # use the wwn to see if we can find the hostname
                        hostname = self._get_3par_hostname_from_wwn_iqn(
                            wwn,
                            iqn)
                        # no 3par host, re-throw
                        if hostname is None:
                            LOG.exception("Exception: %s", e)
                            raise
            else:
                # not a 'host does not exist' HTTPNotFound exception, re-throw
                LOG.error("Exception: %s", e)
                raise

        # try again with name retrieved from 3par
        self.delete_vlun(volume, hostname, wwn=wwn, iqn=iqn,
                         remote_client=remote_client)

    def manage_existing(self, volume, existing_ref):
        """Manage an existing 3PAR volume.

        existing_ref is a dictionary of the form:
        {'source-name': <name of the virtual volume>}
        """
        self.session_mgr.ensure_session()
        target_vol_name = self._get_existing_volume_ref_name(existing_ref)
        LOG.debug("target_vol_name: %(name)s", {'name': target_vol_name})

        # Check for the existence of the virtual volume.
        old_comment_str = ""
        try:
            vol = super().get_volume(target_vol_name)
            if 'comment' in vol:
                old_comment_str = vol['comment']
        except flowkit_exceptions.HPEStorageException as ex:
            err = (_("Virtual volume '%s' doesn't exist on array.") %
                   target_vol_name)
            LOG.error(err)
            raise exception.InvalidInput(reason=err)

        new_comment = {}

        # Use the display name from the existing volume if no new name
        # was chosen by the user.
        if volume['display_name']:
            display_name = volume['display_name']
            new_comment['display_name'] = volume['display_name']
        elif 'comment' in vol:
            display_name = self._get_3par_vol_comment_value(vol['comment'],
                                                            'display_name')
            if display_name:
                new_comment['display_name'] = display_name
        else:
            display_name = None

        # Generate the new volume information based on the new ID.
        new_vol_name = self._get_3par_vol_name(volume)
        LOG.debug("new_vol_name: %(name)s", {'name': new_vol_name})
        # No need to worry about "_name_id" because this is a newly created
        # volume that cannot have been migrated.
        name = 'volume-' + volume['id']

        new_comment['volume_id'] = volume['id']
        new_comment['name'] = name
        new_comment['type'] = 'OpenStack'
        self._add_name_id_to_comment(new_comment, volume)

        volume_type = None
        if volume['volume_type_id']:
            try:
                volume_type = self._get_volume_type(volume['volume_type_id'])
            except Exception as e:
                reason = (_("Volume type ID '%s' is invalid.") %
                          volume['volume_type_id'])
                raise exception.ManageExistingVolumeTypeMismatch(reason=reason) from e

        new_vals = {'newName': new_vol_name,
                    'comment': json.dumps(new_comment)}

        # Ensure that snapCPG is set (for 3par/Primera)
        # not applicable for Alletra MP

        # Update the existing volume with the new name and comments.
        try:
            super().modify_volume(target_vol_name, new_vals)
        except Exception as e:
            raise exception.InvalidInput(reason=str(e)) from e
        LOG.info("Virtual volume '%(ref)s' renamed to '%(new)s'.",
                 {'ref': existing_ref['source-name'], 'new': new_vol_name})

        retyped = False
        model_update = None
        if volume_type:
            LOG.info("Virtual volume %(disp)s '%(new)s' is being retyped.",
                     {'disp': display_name, 'new': new_vol_name})

            try:
                retyped, model_update = self._retype_from_no_type(volume,
                                                                  volume_type)
                LOG.info("Virtual volume %(disp)s successfully retyped to "
                         "%(new_type)s.",
                         {'disp': display_name,
                          'new_type': volume_type.get('name')})
            except Exception:
                with excutils.save_and_reraise_exception():
                    LOG.warning("Failed to manage virtual volume %(disp)s "
                                "due to error during retype.",
                                {'disp': display_name})
                    # Try to undo the rename and clear the new comment.
                    super().modify_volume(
                        new_vol_name,
                        {'newName': target_vol_name,
                         'comment': old_comment_str})

        updates = {'display_name': display_name}
        if retyped and model_update:
            updates.update(model_update)

        LOG.info("Virtual volume %(disp)s '%(new)s' is now being managed.",
                 {'disp': display_name, 'new': new_vol_name})

        # Return display name to update the name displayed in the GUI and
        # any model updates from retype.
        return updates    

    def manage_existing_get_size(self, volume, existing_ref):
        """Return size of volume to be managed by manage_existing.

        existing_ref is a dictionary of the form:
        {'source-name': <name of the virtual volume>}
        """
        self.session_mgr.ensure_session()
        target_vol_name = self._get_existing_volume_ref_name(existing_ref)

        # Make sure the reference is not in use.
        if re.match('osv-*|oss-*|vvs-*', target_vol_name):
            reason = _("Reference must be for an unmanaged virtual volume.")
            raise exception.ManageExistingInvalidReference(
                existing_ref=target_vol_name,
                reason=reason)

        # Check for the existence of the virtual volume.
        try:
            vol = super().get_volume(target_vol_name)
        except flowkit_exceptions.HPEStorageException as e:
            err = (_("Virtual volume '%s' doesn't exist on array.") %
                   target_vol_name)
            LOG.error(err)
            raise exception.InvalidInput(reason=err) from e

        return int(math.ceil(float(vol['sizeMiB']) / units.Ki))

    def unmanage(self, volume):
        """Removes the specified volume from Cinder management."""
        self.session_mgr.ensure_session()
        # Rename the volume's name to unm-* format so that it can be
        # easily found later.
        vol_name = self._get_3par_vol_name(volume)
        # Rename using the user visible ID ignoring the internal "_name_id"
        # that may have been generated during a retype.  This makes it easier
        # to locate volumes in the backend.
        new_vol_name = self._get_3par_unm_name(volume['id'])
        super().modify_volume(vol_name, {'newName': new_vol_name})

        LOG.info("Virtual volume %(disp)s '%(vol)s' is no longer managed. "
                 "Volume renamed to '%(new)s'.",
                 {'disp': volume['display_name'],
                  'vol': vol_name,
                  'new': new_vol_name})

    def get_manageable_volumes(self, cinder_volumes, marker, limit, offset,
                               sort_keys, sort_dirs):
        self.session_mgr.ensure_session()
        already_managed = {}
        for vol_obj in cinder_volumes:
            cinder_id = vol_obj.id
            volume_name = self._get_3par_vol_name(cinder_id)
            already_managed[volume_name] = cinder_id
            LOG.debug("%(name)s is already managed", {'name': volume_name})

        cinder_cpg = self._client_conf['hpe3par_cpg'][0]

        manageable_vols = []

        all_volumes = super().list_volumes_from_cpg(cinder_cpg)
        for vol in all_volumes:
            size_gb = int(vol['sizeMiB'] / 1024)
            vol_name = vol['name']
            if vol_name in already_managed:
                is_safe = False
                reason_not_safe = _('Volume already managed')
                cinder_id = already_managed[vol_name]
            else:
                is_safe = False
                hostname = None
                cinder_id = None
                # Check if the unmanaged volume is attached to any host
                try:
                    vlun = super().getVLUN(vol_name)
                    if vlun is None:
                        raise flowkit_exceptions.HPEStorageException(
                            "VLUN '%s' was not found" % vol_name)
                    hostname = vlun['hostname']
                except flowkit_exceptions.HPEStorageException:
                    # not attached to any host
                    is_safe = True

                if is_safe:
                    reason_not_safe = None
                else:
                    reason_not_safe = _('Volume attached to host ' +
                                        hostname)

            manageable_vols.append({
                'reference': {'name': vol_name},
                'size': size_gb,
                'safe_to_manage': is_safe,
                'reason_not_safe': reason_not_safe,
                'cinder_id': cinder_id,
            })

        return volume_utils.paginate_entries_list(
            manageable_vols, marker, limit, offset, sort_keys, sort_dirs)

    def tune_vv(self, old_tpvv, new_tpvv, old_tdvv, new_tdvv,
                old_cpg, new_cpg, volume_name, new_compression):
        """Tune the volume to change the userCPG and/or provisioningType.

        The volume will be modified/tuned/converted to the new userCPG and
        provisioningType, as needed.

        TaskWaiter is used to make this function wait until the 3PAR task
        is no longer active.  When the task is no longer active, then it must
        either be done or it is in a state that we need to treat as an error.
        """

        compression = False
        if new_compression is not None:
            compression = new_compression

        if old_tpvv == new_tpvv and old_tdvv == new_tdvv:
            if new_cpg != old_cpg:
                LOG.info("Modifying %(volume_name)s userCPG "
                         "from %(old_cpg)s"
                         " to %(new_cpg)s",
                         {'volume_name': volume_name,
                          'old_cpg': old_cpg, 'new_cpg': new_cpg})
                _response, body = super().modify_volume(
                    volume_name,
                    {'action': 6,
                     'tuneOperation': 1,
                     'userCPG': new_cpg})
                task_id = body['taskid']
                status= self._wait_for_task_completion(task_id)
                if status['status'] is not constants.TASK_DONE:
                    msg = (_('Tune volume task stopped before it was done: '
                             'volume_name=%(volume_name)s, '
                             'task-status=%(status)s.') %
                           {'status': status, 'volume_name': volume_name})
                    raise exception.VolumeBackendAPIException(msg)
        else:
            if new_tpvv:
                cop = constants.CONVERT_TO_THIN
                LOG.info("Converting %(volume_name)s to thin provisioning "
                         "with userCPG=%(new_cpg)s",
                         {'volume_name': volume_name, 'new_cpg': new_cpg})
            elif new_tdvv:
                cop = constants.CONVERT_TO_DEDUP
                LOG.info("Converting %(volume_name)s to thin dedup "
                         "provisioning with userCPG=%(new_cpg)s",
                         {'volume_name': volume_name, 'new_cpg': new_cpg})
            else:
                cop = constants.CONVERT_TO_FULL
                LOG.info("Converting %(volume_name)s to full provisioning "
                         "with userCPG=%(new_cpg)s",
                         {'volume_name': volume_name, 'new_cpg': new_cpg})

            response = None
            body = None
            try:
                if self.API_VERSION < constants.COMPRESSION_API_VERSION:
                    response, body = super().modify_volume(
                        volume_name,
                        {'action': 6,
                         'tuneOperation': 1,
                         'userCPG': new_cpg,
                         'conversionOperation': cop})
                else:
                    LOG.debug("compression: %(compression)s",
                              {'compression': compression})
                    body = super().tune_volume(
                        volume_name,
                        {'action': 6,
                         'tuneOperation': 1,
                         'userCPG': new_cpg,
                         'conversionOperation': cop})
                    LOG.debug("body: %(body)s", {'body': body})
            except flowkit_exceptions.HTTPBadRequest as ex:
                ex_str = str(ex)
                LOG.debug("flowkit HTTPNotFound: %s", ex_str)
                if str(constants.API_ERROR_40) in ex_str:
                    # Cannot retype with snapshots because we don't want to
                    # use keepVV and have straggling volumes.  Log additional
                    # info and then raise.
                    LOG.info("tunevv failed because the volume '%s' "
                             "has snapshots.", volume_name)
                    raise

            task_id = body['taskid']
            status= self._wait_for_task_completion(task_id)
            if status['status'] is not constants.TASK_DONE:
                msg = (_('Tune volume task stopped before it was done: '
                         'volume_name=%(volume_name)s, '
                         'task-status=%(status)s.') %
                       {'status': status, 'volume_name': volume_name})
                raise exception.VolumeBackendAPIException(msg)

    def _retype_pre_checks(self, volume, host, new_persona,
                           old_cpg, new_cpg,
                           new_snap_cpg):
        """Test retype parameters before making retype changes.

        Do pre-retype parameter validation.  These checks will
        raise an exception if we should not attempt this retype.
        """

        if new_persona:
            self.validate_persona(new_persona)

        if host is not None:
            (host_type, host_id, _host_cpg) = (
                host['capabilities']['location_info']).split(':')

            if not (host_type == 'HPE3PARDriver'):
                reason = (_("Cannot retype from HPE3PARDriver to %s.") %
                          host_type)
                raise exception.InvalidHost(reason=reason)

            sys_info = super().get_storage_system_info()                    
            if not (host_id == sys_info['serialNumber']):
                reason = (_("Cannot retype from one 3PAR array to another."))
                raise exception.InvalidHost(reason=reason)

        # Validate new_snap_cpg.  A white-space snapCPG will fail eventually,
        # but we'd prefer to fail fast -- if this ever happens.
        if not new_snap_cpg or new_snap_cpg.isspace():
            reason = (_("Invalid new snapCPG name for retype.  "
                        "new_snap_cpg='%s'.") % new_snap_cpg)
            raise exception.InvalidInput(reason)

        # Check to make sure CPGs are in the same domain
        domain = self.get_domain(old_cpg)
        if domain != self.get_domain(new_cpg):
            reason = (_('Cannot retype to a CPG in a different domain.'))
            raise flowkit_exceptions.HPEStorageException(reason)

        # snap_cpg not applicable for Alletra MP

    def _retype(self, volume, volume_name, new_type_name, new_type_id, host,
                new_persona, old_cpg, new_cpg, old_snap_cpg, new_snap_cpg,
                old_tpvv, new_tpvv, old_tdvv, new_tdvv,
                old_vvs, new_vvs, old_qos, new_qos,
                old_flash_cache, new_flash_cache,
                old_comment, new_compression):

        action = "volume:retype"

        self._retype_pre_checks(volume, host, new_persona,
                                old_cpg, new_cpg,
                                new_snap_cpg)

        flow_name = action.replace(":", "_") + "_api"
        retype_flow = linear_flow.Flow(flow_name)
        # Keep this linear and do the big tunevv last.  Everything leading
        # up to that is reversible, but we'd let the 3PAR deal with tunevv
        # errors on its own.
        retype_flow.add(
            ModifyVolumeTask(action),
            ModifySpecsTask(action),
            TuneVolumeTask(action),
            ReplicateVolumeTask(action))

        taskflow.engines.run(
            retype_flow,
            store={'common': self,
                   'volume_name': volume_name, 'volume': volume,
                   'old_tpvv': old_tpvv, 'new_tpvv': new_tpvv,
                   'old_tdvv': old_tdvv, 'new_tdvv': new_tdvv,
                   'old_cpg': old_cpg, 'new_cpg': new_cpg,
                   'old_snap_cpg': old_snap_cpg, 'new_snap_cpg': new_snap_cpg,
                   'old_vvs': old_vvs, 'new_vvs': new_vvs,
                   'old_qos': old_qos, 'new_qos': new_qos,
                   'old_flash_cache': old_flash_cache,
                   'new_flash_cache': new_flash_cache,
                   'new_type_name': new_type_name, 'new_type_id': new_type_id,
                   'old_comment': old_comment,
                   'new_compression': new_compression
                   })

    def _retype_from_old_to_new(self, volume, new_type, old_volume_settings,
                                host):
        """Convert the volume to be of the new type.  Given old type settings.

        Returns True if the retype was successful.
        Uses taskflow to revert changes if errors occur.

        :param volume: A dictionary describing the volume to retype
        :param new_type: A dictionary describing the volume type to convert to
        :param old_volume_settings: Volume settings describing the old type.
        :param host: A dictionary describing the host, where
                     host['host'] is its name, and host['capabilities'] is a
                     dictionary of its reported capabilities.  Host validation
                     is just skipped if host is None.
        """
        volume_name = self._get_3par_vol_name(volume)
        new_type_name = None
        new_type_id = None
        if new_type:
            new_type_name = new_type['name']
            new_type_id = new_type['id']
        pool = None
        if host:
            pool = volume_utils.extract_host(host['host'], 'pool')
        else:
            pool = volume_utils.extract_host(volume['host'], 'pool')
        new_volume_settings = self.get_volume_settings_from_type_id(
            new_type_id, pool)
        new_cpg = new_volume_settings['cpg']
        new_snap_cpg = new_volume_settings['snap_cpg']
        new_tpvv = new_volume_settings['tpvv']
        new_tdvv = new_volume_settings['tdvv']
        new_qos = new_volume_settings['qos']
        new_vvs = new_volume_settings['vvs_name']
        new_persona = None
        new_hpe3par_keys = new_volume_settings['hpe3par_keys']
        if 'persona' in new_hpe3par_keys:
            new_persona = new_hpe3par_keys['persona']
        new_flash_cache = self.get_flash_cache_policy(new_hpe3par_keys)

        # it will return None / True /False$
        new_compression = self.get_compression_policy(new_hpe3par_keys)

        old_qos = old_volume_settings['qos']
        old_vvs = old_volume_settings['vvs_name']
        old_hpe3par_keys = old_volume_settings['hpe3par_keys']
        old_flash_cache = self.get_flash_cache_policy(old_hpe3par_keys)

        # Get the current volume info because we can get in a bad state
        # if we trust that all the volume type settings are still the
        # same settings that were used with this volume.
        old_volume_info = super().get_volume(volume_name)
        old_tpvv = old_volume_info['provisioningType'] == constants.THIN
        old_tdvv = old_volume_info['provisioningType'] == constants.DEDUP
        old_cpg = old_volume_info['userCPG']
        old_comment = old_volume_info.get('comment')
        old_snap_cpg = None
        if 'snapCPG' in old_volume_info:
            old_snap_cpg = old_volume_info['snapCPG']

        LOG.debug("retype old_volume_info=%s", old_volume_info)
        LOG.debug("retype old_volume_settings=%s", old_volume_settings)
        LOG.debug("retype new_volume_settings=%s", new_volume_settings)

        self._retype(volume, volume_name, new_type_name, new_type_id,
                     host, new_persona, old_cpg, new_cpg,
                     old_snap_cpg, new_snap_cpg, old_tpvv, new_tpvv,
                     old_tdvv, new_tdvv, old_vvs, new_vvs,
                     old_qos, new_qos, old_flash_cache, new_flash_cache,
                     old_comment, new_compression)

        if host:
            return True, self._get_model_update(host['host'], new_cpg)
        else:
            return True, self._get_model_update(volume['host'], new_cpg)

    def _retype_from_no_type(self, volume, new_type):
        """Convert the volume to be of the new type.  Starting from no type.

        Returns True if the retype was successful.
        Uses taskflow to revert changes if errors occur.

        :param volume: A dictionary describing the volume to retype. Except the
                       volume-type is not used here. This method uses None.
        :param new_type: A dictionary describing the volume type to convert to
        """
        pool = volume_utils.extract_host(volume['host'], 'pool')
        none_type_settings = self.get_volume_settings_from_type_id(None, pool)
        return self._retype_from_old_to_new(volume, new_type,
                                            none_type_settings, None)

    def retype(self, volume, new_type, diff, host):
        """Convert the volume to be of the new type.

        Returns True if the retype was successful.
        Uses taskflow to revert changes if errors occur.

        :param volume: A dictionary describing the volume to retype
        :param new_type: A dictionary describing the volume type to convert to
        :param diff: A dictionary with the difference between the two types
        :param host: A dictionary describing the host, where
                     host['host'] is its name, and host['capabilities'] is a
                     dictionary of its reported capabilities.  Host validation
                     is just skipped if host is None.
        """
        self.session_mgr.ensure_session()
        LOG.debug(("enter: retype: id=%(id)s, new_type=%(new_type)s,"
                   "diff=%(diff)s, host=%(host)s"), {'id': volume['id'],
                                                     'new_type': new_type,
                                                     'diff': diff,
                                                     'host': host})
        self.remove_temporary_snapshots(volume)
        old_volume_settings = self.get_volume_settings_from_type(volume, host)
        return self._retype_from_old_to_new(volume, new_type,
                                            old_volume_settings, host)

    def remove_temporary_snapshots(self, volume):
        self.session_mgr.ensure_session()
        vol_name = self._get_3par_vol_name(volume)
        snapshots_list = super().getVolumeSnapshots(vol_name)
        tmp_snapshots_list = [snap
                              for snap in snapshots_list
                              if snap.startswith('tss-')]
        LOG.debug("temporary snapshot list %(name)s",
                  {'name': tmp_snapshots_list})
        for temp_snap in tmp_snapshots_list:
            LOG.debug("Found a temporary snapshot %(name)s",
                      {'name': temp_snap})
            try:
                super().delete_volume(temp_snap)
            except flowkit_exceptions.HTTPNotFound:
                # if the volume is gone, it's as good as a
                # successful delete
                pass
            except Exception:
                msg = _("Volume has a temporary snapshot.")
                raise exception.VolumeIsBusy(message=msg)

    def migrate_volume(self, volume, host):
        """Migrate directly if source and dest are managed by same storage.

        :param volume: A dictionary describing the volume to migrate
        :param host: A dictionary describing the host to migrate to, where
                     host['host'] is its name, and host['capabilities'] is a
                     dictionary of its reported capabilities.
        :returns: (False, None) if the driver does not support migration,
                 (True, model_update) if successful

        """

        self.session_mgr.ensure_session()
        dbg = {'id': volume['id'],
               'host': host['host'],
               'status': volume['status']}
        LOG.debug('enter: migrate_volume: id=%(id)s, host=%(host)s, '
                  'status=%(status)s.', dbg)
        ret = False, None

        if volume['status'] in ['available', 'in-use']:
            volume_type = None
            if volume['volume_type_id']:
                volume_type = self._get_volume_type(volume['volume_type_id'])

            try:
                ret = self.retype(volume, volume_type, None, host)
            except Exception as e:
                LOG.info('3PAR driver cannot perform migration. '
                         'Retype exception: %s', e)

        LOG.debug('leave: migrate_volume: id=%(id)s, host=%(host)s, '
                  'status=%(status)s.', dbg)
        dbg_ret = {'supported': ret[0], 'model_update': ret[1]}
        LOG.debug('migrate_volume result: %(supported)s, %(model_update)s',
                  dbg_ret)
        return ret

    def _rename_migrated_vvset(self, src_volume, dest_volume):
        """Rename the vvsets after a migration.

        """
        vvs_name_src = self._get_3par_vvs_name(src_volume['id'])
        vvs_name_dest = self._get_3par_vvs_name(dest_volume['id'])

        # There can be parallel execution. Ensure that temp_vvs_name is unique
        # eg. if vvs_name_src is: vvs-DK3sEwkPTCqVHdHKHtwZBA
        # then temp_vvs_name is : tos-DK3sEwkPTCqVHdHKHtwZBA
        temp_vvs_name = 'tos-' + vvs_name_src[4:]

        try:
            super().modifyVolumeSet(vvs_name_dest, newName=temp_vvs_name)     #already in pr
            LOG.debug("Renamed vvset %(old)s to %(new)s",
                      {'old': vvs_name_dest, 'new': temp_vvs_name})
        except Exception as ex:
            LOG.error("exception: %(details)s", {'details': str(ex)})

        try:
            super().modifyVolumeSet(vvs_name_src, newName=vvs_name_dest)            #already in pr
            LOG.debug("Renamed vvset %(old)s to %(new)s",
                      {'old': vvs_name_src, 'new': vvs_name_dest})
        except flowkit_exceptions.HPEStorageException as ex:
            LOG.error("exception: %(details)s", {'details': str(ex)})

        try:
            super().modifyVolumeSet(temp_vvs_name, newName=vvs_name_src)
            LOG.debug("Renamed vvset %(old)s to %(new)s",
                      {'old': temp_vvs_name, 'new': vvs_name_src})
        except flowkit_exceptions.HPEStorageException as ex:
            LOG.error("exception: %(details)s", {'details': str(ex)})


    def _rename_migrated(self, volume, dest_volume):
        """Rename the destination volume after a migration.

        Returns whether the destination volume has the name matching the source
        volume or not.

        That way we know whether we need to set the _name_id or not.
        """
        def log_error(vol_type, error, src, dest, rename_name=None,
                      original_name=None):
            LOG.error("Changing the %(vol_type)s volume name from %(src)s to "
                      "%(dest)s failed because %(reason)s",
                      {'vol_type': vol_type, 'src': src, 'dest': dest,
                       'reason': error})
            if rename_name:
                original_name = original_name or dest
                # Don't fail the migration, but help the user fix the
                # source volume stuck in error_deleting.
                LOG.error("Migration will fail to delete the original volume. "
                          "It must be manually renamed from %(rename_name)s to"
                          "  %(original_name)s in the backend, and then we "
                          "have to tell cinder to delete volume %(vol_id)s",
                          {'rename_name': rename_name,
                           'original_name': original_name,
                           'vol_id': dest_volume['id']})

        original_volume_renamed = False
        # We don't need to rename the source volume if it uses a _name_id,
        # since the id we want to use to rename the new volume is available.
        if volume['id'] == (volume.get('_name_id') or volume['id']):
            original_name = self._get_3par_vol_name(volume)
            temp_name = self._get_3par_vol_name(volume, temp_vol=True)

            # In case the original volume is on the same backend, try
            # renaming it to a temporary name.
            try:
                volumeTempMods = {'newName': temp_name}
                super().modify_volume(original_name, volumeTempMods)              #already in pr
                original_volume_renamed = True
            except flowkit_exceptions.HPEStorageException as ex:
                pass
            except Exception as e:
                log_error('original', e, original_name, temp_name)
                return False

        # Change the destination volume name to the source's ID name
        current_name = self._get_3par_vol_name(dest_volume)
        volume_id_name = self._get_3par_vol_name(volume['id'])
        try:
            # After this call the volume manager will call
            # finish_volume_migration and swap the fields, so we want to
            # have the right info on the comments if we succeed in renaming
            # the volumes in the backend.
            new_comment = self._get_updated_comment(current_name,
                                                    volume_id=volume['id'],
                                                    _name_id=None)
            volumeMods = {'newName': volume_id_name, 'comment': new_comment}
            super().modify_volume(current_name, volumeMods)                       #already in pr
            LOG.info("Current volume changed from %(cur)s to %(orig)s",
                     {'cur': current_name, 'orig': volume_id_name})
        except Exception as e:
            if original_volume_renamed:
                _name = temp_name
            else:
                _name = original_name = None
            log_error('migrating', e, current_name, volume_id_name, _name,
                      original_name)
            return False

        # If it was renamed, rename the original volume again to the
        # migrated volume's name (effectively swapping the names). If
        # this operation fails, the newly migrated volume is OK but the
        # original volume (with the temp name) may need to be manually
        # cleaned up on the backend.
        if original_volume_renamed:
            try:
                old_comment = self._get_updated_comment(
                    original_name,
                    volume_id=dest_volume['id'],
                    _name_id=volume.get('_name_id'))
                volumeCurrentMods = {'newName': current_name,
                                     'comment': old_comment}
                super().modify_volume(temp_name, volumeCurrentMods)            #already in pr
            except Exception as e:
                log_error('original', e, temp_name, current_name, temp_name)
        return True

    def update_migrated_volume(self, context, volume, new_volume,
                               original_volume_status):
        """Rename the new (temp) volume to it's original name.


        This method tries to rename the new volume to it's original
        name after the migration has completed.

        """
        self.session_mgr.ensure_session()
        LOG.debug("Update volume name for %(id)s", {'id': new_volume['id']})

        # For available volumes we'll try renaming the destination volume to
        # match the id of the source volume.
        if original_volume_status == 'available':
            new_volume_renamed = self._rename_migrated(volume, new_volume)
        else:
            new_volume_renamed = False

        if new_volume_renamed:
            name_id = None
            # NOTE: I think this will break with replicated volumes.
            provider_location = None

        else:
            # the backend can't change the name.
            name_id = new_volume['_name_id'] or new_volume['id']
            provider_location = new_volume['provider_location']
            # Update the comment in the backend to reflect the _name_id
            current_name = self._get_3par_vol_name(new_volume)
            self._update_comment(current_name, volume_id=volume['id'],
                                 _name_id=name_id)

        if new_volume_renamed:
            type_info = self.get_volume_settings_from_type(volume)
            qos = type_info['qos']
            if qos:
                # rename the vvsets as per volume names
                self._rename_migrated_vvset(volume, new_volume)

        return {'_name_id': name_id, 'provider_location': provider_location}
  
    def create_group(self, context, group):
        """Creates a group."""

        self.session_mgr.ensure_session()
        if (not volume_utils.is_group_a_cg_snapshot_type(group)
                and not group.is_replicated):
            raise NotImplementedError()

        model_update = {'status': fields.GroupStatus.AVAILABLE}

        if group.volume_type_ids is not None:
            for volume_type in group.volume_types:
                allow_type = self.is_volume_group_snap_type(
                    volume_type)
                if not allow_type:
                    msg = _('For a volume type to be a part of consistent '
                            'group, volume type extra spec must have '
                            'consistent_group_snapshot_enabled="<is> True"')
                    LOG.error(msg)
                    raise exception.InvalidInput(reason=msg)

        pool = volume_utils.extract_host(group.host, level='pool')
        domain = self.get_domain(pool)
        cg_name = self._get_3par_vvs_name(group.id)

        extra = {'group_id': group.id}
        if group.group_snapshot_id is not None:
            extra['group_snapshot_id'] = group.group_snapshot_id

        if group.is_replicated:
            LOG.debug("Group: %(group)s is a replication group.",
                      {'group': group.id})
          
            self._check_replication_configuration_on_volume_types(
                group.volume_types)

            self._check_tiramisu_configuration_on_volume_types(
                group.volume_types)

            # Attributes of Remote must be same on each volume type
            self._check_attributes_of_remote_per_volume_type(group)

            # Create remote copy group
            self._create_remote_copy_group_for_group(group)
            # Start Remote copy
            self._start_remote_copy_group(group)
            model_update.update({
                'replication_status': fields.ReplicationStatus.ENABLED})

        super().createVolumeSet(cg_name, domain=domain,
                                comment=str(extra))

        return model_update

    def delete_group(self, context, group, volumes):

        """Deletes a group."""

        self.session_mgr.ensure_session()
        if (not volume_utils.is_group_a_cg_snapshot_type(group)           #cinder side call
           and not group.is_replicated):
            raise NotImplementedError()

        if group.is_replicated:
            self._remove_volumes_and_remote_copy_group(group, volumes)
        try:
            cg_name = self._get_3par_vvs_name(group.id)
            super().delete_volumeset(cg_name)
        except flowkit_exceptions.HTTPNotFound:
            LOG.warning("Virtual Volume Set '%s' doesn't exist on array.",
                        cg_name)
        except flowkit_exceptions.HTTPConflict as e:
            LOG.error("Conflict detected in Virtual Volume Set"
                      " %(volume_set)s: %(error)s",
                      {"volume_set": cg_name,
                       "error": e})

        volume_model_updates = []
        for volume in volumes:
            volume_update = {'id': volume.get('id')}
            try:
                self.delete_volume(volume)                          #already in raghvendra's pr
                volume_update['status'] = 'deleted'
            except Exception as ex:
                LOG.error("There was an error deleting volume %(id)s: "
                          "%(error)s.",
                          {'id': volume.id,
                           'error': ex})
                volume_update['status'] = 'error'
            volume_model_updates.append(volume_update)
        model_update = {'status': group.status}
        return model_update, volume_model_updates

    def update_group(self, context, group, add_volumes=None,
                     remove_volumes=None):
        self.session_mgr.ensure_session()
        grp_snap_enable = volume_utils.is_group_a_cg_snapshot_type(group)
        if not grp_snap_enable and not group.is_replicated:
            raise NotImplementedError()
        add_volume = []
        remove_volume = []
        vol_rep_status = fields.ReplicationStatus.ENABLED

        volume_set_name = self._get_3par_vvs_name(group.id)

        # If replication is enabled on a group then we need
        # to stop RCG, so we can add/remove in/from RCG.
        if group.is_replicated:
            # Check replication status on a group.
            self._check_rep_status_enabled_on_group(group)
            # Stop remote copy.
            self._stop_remote_copy_group(group)

        # TODO(kushal) : we will use volume as object when we re-write
        # the design for unit tests to use objects instead of dicts.
        for volume in add_volumes:
            volume_name = self._get_3par_vol_name(volume)
            vol_snap_enable = self.is_volume_group_snap_type(
                volume.get('volume_type'))
            try:
                if vol_snap_enable:
                    self._check_replication_matched(volume, group)
                    if group.is_replicated:
                        # Add volume to remote copy group
                        self._add_vol_to_remote_copy_group(group, volume)
                        # We have introduced one flag hpe3par:group_replication
                        # in extra_spec of volume_type,which denotes group
                        # level replication on 3par,so when a volume from this
                        # type is added into group we need to set
                        # replication_status on a volume.
                        update = {'id': volume.get('id'),
                                  'replication_status': vol_rep_status}
                        add_volume.append(update)
                    super().addVolumeToVolumeSet(volume_set_name, volume_name)
                else:
                    msg = (_('Volume with volume id %s is not '
                             'supported as extra specs of this '
                             'volume does not have '
                             'consistent_group_snapshot_enabled="<is> True"'
                             ) % volume['id'])
                    LOG.error(msg)
                    raise exception.InvalidInput(reason=msg)
            except flowkit_exceptions.HPEStorageException as ex:
                msg = (_('Virtual Volume Set %s does not exist.') %
                       volume_set_name)
                LOG.error(msg)
                raise exception.InvalidInput(reason=msg)

        for volume in remove_volumes:
            volume_name = self._get_3par_vol_name(volume)

            if group.is_replicated:
                # Remove a volume from remote copy group
                self._remove_vol_from_remote_copy_group(
                    group, volume)
                update = {'id': volume.get('id'),
                          'replication_status': None}
                remove_volume.append(update)
            try:
                super().removeVolumeFromVolumeSet(volume_set_name, volume_name)
            except flowkit_exceptions.HPEStorageException as ex:
                msg = (_('Virtual Volume Set %s does not exist.') %
                       volume_set_name)
                LOG.error(msg)
                raise exception.InvalidInput(reason=msg)

        if group.is_replicated:
            # Start remote copy.
            self._start_remote_copy_group(group)

        return None, add_volume, remove_volume    

    def create_group_from_src(self, context, group, volumes,
                              group_snapshot=None, snapshots=None,
                              source_group=None, source_vols=None):

        self.session_mgr.ensure_session()
        self.create_group(context, group)
        volumes_model_update = []
        task_id_list = []
        volumes_cpg_map = []
        snap_vol_dict = {}
        replication_flag = False
        model_update = {'status': fields.GroupStatus.AVAILABLE}

        vvs_name = self._get_3par_vvs_name(group.id)
        if group_snapshot and snapshots:
            cgsnap_name = self._get_3par_snap_name(group_snapshot.id)
            snap_base = cgsnap_name
        elif source_group and source_vols:
            cg_id = source_group.id
            # Create a brand new uuid for the temp snap.
            snap_uuid = uuid.uuid4().hex

            # Create a temporary snapshot of the volume set in order to
            # perform an online copy. These temp snapshots will be deleted
            # when the source consistency group is deleted.
            temp_snap = self._get_3par_snap_name(snap_uuid, temp_snap=True)
            snap_shot_name = temp_snap + "-@count@"
            copy_of_name = self._get_3par_vvs_name(cg_id)
            optional = {'expirationHours': 1}
            super().createSnapshotOfVolumeSet(snap_shot_name, copy_of_name,
                                              optional=optional)
            snap_base = temp_snap

        if group.is_replicated:
            replication_flag = True
            # Stop remote copy, so we can add volumes in RCG.
            self._stop_remote_copy_group(group)

        for i in range(0, len(volumes)):
            # In case of group created from group,we are mapping
            # source volume with it's snapshot
            snap_name = snap_base + "-" + str(i)
            snap_detail = super().get_volume(snap_name)
            vol_name = snap_detail.get('copyOf')
            src_vol_name = vol_name

            # In case of group created from group snapshots,we are mapping
            # source volume with it's snapshot
            if source_group is None:
                for snapshot in snapshots:
                    # Getting vol_name from snapshot, in case of group created
                    # from group snapshot.
                    # Don't use the "volume_id" from the snapshot directly in
                    # case the volume has been migrated and uses a different ID
                    # in the backend.  This may trigger OVO lazy loading.  Use
                    # dict compatibility to avoid changing all the unit tests.
                    vol_name = self._get_3par_vol_name(snapshot['volume'])
                    if src_vol_name == vol_name:
                        vol_name = (
                            self._get_3par_vol_name(snapshot.get('id')))
                        break
            LOG.debug("Source volume name: %(vol)s of snapshot: %(snap)s",
                      {'vol': src_vol_name, 'snap': snap_name})
            snap_vol_dict[vol_name] = snap_name

        for volume in volumes:
            src_vol_name = volume.get('source_volid')
            if src_vol_name is None:
                src_vol_name = volume.get('snapshot_id')

            # Finding source volume from volume and then use snap_vol_dict
            # to get right snap name from source volume.
            vol_name = self._get_3par_vol_name(src_vol_name)
            snap_name = snap_vol_dict.get(vol_name)

            volume_name = self._get_3par_vol_name(volume)
            type_info = self.get_volume_settings_from_type(volume)
            cpg = type_info['cpg']
            snapcpg = type_info['snap_cpg']
            tpvv = type_info.get('tpvv', False)
            tdvv = type_info.get('tdvv', False)
            volumes_cpg_map.append((volume, volume_name, cpg))

            compression = self.get_compression_policy(
                type_info['hpe3par_keys'])

            optional = {'tpvv': tpvv, 'online': True}

            if tdvv and compression:
                optional['reduce'] = tdvv

            body = super().copy_volume(snap_name, volume_name, cpg,
                                       optional)
            task_id = body['taskid']
            task_id_list.append((task_id, volume.get('id')))

        # Only in case of replication, we are waiting for tasks to complete.
        if group.is_replicated:
            for task_id, vol_id in task_id_list:
                task_status = self._wait_for_task_completion(task_id)
                if task_status['status'] is not constants.TASK_DONE:
                    dbg = {'status': task_status, 'id': vol_id}
                    msg = _('Copy volume task failed:  '
                            'create_group_from_src_group '
                            'id=%(id)s, status=%(status)s.') % dbg
                    LOG.error(msg)
                    raise exception.CinderException(msg)
                else:
                    LOG.debug('Online copy volume completed: '
                              'create_group_from_src_group: id=%s.', vol_id)

        for volume, volume_name, cpg in volumes_cpg_map:
            if group.is_replicated:
                # Add volume to remote copy group
                self._add_vol_to_remote_copy_group(group, volume)
            super().addVolumeToVolumeSet(vvs_name, volume_name)

            volume_model_update = self._get_model_update(
                volume.get('host'), cpg, replication=replication_flag,
                provider_location=self.id)                           # not sure how to handle this

            if volume_model_update is not None:
                volume_model_update.update({'id': volume.get('id')})
                # Update volumes_model_update
                volumes_model_update.append(volume_model_update)

        if group.is_replicated:
            # Start remote copy.
            self._start_remote_copy_group(group)
            model_update.update({
                'replication_status': fields.ReplicationStatus.ENABLED})

        return model_update, volumes_model_update
    

    ######################################################
    # replication code starts here

    def _get_replication_targets(self):
        replication_targets = []
        for target in self._replication_targets:
            replication_targets.append(target['backend_id'])

        return replication_targets

    def _do_volume_replication_setup(self, volume, retype=False,
                                     dist_type_id=None):
        """This function will do or ensure the following:

        -Create volume on main array (already done in create_volume)
        -Create Remote Copy Group on main array
        -Add volume to Remote Copy Group on main array
        -Start remote copy

        If anything here fails, we will need to clean everything up in
        reverse order, including the original volume.
        """

        LOG.debug("Inside _do_volume_replication_setup()")
        rcg_name = self._get_3par_rcg_name(volume)
        # If the volume is already in a remote copy group, return True
        # after starting remote copy. If remote copy is already started,
        # issuing this command again will be fine.
        if self._is_volume_in_remote_copy_group(volume):
            try:
                super().start_remote_copy_group(rcg_name)
            except Exception:
                pass
            return True

        try:
            # Grab the extra_spec entries for replication and make sure they
            # are set correctly.
            volume_type = self._get_volume_type(volume["volume_type_id"])
            if retype and dist_type_id is not None:
                dist_type = self._get_volume_type(dist_type_id)
                extra_specs = dist_type.get("extra_specs")
            else:
                extra_specs = volume_type.get("extra_specs")
            replication_mode = extra_specs.get(
                constants.EXTRA_SPEC_REP_MODE, constants.DEFAULT_REP_MODE)
            replication_mode_num = self._get_remote_copy_mode_num(
                replication_mode)
            replication_sync_period = extra_specs.get(
                constants.EXTRA_SPEC_REP_SYNC_PERIOD, constants.DEFAULT_SYNC_PERIOD)
            if replication_sync_period:
                replication_sync_period = int(replication_sync_period)

            if not self._is_replication_mode_correct(replication_mode,
                                                     replication_sync_period):
                msg = _("The replication mode was not configured correctly "
                        "in the volume type extra_specs. If replication:mode "
                        "is periodic, replication:sync_period must also be "
                        "specified and be between 300 and 31622400 seconds.")
                LOG.error(msg)
                raise exception.VolumeBackendAPIException(data=msg)

            vol_settings = self.get_volume_settings_from_type(volume)
            local_cpg = vol_settings['cpg']
            vol_name = self._get_3par_vol_name(volume)

            # Create remote copy group on main array.
            rcg_targets = []
            sync_targets = []
            policy_targets = []
            for target in self._replication_targets:
                # Only add targets that match the volumes replication mode.
                if target['replication_mode'] == replication_mode_num:
                    cpg = self._get_cpg_from_cpg_map(target['cpg_map'],
                                                     local_cpg)
                    rcg_target = {'targetName': target['backend_id'],
                                  'mode': replication_mode_num,
                                  'userCPG': cpg}
                    rcg_targets.append(rcg_target)
                    sync_target = {'targetName': target['backend_id'],
                                   'syncPeriod': replication_sync_period}
                    sync_targets.append(sync_target)
                    # If replication mode is SYNC, set autoRecover and autoSynchronize
                    # policies. If replication mode is PERIODIC, set autoRecover only.
                    if replication_mode_num == constants.SYNC:
                        policy_auto_target = {'targetName': target['backend_id'],
                                        'policies': {'autoRecover': True, 
                                                    'autoSynchronize': True}
                                        }
                        policy_targets.append(policy_auto_target)
                    else:
                        policy_target = {'targetName': target['backend_id'],
                                        'policies': {'autoRecover': True}
                                        }
                        policy_targets.append(policy_target)

            optional = {'localUserCPG': local_cpg}
            pool = volume_utils.extract_host(volume['host'], level='pool')
            domain = self.get_domain(pool)
            if domain:
                optional["domain"] = domain
            try:
                super().create_remote_copy_group(rcg_name, rcg_targets,
                                                  optional)
            except Exception as ex:
                msg = (_("There was an error creating the remote copy "
                         "group: %s.") %
                       str(ex))
                LOG.error(msg)
                raise exception.VolumeBackendAPIException(data=msg) from ex

            LOG.debug("created rcg %(name)s", {'name': rcg_name})

            # Add volume to remote copy group.
            rcg_targets = []
            for target in self._replication_targets:
                # Only add targets that match the volumes replication mode.
                if target['replication_mode'] == replication_mode_num:
                    rcg_target = {'targetName': target['backend_id'],
                                  'secVolumeName': vol_name}
                    rcg_targets.append(rcg_target)
            optional = {'volumeAutoCreation': True}
            try:
                super().add_volume_to_remote_copy_group(rcg_name, vol_name,
                                                       rcg_targets,
                                                       optional)
            except Exception as ex:
                msg = (_("There was an error adding the volume to the remote "
                         "copy group: %s.") %
                       str(ex))
                LOG.error(msg)
                raise exception.VolumeBackendAPIException(data=msg) from ex

            # Check and see if we are in periodic mode. If we are, update
            # Remote Copy Group to have a sync period.
            if replication_sync_period and (
               replication_mode_num == constants.PERIODIC):
                opt = {'targets': sync_targets}
                try:
                    super().modify_remote_copy_group(rcg_name, opt)
                except Exception as ex:
                    msg = (_("There was an error setting the sync period for "
                             "the remote copy group: %s.") %
                           str(ex))
                    LOG.error(msg)
                    raise exception.VolumeBackendAPIException(data=msg) from ex
                
                opt_new = {'targets': policy_targets}
                LOG.debug("Setting policy targets as %(targets)s", {'targets': policy_targets})
                try:
                    super().modify_remote_copy_group(rcg_name, opt_new)
                except Exception as ex:
                    msg = (_("There was an error setting the policy for "
                             "the remote copy group: %s.") %
                           str(ex))
                    LOG.error(msg)
                    raise exception.VolumeBackendAPIException(data=msg) from ex

            # Check if we are in sync mode and, if so, apply
            # Peer Persistence (PP) policy based on explicit
            # configuration rather than quorum witness presence.
            if replication_mode_num == constants.SYNC:
                remote_target = self._replication_targets[0]
                quorum_witness_ip = remote_target.get('quorum_witness_ip')
                LOG.debug("quorum_witness_ip %(qip)s", {'qip': quorum_witness_ip})

                # Determine replication policy from volume type extra_specs
                # (if present) or from cinder.conf replication_device.
                replication_policy = None
                if extra_specs:
                    # Prefer an explicit policy from extra specs if set.
                    replication_policy = (
                        extra_specs.get('replication:policy') or
                        extra_specs.get('replication_policy')
                    )

                if not replication_policy:
                    replication_policy = remote_target.get('replication_policy')

                if replication_policy:
                    # Compare policy in a case-insensitive manner.
                    policy_normalized = replication_policy.lower()
                    LOG.debug("replication_policy %(policy)s", {'policy': replication_policy})

                    if policy_normalized == constants.ACTIVE_PP_REP_POLICY:
                        # activeActive policy will also set autoSynchronize
                        # and autoRecover policies on the group.
                        pp_params = {
                            'targets': [{
                                'policies': {
                                    'autoFailover': True,
                                    'activeActive': True
                                }
                            }]
                        }
                    else:
                        # Any explicitly configured policy other than
                        # active-active is considered invalid.
                        msg = (_("Invalid replication policy '%(policy)s' "
                                 "configured for synchronous replication. "
                                 "Only '%(valid)s' is supported.") %
                               {"policy": replication_policy,
                                "valid": constants.ACTIVE_PP_REP_POLICY})
                        LOG.error(msg)
                        raise exception.VolumeBackendAPIException(data=msg)

                    try:
                        super().modify_remote_copy_group(rcg_name, pp_params)
                    except Exception as ex:
                        msg = _("There was an error while modifying remote "
                                 "copy group: %s.") % str(ex)
                        LOG.error(msg)
                        raise exception.VolumeBackendAPIException(data=msg)
                else:
                    # No replication policy explicitly set: do not fall back
                    # to classic/pathManagement PP, but still ensure
                    # autoRecover is enabled for SYNC.
                    opt_auto = {'targets': policy_targets}
                    LOG.debug("Setting policy targets as %(targets)s", {'targets': policy_targets})
                    try:
                        super().modify_remote_copy_group(rcg_name, opt_auto)
                    except Exception as ex:
                        msg = (_("There was an error setting autoRecover for the "
                                 "remote copy group: %s.") % str(ex))
                        LOG.error(msg)
                        raise exception.VolumeBackendAPIException(data=msg)

            # Start the remote copy.
            try:
                super().start_remote_copy_group(rcg_name)
            except Exception as ex:
                msg = (_("There was an error starting remote copy: %s.") %
                       str(ex))
                LOG.error(msg)
                raise exception.VolumeBackendAPIException(data=msg) from ex

            return True
        except Exception as ex:
            self._do_volume_replication_destroy(volume, retype=retype)
            msg = (_("There was an error setting up a remote copy group "
                     "on the 3PAR arrays: ('%s'). The volume will not be "
                     "recognized as replication type.") %
                   str(ex))
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg) from ex
        

    def _do_volume_replication_destroy(self, volume, rcg_name=None,
                                       retype=False):
        """This will completely remove all traces of a remote copy group.

        It should be used when deleting a replication enabled volume
        or if setting up a remote copy group fails. It will try and do the
        following:
        -Stop remote copy
        -Remove volume from Remote Copy Group on main array
        -Delete Remote Copy Group from main array
        -Delete volume from main array
        """
        if not rcg_name:
            rcg_name = self._get_3par_rcg_name(volume)
        vol_name = self._get_3par_vol_name(volume)

        # Stop remote copy.
        try:
            super().stop_remote_copy_group(rcg_name)
        except Exception:
            pass

        # Delete volume from remote copy group on main array.
        try:
            super().remove_volume_from_remote_copy_group_overload(rcg_name, vol_name, removeFromTarget=True)
        except Exception:
            pass

        # Delete remote copy group on main array.
        try:
            super().delete_remote_copy_group_overload(rcg_name)
        except Exception:
            pass

        # Delete volume on the main array.
        try:
            if not retype:
                super().delete_volume(vol_name)
        except flowkit_exceptions.HTTPConflict as ex:
            ex_str = str(ex)
            LOG.debug("flowkit HTTPConflict: %s", ex_str)
            if str(constants.API_ERROR_34) in ex_str:
                # This is a special case which means the
                # volume is part of a volume set.
                self._delete_vvset(volume)
                self.delete_volume(vol_name)
        except Exception:
            pass

    def _delete_replicated_failed_over_volume(self, volume):
        location = volume.get('provider_location')
        rcg_name = self._get_3par_remote_rcg_name(volume, location)
        targets = super().get_remote_copy_group(rcg_name)['targets']
        # When failed over, we want to temporarily disable config mirroring
        # in order to be allowed to delete the volume and remote copy group
        for target in targets:
            target_name = target['targetName']
            super().toggle_remote_copy_config_mirror(target_name,
                                                     mirror_config=False)
        # Do regular volume replication destroy now config mirroring is off
        try:
            self._do_volume_replication_destroy(volume, rcg_name)
        except Exception as ex:
            msg = (_("The failed-over volume could not be deleted: %s") %
                   str(ex))
            LOG.error(msg)
            raise exception.VolumeIsBusy(message=msg) from ex
        finally:
            # Turn config mirroring back on
            for target in targets:
                target_name = target['targetName']
                super().toggle_remote_copy_config_mirror(target_name,
                                                         mirror_config=True)

    def _delete_vvset(self, volume):
        # volume is part of a volume set.
        LOG.debug("_delete_vvset. vol_id: %(id)s", {'id': volume['id']})
        volume_name = self._get_3par_vol_name(volume)
        vvset_name = self._get_3par_vvs_name(volume['id'])

        try:
            # find vvset
            super().get_volumeset(vvset_name)
            # (a) vvset is found:
            # We have a single volume per volume set, so
            # remove the volume set.
            LOG.debug("Deleting vvset: %(name)s", {'name': vvset_name})
            super().delete_volumeset(vvset_name)

        except flowkit_exceptions.HTTPNotFound:
            # (b) vvset not found:
            # - find the vvset name from volume name
            # - remove the volume and leave the vvset
            vvset_name = self.findVolumeSet(volume_name)

            LOG.debug("Removing vol %(volume_name)s from vvset %(vvset_name)s",
                      {'volume_name': volume_name, 'vvset_name': vvset_name})
            super().removeVolumeFromVolumeSet(vvset_name, volume_name)

    # VolumeSet methods
    def findVolumeSet(self, name):
        vvset_names = self.findAllVolumeSets(name)
        vvset_name = None
        if vvset_names:
            vvset_name = vvset_names[0]['name']

        return vvset_name


    def findAllVolumeSets(self, name):
        vvset_names = []
        volume_sets = super().get_volumesets()
        for volume_set in volume_sets['members']:
            if 'setmembers' in volume_set and name in volume_set['setmembers']:
                vvset_names.append(volume_set)
        return vvset_names


    def _get_3par_rcg_name_of_group(self, group_id):
        rcg_name = self._encode_name(group_id)
        rcg = "rcg-%s" % rcg_name
        return rcg[:22]

    def _get_3par_remote_rcg_name_of_group(self, group_id, provider_location):
        return self._get_3par_rcg_name_of_group(group_id) + ".r" + (
            str(provider_location))

    def _get_hpe3par_tiramisu_value(self, volume_type):
        hpe3par_tiramisu = False
        hpe3par_keys = self._get_keys_by_volume_type(volume_type)
        if hpe3par_keys.get('group_replication'):
            hpe3par_tiramisu = (
                hpe3par_keys['group_replication'] == "<is> True")

        return hpe3par_tiramisu

    def _stop_remote_copy_group(self, group):
        # Stop remote copy.
        # Handle both group objects and rcg_name strings
        if isinstance(group, str):
        # Called with rcg_name string
            rcg_name = group
        else:
        # Called with group object
            rcg_name = self._get_3par_rcg_name_of_group(group.id)

        try:
            super().stop_remote_copy_group(rcg_name)
        except Exception:
            LOG.debug("Stopping remote copy group on group: %(group_id)s is "
                      "failed", {'group_id': group.id})

    def _start_remote_copy_group(self, group):
        # Start remote copy.
        # Handle both group objects and rcg_name strings
        if isinstance(group, str):
        # Called with rcg_name string
            rcg_name = group
        else:
        # Called with group object
            rcg_name = self._get_3par_rcg_name_of_group(group.id)

        rcg = super().get_remote_copy_group(rcg_name)
        if not rcg['volumes']:
            return
        try:
            super().start_remote_copy_group(rcg_name)
        except Exception as ex:
            msg = (_("There was an error starting remote copy: %s.") %
                   str(ex))
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg) from ex

    def _check_rep_status_enabled_on_group(self, group):
        """Check replication status for group.

        Group status must be enabled before proceeding with certain
        operations.
        :param group: the group object
        :raises: InvalidInput
        """
        if group.is_replicated:
            if group.replication_status != fields.ReplicationStatus.ENABLED:
                msg = (_('Replication status should be %(status)s for '
                         'replication-enabled group: %(group)s.')
                       % {'status': fields.ReplicationStatus.ENABLED,
                          'group': group.id})
                LOG.error(msg)
                raise exception.InvalidInput(reason=msg)

            if not self._replication_enabled:
                host_backend = volume_utils.extract_host(group.host, 'backend')
                msg = _("replication is not properly configured on backend: "
                        "(backend)%s") % {'backend': host_backend}
                LOG.error(msg)
                raise exception.VolumeBackendAPIException(data=msg)
        else:
            LOG.debug('Replication is not enabled on group %s, '
                      'skip status check.', group.id)

    def _get_replication_mode_from_volume(self, volume):
        volume_type = self._get_volume_type(volume["volume_type_id"])
        replication_mode_num = (
            self._get_replication_mode_from_volume_type(volume_type))

        return replication_mode_num

    def _get_replication_mode_from_volume_type(self, volume_type):
        # Default replication mode is PERIODIC
        replication_mode_num = constants.PERIODIC
        extra_specs = volume_type.get("extra_specs")
        if extra_specs:
            replication_mode = extra_specs.get(
                constants.EXTRA_SPEC_REP_MODE, constants.DEFAULT_REP_MODE)

            replication_mode_num = self._get_remote_copy_mode_num(
                replication_mode)

        return replication_mode_num

    def _get_replication_sync_period_from_volume(self, volume):
        volume_type = self._get_volume_type(volume["volume_type_id"])
        replication_sync_period = (
            self._get_replication_sync_period_from_volume_type(volume_type))

        return replication_sync_period

    def _get_replication_sync_period_from_volume_type(self, volume_type):
        # Default replication sync period is 900s
        replication_sync_period = constants.DEFAULT_SYNC_PERIOD
        rep_mode = constants.DEFAULT_REP_MODE
        extra_specs = volume_type.get("extra_specs")
        if extra_specs:
            replication_sync_period = extra_specs.get(
                constants.EXTRA_SPEC_REP_SYNC_PERIOD, constants.DEFAULT_SYNC_PERIOD)

            replication_sync_period = int(replication_sync_period)
            if not self._is_replication_mode_correct(rep_mode,
                                                     replication_sync_period):
                msg = _("The replication mode was not configured "
                        "correctly in the volume type extra_specs. "
                        "If replication:mode is periodic, "
                        "replication:sync_period must also be specified "
                        "and be between 300 and 31622400 seconds.")
                LOG.error(msg)
                raise exception.VolumeBackendAPIException(data=msg)

        return replication_sync_period

    def _check_replication_matched(self, volume, group):
        """Check volume type and group type.

        This will make sure they do not conflict with each other.
        :param volume: volume to be checked
        :param extra_specs: the extra specifications
        :raises: InvalidInput
        """

        vol_is_re = self._volume_of_replicated_type(volume)
        group_is_re = group.is_replicated

        if not (vol_is_re == group_is_re):
            msg = _('Replication should be enabled or disabled for both '
                    'volume or group. Volume replication status: '
                    '%(vol_status)s, group replication status: '
                    '%(group_status)s') % {
                        'vol_status': vol_is_re, 'group_status': group_is_re}
            raise exception.InvalidInput(reason=msg)

    def _remove_vol_from_remote_copy_group(self, group, volume):
        rcg_name = self._get_3par_rcg_name_of_group(group.id)
        vol_name = self._get_3par_vol_name(volume)

        try:
            # Delete volume from remote copy group on secondary array.
            super().remove_volume_from_remote_copy_group_overload(
                rcg_name, vol_name, removeFromTarget=True)
        except Exception as ex:
            # Start RCG even if we fail to remove volume from it.
            self._start_remote_copy_group(group)
            msg = (_("There was an error removing a volume: %(volume)s from "
                     "Group: %(group)s : %(err)s") %
                   {'volume': volume.get('id'), 'group': group.id,
                    'err': str(ex)})
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg)

    def _add_vol_to_remote_group(self, group, volume):
        # Stop remote copy, so we can add volumes in RCG.
        self._stop_remote_copy_group(group)
        # Add a volume to RCG
        self._add_vol_to_remote_copy_group(group, volume)
        # Start RCG
        self._start_remote_copy_group(group)

    def _add_vol_to_remote_copy_group(self, group, volume):
        rcg_name = self._get_3par_rcg_name_of_group(group.id)
        try:
            rcg = super().get_remote_copy_group(rcg_name)
            # If volumes are not present in RCG, which means we need to set,
            # RCG attributes.
            if not len(rcg['volumes']):
                self._set_rcg_attributes(volume, rcg_name)

            self._add_vol_to_remote(volume, rcg_name)
            # If replication mode is periodic then set sync period on RCG.
            self._set_rcg_sync_period(volume, rcg_name)
        except Exception as ex:
            # Start RCG even if we fail to add volume to it
            self._start_remote_copy_group(group)
            msg = (_("There was an error adding a volume: %(volume)s to "
                     "Group: %(group)s : %(err)s") %
                   {'volume': volume.get('id'), 'group': group.id,
                    'err': str(ex)})
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg) from ex

    def _set_rcg_sync_period(self, volume, rcg_name):
        sync_targets = []
        replication_mode_num = self._get_replication_mode_from_volume(volume)
        replication_sync_period = (
            self._get_replication_sync_period_from_volume(volume))
        if not (replication_mode_num == constants.PERIODIC):
            return

        rcg = super().get_remote_copy_group(rcg_name)

        # Check and see if we are in periodic mode. If we are, update
        # Remote Copy Group to have a sync period.
        if len(rcg['volumes']) and 'syncPeriod' in rcg['targets'][0]:
            if replication_sync_period != int(rcg['targets'][0]['syncPeriod']):
                for target in self._replication_targets:
                    if target['replication_mode'] == replication_mode_num:
                        sync_target = {'targetName': target['backend_id'],
                                       'syncPeriod': replication_sync_period}
                        sync_targets.append(sync_target)

                opt = {'targets': sync_targets}

                try:
                    super().modify_remote_copy_group(rcg_name, opt)
                except Exception as ex:
                    msg = (_("There was an error setting the sync period for "
                             "the remote copy group: %s.") %
                           str(ex))
                    LOG.error(msg)
                    raise exception.VolumeBackendAPIException(data=msg)

    def _set_rcg_attributes(self, volume, rcg_name):
        rcg_targets = []
        vol_settings = self.get_volume_settings_from_type(volume)
        local_cpg = vol_settings['cpg']
        replication_mode_num = self._get_replication_mode_from_volume(volume)

        for target in self._replication_targets:
            if target['replication_mode'] == replication_mode_num:
                cpg = self._get_cpg_from_cpg_map(target['cpg_map'],
                                                 local_cpg)
                rcg_target = {'targetName': target['backend_id'],
                              'remoteUserCPG': cpg,
                              'remoteSnapCPG': cpg}
                rcg_targets.append(rcg_target)

        optional = {'localSnapCPG': vol_settings['snap_cpg'],
                    'localUserCPG': local_cpg,
                    'targets': rcg_targets}

        try:
            super().modify_remote_copy_group(rcg_name, optional)
        except Exception as ex:
            msg = (_("There was an error modifying the remote copy "
                     "group: %s.") %
                   str(ex))
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg)

    def _add_vol_to_remote(self, volume, rcg_name):
        # Add a volume to remote copy group.
        rcg_targets = []
        vol_name = self._get_3par_vol_name(volume)
        replication_mode_num = self._get_replication_mode_from_volume(volume)
        for target in self._replication_targets:
            if target['replication_mode'] == replication_mode_num:
                rcg_target = {'targetName': target['backend_id'],
                              'secVolumeName': vol_name}
                rcg_targets.append(rcg_target)
        optional = {'volumeAutoCreation': True}
        try:
            super().add_volume_to_remote_copy_group(rcg_name, vol_name,
                                                   rcg_targets,
                                                   optional)
        except Exception as ex:
            msg = (_("There was an error adding the volume to the remote "
                     "copy group: %s.") %
                   str(ex))
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg)

    def _is_group_in_remote_copy_group(self, group):
        rcg_name = self._get_3par_rcg_name_of_group(group.id)
        try:
            super().get_remote_copy_group(rcg_name)
            return True
        except flowkit_exceptions.HTTPNotFound:
            return False

    def _remove_volumes_and_remote_copy_group(self, group, volumes):
        if not self._is_group_in_remote_copy_group(group):
            return True

        rcg_name = self._get_3par_rcg_name_of_group(group.id)
        # Stop remote copy.
        try:
            super().stop_remote_copy_group(rcg_name)
        except Exception:
            pass

        for volume in volumes:
            vol_name = self._get_3par_vol_name(volume)
            # Delete volume from remote copy group on secondary array.
            try:
                super().remove_volume_from_remote_copy_group_overload(
                    rcg_name, vol_name, removeFromTarget=True)
            except Exception:
                pass

        # Delete remote copy group on main array.
        try:
            super().delete_remote_copy_group_overload(rcg_name)
        except Exception as ex:
            msg = (_("There was an error deleting RCG %(rcg_name)s: "
                     "%(error)s.") % {'rcg_name': rcg_name, 'error': ex})
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg) from ex

    def _check_tiramisu_configuration_on_volume_types(self, volume_types):
        for volume_type in volume_types:
            self._check_tiramisu_configuration_on_volume_type(volume_type)

    def _check_tiramisu_configuration_on_volume_type(self, volume_type):
        hpe3par_tiramisu = self._get_hpe3par_tiramisu_value(volume_type)
        if not hpe3par_tiramisu:
            msg = _("hpe3par:group_replication is not set on volume type: "
                    "(id)%s") % {'id': volume_type.get('id')}
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg)
        return hpe3par_tiramisu

    def _check_replication_configuration_on_volume_types(self, volume_types):
        for volume_type in volume_types:
            replicated_type = self._is_volume_type_replicated(volume_type)
            if not replicated_type:
                msg = _("replication is not set on volume type: "
                        "(id)%s") % {'id': volume_type.get('id')}
                LOG.error(msg)
                raise exception.VolumeBackendAPIException(data=msg)

    def _check_attributes_of_remote_per_volume_type(self, group):
        rep_modes = []
        rep_sync_periods = []

        for volume_type in group.volume_types:
            replication_mode_num = (
                self._get_replication_mode_from_volume_type(volume_type))
            rep_modes.append(replication_mode_num)

            if replication_mode_num == constants.PERIODIC:
                rep_sync_period = (
                    self._get_replication_sync_period_from_volume_type(
                        volume_type))
                rep_sync_periods.append(rep_sync_period)

        # Check attributes of Remote on all volume types are same or not?
        if not (all(x == rep_modes[0] for x in rep_modes) and
           all(y == rep_sync_periods[0] for y in rep_sync_periods)):

            msg = _("replication mode or replication sync period must be same "
                    "on each volume type of Group:(id)%s") % {'id': group.id}
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg)

    def _create_remote_copy_group_for_group(self, group):
        # Create remote copy group on main array.
        host_backend = volume_utils.extract_host(group.host, 'backend')
        rcg_targets = []
        optional = {}
        if not self._replication_enabled:
            msg = _("replication is not properly configured on backend: "
                    "(backend)%s") % {'backend': host_backend}
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg)

        rcg_name = self._get_3par_rcg_name_of_group(group.id)
        replication_mode_num = (
            self._get_replication_mode_from_volume_type(group.volume_types[0]))

        for target in self._replication_targets:
            if (target['replication_mode'] == replication_mode_num):

                rcg_target = {'targetName': target['backend_id'],
                              'mode': target['replication_mode']}
                rcg_targets.append(rcg_target)

        pool = volume_utils.extract_host(group.host, level='pool')
        domain = self.get_domain(pool)
        if domain:
            optional = {"domain": domain}
        try:
            super().create_remote_copy_group(rcg_name, rcg_targets,
                                              optional)
        except Exception as ex:
            msg = (_("There was an error creating the remote copy "
                     "group: %s.") %
                   str(ex))
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg) from ex

    def _are_targets_in_their_natural_direction(self, rcg):

        targets = rcg['targets']
        for target in targets:
            LOG.debug("target %(target)s, roleReversed: %(roleReversed)s, "
                      "state: %(state)s",
                      {'target': target['targetName'],
                       'roleReversed': target['roleReversed'],
                       'state': target['state']})
            if target['roleReversed'] or (
               target['state'] != constants.RC_GROUP_STARTED):
                LOG.debug("Target %(target)s is not in its natural direction.",
                          {'target': target['targetName']})
                return False

        # Make sure all volumes are fully synced.
        volumes = rcg['volumes']
        for volume in volumes:
            remote_volumes = volume['remoteVolumes']
            for remote_volume in remote_volumes:
                remote_volume_name = remote_volume['remoteVolumeName']
                sync_status = remote_volume.get('syncStatus')
                LOG.debug("remote_volume %(remote_volume)s, syncStatus: "
                          "%(syncStatus)s",
                          {'remote_volume': remote_volume_name,
                           'syncStatus': sync_status})
                if sync_status != (
                   constants.SYNC_STATUS_COMPLETED):
                    return False
        return True

    def _group_failover_replication(self, failover_target, group,
                                    provider_location):
        rcg_name = self._get_3par_rcg_name_of_group(group.id)
        try:
            # Try and stop remote-copy on main array. We eat the
            # exception here because when an array goes down, the
            # groups will stop automatically.
            super().stop_remote_copy_group(rcg_name)
        except Exception:
            pass

        # Failover to secondary array.
        remote_rcg_name = self._get_3par_remote_rcg_name_of_group(
            group.id, provider_location)

        repl_session_mgr = None
        try:
            repl_session_mgr = self._create_replication_client(
                failover_target)
            rcg_wf = RemoteCopyGroupWorkflow(repl_session_mgr, None)

            # Check the current role/direction of the remote copy group
            # on the secondary array. If it is already not in its natural
            # direction, we assume the group has already been failed over
            # and simply skip issuing another failover action while letting
            # Cinder update status as requested.
            remote_rcg = rcg_wf.get_remote_copy_group(remote_rcg_name)
            already_failed_over = any(
                            t.get('roleReversed') for t in remote_rcg.get('targets', [])
                        )
            if already_failed_over:
                LOG.info("Remote copy group %(rcg)s for group %(group)s is "
                         "already in failed-over state; skipping backend "
                         "failover action.",
                         {'rcg': remote_rcg_name, 'group': group.id})
            else:
                LOG.debug("Issuing failover action for remote copy group %(rcg)s for "
                          "group %(group)s.",
                          {'rcg': remote_rcg_name, 'group': group.id})

                rcg_wf.recover_remote_copy_group_from_disaster(
                    remote_rcg_name, constants.RC_ACTION_CHANGE_TO_PRIMARY)
        except Exception as ex:
            msg = (_("There was a problem with the failover: "
                     "(%(error)s) and it was unsuccessful.") %
                   {'error': str(ex)})
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg) from ex
        finally:
            if repl_session_mgr is not None:
                self._destroy_replication_client(repl_session_mgr)


    def _group_failback_replication(self, failback_target, group,
                                    provider_location):
        remote_rcg_name = self._get_3par_remote_rcg_name_of_group(
            group.id, provider_location)
        repl_session_mgr = None
        try:
            repl_session_mgr = self._create_replication_client(failback_target)
            rcg_wf = RemoteCopyGroupWorkflow(repl_session_mgr, None)
            remote_rcg = rcg_wf.get_remote_copy_group(remote_rcg_name)

        except Exception as ex:
            msg = (_("There was a problem with the failback: "
                     "(%(error)s) and it was unsuccessful.") %
                   {'error': str(ex)})
            LOG.error(msg)
            raise exception.VolumeBackendAPIException(data=msg) from ex
        finally:
            if repl_session_mgr is not None:
                self._destroy_replication_client(repl_session_mgr)

        if not self._are_targets_in_their_natural_direction(remote_rcg):
            msg = _("The host is not ready to be failed back. Please "
                    "resynchronize the volumes and resume replication on the "
                    "3PAR backends.")
            LOG.error(msg)
            raise exception.InvalidReplicationTarget(reason=msg)


    #######################################################
    # Functions from fc.py

    def _build_initiator_target_map(self, lookup_service, connector,
                                    remote_client=None):
        """Build the target_wwns and the initiator target map."""

        fc_ports = self.get_active_fc_target_ports(remote_client)
        all_target_wwns = []
        target_wwns = []
        init_targ_map = {}
        numPaths = 0

        for port in fc_ports:
            all_target_wwns.append(port['portWWN'])

        if lookup_service is not None:
            # use FC san lookup to determine which NSPs to use
            # for the new VLUN.
            dev_map = lookup_service.get_device_mapping_from_network(
                connector['wwpns'],
                all_target_wwns)

            for fabric_name in dev_map:
                fabric = dev_map[fabric_name]
                target_wwns += fabric['target_port_wwn_list']
                for initiator in fabric['initiator_port_wwn_list']:
                    if initiator not in init_targ_map:
                        init_targ_map[initiator] = []
                    init_targ_map[initiator] += fabric['target_port_wwn_list']
                    init_targ_map[initiator] = list(set(
                        init_targ_map[initiator]))
                    for _target in init_targ_map[initiator]:
                        numPaths += 1
            target_wwns = list(set(target_wwns))
        else:
            initiator_wwns = connector['wwpns']
            target_wwns = all_target_wwns

            for initiator in initiator_wwns:
                init_targ_map[initiator] = target_wwns

        return target_wwns, init_targ_map, numPaths

    def _create_3par_fibrechan_host(self, hostname, wwns,
                                    domain, persona_id, remote_client=None):
        """Create a 3PAR host.

        Create a 3PAR host, if there is already a host on the 3par using
        the same wwn but with a different hostname, return the hostname
        used by 3PAR.
        """
        LOG.debug("inside _create_3par_fibrechan_host")
        # first search for an existing host
        host_found = None

        if remote_client:
            client_obj = remote_client
        else:
            client_obj = HostWorkflow(self.session_mgr)

        hosts = client_obj.query_host(wwns=wwns)

        if hosts and hosts['members'] and 'name' in hosts['members'][0]:
            host_found = hosts['members'][0]['name']

        if host_found is not None:
            return host_found
        else:
            persona_id = int(persona_id)
            try:
                optional={'domain': domain,
                          'persona': persona_id,
                          'FCWWNs': wwns}
                LOG.debug("calling client_obj.create_host")
                client_obj.create_host(hostname, optional)
            except flowkit_exceptions.HTTPConflict as path_conflict:
                ex_str = str(path_conflict)
                msg = "Create FC host caught HTTP conflict: %s"
                LOG.exception(msg, path_conflict.error)
                with save_and_reraise_exception(reraise=False) as ctxt:
                    if str(constants.EXISTENT_PATH) in ex_str:
                        # Handle exception : EXISTENT_PATH - host WWN/iSCSI
                        # name already used by another host
                        hosts = client_obj.query_host(wwns=wwns)
                        if hosts and hosts['members'] and (
                                'name' in hosts['members'][0]):
                            hostname = hosts['members'][0]['name']
                        else:
                            # re rasise last caught exception
                            ctxt.reraise = True
                    else:
                        # re rasise last caught exception
                        # for other HTTP conflict
                        ctxt.reraise = True
            return hostname

    def _modify_3par_fibrechan_host(self, hostname, wwn,
                                    remote_client):
        if remote_client:
            client_obj = remote_client
        else:
            client_obj = HostWorkflow(self.session_mgr)

        mod_request = {'pathOperation': constants.HOST_EDIT_ADD,
                       'FCWWNs': wwn}
        try:
            client_obj.modify_host(hostname, mod_request)
        except flowkit_exceptions.HTTPConflict as path_conflict:
            msg = ("Modify FC Host %(hostname)s caught "
                   "HTTP conflict msg: %(code)s")
            LOG.exception(msg,
                          {'hostname': hostname,
                           'code': path_conflict.error})

    def _create_host_fc(self, fc_configuration, volume, connector,
                        remote_target=None, src_cpg=None, remote_client=None):
        """Creates or modifies existing 3PAR host."""
        client_obj = HostWorkflow(self.session_mgr)
        host = None
        domain = None
        hostname = self._safe_hostname(connector, fc_configuration)
        LOG.debug("inside _create_host_fc. hostname: %(hostname)s",
                  {'hostname': hostname})
        if remote_target:
            cpg = self._get_cpg_from_cpg_map(
                remote_target['cpg_map'], src_cpg)
            cpg_obj = remote_client.get_cpg(cpg)
            if 'domain' in cpg_obj:
                domain = cpg_obj['domain']
        else:
            cpg = self.get_cpg(volume, allowSnap=True)
            domain = self.get_domain(cpg)

        if not connector.get('multipath'):
            connector['wwpns'] = connector['wwpns'][:1]
        try:
            if remote_target:
                host = remote_client._get_3par_host(hostname)
            else:
                LOG.debug("calling self._get_3par_host")
                host = self._get_3par_host(hostname)

                LOG.debug("host: %(host)s", {'host': host})

                # Check whether host with wwn of initiator present on 3par
                LOG.debug("calling client_obj.query_host")
                hosts = client_obj.query_host(wwns=connector['wwpns'])
                LOG.debug("hosts: %(hosts)s", {'hosts': hosts})
                host, hostname = (
                    self._get_prioritized_host_on_3par(
                        host, hosts, hostname))
        except flowkit_exceptions.HPEStorageException as ex:
            LOG.debug("exception HPEStorageException %s", ex)
            # get persona from the volume type extra specs
            persona_id = self.get_persona_type(volume)
            # host doesn't exist, we have to create it
            LOG.debug("host doesn't exist, we have to create it")
            hostname = self._create_3par_fibrechan_host(hostname,
                                                        connector['wwpns'],
                                                        domain,
                                                        persona_id,
                                                        remote_client)
            if remote_target:
                host = remote_client._get_3par_host(hostname)
            else:
                host = self._get_3par_host(hostname)
            return host, cpg
        else:
            LOG.debug("calling _add_new_wwn_to_host")
            host = self._add_new_wwn_to_host(
                host, connector['wwpns'], remote_client)
            return host, cpg

    def _add_new_wwn_to_host(self, host, wwns, remote_client=None):
        """Add wwns to a host if one or more don't exist.

        Identify if argument wwns contains any world wide names
        not configured in the 3PAR host path. If any are found,
        add them to the 3PAR host.
        """
        # get the currently configured wwns
        # from the host's FC paths
        host_wwns = []
        if 'FCPaths' in host:
            for path in host['FCPaths']:
                wwn = path.get('wwn', None)
                if wwn is not None:
                    host_wwns.append(wwn.lower())

        # lower case all wwns in the compare list
        compare_wwns = [x.lower() for x in wwns]

        # calculate wwns in compare list, but not in host_wwns list
        new_wwns = list(set(compare_wwns).difference(host_wwns))

        # if any wwns found that were not in host list,
        # add them to the host
        if (len(new_wwns) > 0):
            LOG.debug("calling _modify_3par_fibrechan_host")
            self._modify_3par_fibrechan_host(
                host['name'], new_wwns, remote_client)
            if remote_client:
                host = remote_client._get_3par_host(host['name'])
            else:
                host = self._get_3par_host(host['name'])
        else:
            LOG.debug("not reqd to call _modify_3par_fibrechan_host")
            LOG.debug("return host as it is")

        return host

    def _get_user_target(self):
        target_nsp = self.config.hpe3par_target_nsp

        if not target_nsp:
            return None

        # Get target wwn from target nsp
        fc_ports = self.get_active_fc_target_ports()

        target_wwn = None
        for port in fc_ports:
            nsp = port['nsp']
            if target_nsp == nsp:
                target_wwn = port['portWWN']
                break

        if not target_wwn:
            LOG.warning("Did not get wwn for target nsp: "
                        "%(nsp)s", {'nsp': target_nsp})

        return target_wwn

    def merge_dicts(self, dict_1, dict_2):
        keys = set(dict_1).union(dict_2)
        no = []
        return {k: (dict_1.get(k, no) + dict_2.get(k, no)) for k in keys}


    #######################################################
    # Functions from iscsi.py

    def _update_dicts(self, temp_iscsi_ip, iscsi_ip_list, ip, port):
        ip_port = temp_iscsi_ip[ip]['ip_port']
        iscsi_ip_list[ip] = {'ip_port': ip_port,
                             'nsp': port['nsp'],
                             'iqn': port['iSCSIName']}
        del temp_iscsi_ip[ip]

    def get_matched_array_ips_iscsi(self, backend_conf, remote_client):
        # map iscsi_ip-> ip_port
        #             -> iqn
        #             -> nsp
        iscsi_ip_list = {}
        temp_iscsi_ip = {}

        # use the storage ip_addr list for iSCSI configuration
        if len(backend_conf['hpe3par_iscsi_ips']) > 0:
            LOG.debug("ip address specified in hpe3par_iscsi_ips")
            # add port values to ip_addr, if necessary
            for ip_addr in backend_conf['hpe3par_iscsi_ips']:
                if "." in ip_addr:
                    # v4
                    ip = ip_addr.split(':')
                    if len(ip) == 1:
                        temp_iscsi_ip[ip_addr] = (
                            {'ip_port': constants.DEFAULT_ISCSI_PORT})
                    elif len(ip) == 2:
                        temp_iscsi_ip[ip[0]] = {'ip_port': ip[1]}
                elif ":" in ip_addr:
                    # v6
                    if "]" in ip_addr:
                        ip = ip_addr.split(']:')
                        ip_addr_v6 = ip[0]
                        ip_addr_v6 = ip_addr_v6.strip('[')
                        port_v6 = ip[1]
                        temp_iscsi_ip[ip_addr_v6] = {'ip_port': port_v6}
                    else:
                        temp_iscsi_ip[ip_addr] = (
                            {'ip_port': constants.DEFAULT_ISCSI_PORT})
                else:
                    LOG.warning("Invalid IP address format '%s'", ip_addr)

        LOG.debug("temp_iscsi_ip: %(conf_ip)s", {'conf_ip': temp_iscsi_ip})

        # add the single value iscsi_ip_address option to the IP dictionary.
        # This way we can see if it's a valid iSCSI IP. If it's not valid,
        # we won't use it and won't bother to report it, see below
        if 'iscsi_ip_address' in backend_conf:
            if (backend_conf['iscsi_ip_address'] not in temp_iscsi_ip):
                ip = backend_conf['iscsi_ip_address']
                ip_port = backend_conf['iscsi_port']
                temp_iscsi_ip[ip] = {'ip_port': ip_port}

        # get all the valid iSCSI ports from storage
        # when found, add the valid iSCSI ip, ip port, iqn and nsp
        # to the iSCSI IP dictionary
        iscsi_ports = self.get_active_iscsi_target_ports(remote_client)
        LOG.debug("iscsi_ports: %(iscsi_ports)s", {'iscsi_ports': iscsi_ports})

        for port in iscsi_ports:
            ip = port['IPAddr']
            if ip in temp_iscsi_ip:
                self._update_dicts(temp_iscsi_ip, iscsi_ip_list, ip, port)

            if 'iSCSIVlans' in port:
                for vip in port['iSCSIVlans']:
                    ip = vip['IPAddr']
                    if ip in temp_iscsi_ip:
                        LOG.debug("vlan ip: %(ip)s", {'ip': ip})
                        self._update_dicts(temp_iscsi_ip, iscsi_ip_list,
                                           ip, port)

        # if the single value iscsi_ip_address option is still in the
        # temp dictionary it's because it defaults to $my_ip which doesn't
        # make sense in this context. So, if present, remove it and move on.
        if 'iscsi_ip_address' in backend_conf:
            if backend_conf['iscsi_ip_address'] in temp_iscsi_ip:
                del temp_iscsi_ip[backend_conf['iscsi_ip_address']]

        ret_vals = (temp_iscsi_ip, iscsi_ip_list)
        return ret_vals

    def _clear_chap_3par(self, volume):
        """Clears CHAP credentials on a volume.

        Ignore exceptions caused by the keys not being present on a volume.
        """
        vol_wf = VolumeWorkflow(self.session_mgr)

        vol_name = self._get_3par_vol_name(volume)
        LOG.debug("inside _clear_chap_3par. vol_name: %(name)s",
                  {'name': vol_name})

        try:
            vol_wf.removeVolumeMetaData(vol_name, constants.CHAP_USER_KEY)
        except flowkit_exceptions.HPEStorageException:
            # HTTPNotFound
            pass
        except Exception:
            raise

        try:
            vol_wf.removeVolumeMetaData(vol_name, constants.CHAP_PASS_KEY)
        except flowkit_exceptions.HPEStorageException:
            # HTTPNotFound
            pass
        except Exception:
            raise

    def _create_host_iscsi(self, iscsi_configuration, volume, connector,
                           remote_target=None, src_cpg=None, remote_client=None):
        """Creates or modifies existing host on storage"""
        # make sure we don't have the host already
        host = None
        domain = None
        username = None
        password = None
        hostname = self._safe_hostname(connector, iscsi_configuration)
        LOG.debug("inside _create_host_iscsi. hostname: %(hostname)s",
                  {'hostname': hostname})

        client_obj = HostWorkflow(self.session_mgr)
        vol_wf = VolumeWorkflow(self.session_mgr)

        if remote_target:
            cpg = self._get_cpg_from_cpg_map(
                remote_target['cpg_map'], src_cpg)
            cpg_obj = remote_client.get_cpg(cpg)
            if 'domain' in cpg_obj:
                domain = cpg_obj['domain']
        else:
            cpg = self.get_cpg(volume, allowSnap=True)
            domain = self.get_domain(cpg)

        if not remote_target:
            # Get the CHAP secret if CHAP is enabled
            if self._client_conf['hpe3par_iscsi_chap_enabled']:
                vol_name = self._get_3par_vol_name(volume)
                username = vol_wf.getVolumeMetaData(
                    vol_name, constants.CHAP_USER_KEY)['value']
                password = vol_wf.getVolumeMetaData(
                    vol_name, constants.CHAP_PASS_KEY)['value']

        try:
            if remote_target:
                host = remote_client._get_3par_host(hostname)
            else:
                LOG.debug("calling self._get_3par_host")
                host = self._get_3par_host(hostname)

                LOG.debug("host: %(host)s", {'host': host})

                # Check whether host with iqn of initiator present on storage
                LOG.debug("calling client_obj.query_host")
                hosts = client_obj.query_host(iqns=[connector['initiator']])
                LOG.debug("hosts: %(hosts)s", {'hosts': hosts})
                host, hostname = (
                    self._get_prioritized_host_on_3par(
                        host, hosts, hostname))

        except flowkit_exceptions.HPEStorageException:
            # get persona from the volume type extra specs
            persona_id = self.get_persona_type(volume)
            # host doesn't exist, we have to create it
            LOG.debug("host doesn't exist, we have to create it")
            hostname = self._create_3par_iscsi_host(hostname,
                                                    [connector['initiator']],
                                                    domain,
                                                    persona_id,
                                                    remote_client)
        else:
            if not remote_target:
                if 'iSCSIPaths' not in host or len(host['iSCSIPaths']) < 1:
                    LOG.debug("calling _modify_3par_iscsi_host")
                    self._modify_3par_iscsi_host(
                        hostname,
                        connector['initiator'])
                elif (not host['initiatorChapEnabled'] and
                        self._client_conf['hpe3par_iscsi_chap_enabled']):
                    LOG.warning("Host exists without CHAP credentials set and "
                                "has iSCSI attachments but CHAP is enabled. "
                                "Updating host with new CHAP credentials.")

        if remote_target:
            host = remote_client._get_3par_host(hostname)
        else:
            # set/update the chap details for the host
            LOG.debug("calling _set_3par_chaps")
            self._set_3par_chaps(hostname, volume, username, password)
            host = self._get_3par_host(hostname)
        return host, username, password, cpg

    def _create_3par_iscsi_host(self, hostname, iscsi_iqn, domain,
                                persona_id, remote_client=None):
        """Create a host on storage.

        Create a host on storage;
        if there is already a host on the storage
        using the same iqn but with a different hostname,
        then return the hostname used by storage.
        """
        # first search for an existing host
        host_found = None

        if remote_client:
            client_obj = remote_client
        else:
            client_obj = HostWorkflow(self.session_mgr)

        hosts = client_obj.query_host(iqns=iscsi_iqn)

        if hosts and hosts['members'] and 'name' in hosts['members'][0]:
            host_found = hosts['members'][0]['name']

        if host_found is not None:
            return host_found
        else:
            persona_id = int(persona_id)
            try:
                optional = {'domain': domain,
                            'persona': persona_id,
                            'iSCSINames': iscsi_iqn}
                LOG.debug("calling client_obj.create_host")
                client_obj.create_host(hostname, optional)
            except flowkit_exceptions.HTTPConflict as path_conflict:
                ex_str = str(path_conflict)
                msg = "Create iSCSI host caught HTTP conflict code: %s"
                LOG.exception(msg, path_conflict.error)
                with save_and_reraise_exception(reraise=False) as ctxt:
                    if str(constants.EXISTENT_PATH) in ex_str:            
                        # Handle exception : EXISTENT_PATH - host WWN/iSCSI
                        # name already used by another host
                        hosts = client_obj.query_host(iqns=iscsi_iqn)
                        if hosts and hosts['members'] and (
                                'name' in hosts['members'][0]):
                            hostname = hosts['members'][0]['name']
                        else:
                            # re-raise last caught exception
                            ctxt.reraise = True
                    else:
                        # re-raise last caught exception
                        # for other HTTP conflict
                        ctxt.reraise = True
            return hostname

    def _modify_3par_iscsi_host(self, hostname, iscsi_iqn):
        client_obj = HostWorkflow(self.session_mgr)
        mod_request = {'pathOperation': self.HOST_EDIT_ADD,
                       'iSCSINames': [iscsi_iqn]}

        client_obj.modify_host(hostname, mod_request)

    def _set_3par_chaps(self, hostname, volume, username, password):
        """Sets a storage host's CHAP credentials."""
        if not self._client_conf['hpe3par_iscsi_chap_enabled']:
            return

        client_obj = HostWorkflow(self.session_mgr)
        mod_request = {'chapOperation': self.HOST_EDIT_ADD,
                       'chapOperationMode': self.CHAP_INITIATOR,
                       'chapName': username,
                       'chapSecret': password}
        client_obj.modify_host(hostname, mod_request)

    def _get_least_used_nsp_for_host(self, iscsi_ips, hostname):
        """Get the least used NSP for the current host.

        Steps to determine which NSP to use.
            * If only one iSCSI NSP, return it
            * If there is already an active vlun to this host, return its NSP
            * Return NSP with fewest active vluns
        """

        LOG.debug("iscsi_ips: %(ips)s", {'ips': iscsi_ips})
        LOG.debug("hostname: %(name)s", {'name': hostname})
        iscsi_nsps = self._get_iscsi_nsps(iscsi_ips)

        if len(iscsi_nsps) == 0:
            LOG.debug("No candidate iSCSI NSPs for host %(name)s",
                      {'name': hostname})
            return None

        # If there's only one path, use it
        if len(iscsi_nsps) == 1:
            return iscsi_nsps[0]

        # Try to reuse an existing iscsi path to the host
        vlun_wf = VLUNWorkflow(self.session_mgr)
        vluns = vlun_wf.getVLUNs()
        members = vluns.get('members', []) if vluns else []
        for vlun in members:
            if vlun['active']:
                if vlun['hostname'] == hostname:
                    temp_nsp = self.build_nsp(vlun['portPos'])
                    if temp_nsp in iscsi_nsps:
                        # this host already has an iscsi path, so use it
                        return temp_nsp

        # Calculate the least used iscsi nsp
        # Reuses existing NSP when present
        least_used_nsp = self._get_least_used_nsp(members,
                                                  self._get_iscsi_nsps(iscsi_ips))
        return least_used_nsp

    def _get_iscsi_nsps(self, iscsi_ips):
        """Return the list of candidate nsps."""
        nsps = []
        for value in iscsi_ips.values():
            if value not in nsps:
                nsps.append(value['nsp'])
        return nsps

    def _get_ip_using_nsp(self, nsp, iscsi_ips):
        """Return IP associated with given nsp."""
        for (key, value) in iscsi_ips.items():
            if value['nsp'] == nsp:
                return key

    def _get_least_used_nsp(self, vluns, nspss):
        """Return the nsp that has the fewest active vluns."""
        # return only the nsp (node:server:port)
        # count the number of nsps
        nsp_counts = {}
        for nsp in nspss:
            # initialize counts to zero
            nsp_counts[nsp] = 0

        current_least_used_nsp = None

        for vlun in vluns:
            if vlun['active']:
                nsp = self.build_nsp(vlun['portPos'])
                if nsp in nsp_counts:
                    nsp_counts[nsp] = nsp_counts[nsp] + 1

        # identify key (nsp) of least used nsp
        current_smallest_count = sys.maxsize
        for (nsp, count) in nsp_counts.items():
            if count < current_smallest_count:
                current_least_used_nsp = nsp
                current_smallest_count = count
        return current_least_used_nsp



class ReplicateVolumeTask(flow_utils.CinderTask):

    """Task to replicate a volume.

    This is a task for adding/removing the replication feature to volume.
    It is intended for use during retype(). This task has no revert.
    # TODO(sumit): revert back to original volume extra-spec
    """

    def __init__(self, action, **kwargs):
        super(ReplicateVolumeTask, self).__init__(addons=[action])

    def execute(self, common, volume, new_type_id):

        new_replicated_type = False

        if new_type_id:
            new_volume_type = common._get_volume_type(new_type_id)

            extra_specs = new_volume_type.get('extra_specs', None)
            if extra_specs and 'replication_enabled' in extra_specs:
                rep_val = extra_specs['replication_enabled']
                new_replicated_type = (rep_val == "<is> True")

        if (common._volume_of_replicated_type(volume, hpe_tiramisu_check=True)
           and new_replicated_type):
            # Retype from replication enabled to replication enable.
            common._do_volume_replication_destroy(volume, retype=True)
            common._do_volume_replication_setup(
                volume,
                retype=True,
                dist_type_id=new_type_id)
        elif (not common._volume_of_replicated_type(volume,
              hpe_tiramisu_check=True) and new_replicated_type):
            # Retype from replication disabled to replication enable.
            common._do_volume_replication_setup(
                volume,
                retype=True,
                dist_type_id=new_type_id)
        elif common._volume_of_replicated_type(volume,
                                               hpe_tiramisu_check=True):
            # Retype from replication enabled to replication disable.
            common._do_volume_replication_destroy(volume, retype=True)


class ModifyVolumeTask(flow_utils.CinderTask):

    """Task to change a volume's snapCPG and comment.

    This is a task for changing the snapCPG and comment.  It is intended for
    use during retype().  These changes are done together with a single
    modify request which should be fast and easy to revert.

    Because we do not support retype with existing snapshots, we can change
    the snapCPG without using a keepVV.  If snapshots exist, then this will
    fail, as desired.

    This task does not change the userCPG or provisioningType.  Those changes
    may require tunevv, so they are done by the TuneVolumeTask.

    The new comment will contain the new type, VVS and QOS information along
    with whatever else was in the old comment dict.

    The old comment and snapCPG are restored if revert is called.
    """

    def __init__(self, action):
        self.needs_revert = False
        super(ModifyVolumeTask, self).__init__(addons=[action])

    def _get_new_comment(self, old_comment, new_vvs, new_qos,
                         new_type_name, new_type_id):

        # Modify the comment during ModifyVolume
        if not old_comment:
            comment_dict = {}
        else:
            comment_dict = dict(ast.literal_eval(old_comment))
        if 'vvs' in comment_dict:
            del comment_dict['vvs']
        if 'qos' in comment_dict:
            del comment_dict['qos']
        if new_vvs:
            comment_dict['vvs'] = new_vvs
        elif new_qos:
            comment_dict['qos'] = new_qos
        else:
            comment_dict['qos'] = {}

        if new_type_name:
            comment_dict['volume_type_name'] = new_type_name
        else:
            comment_dict.pop('volume_type_name', None)

        if new_type_id:
            comment_dict['volume_type_id'] = new_type_id
        else:
            comment_dict.pop('volume_type_id', None)

        return comment_dict

    def execute(self, common, volume_name, old_snap_cpg, new_snap_cpg,
                old_comment, new_vvs, new_qos, new_type_name, new_type_id):

        comment_dict = self._get_new_comment(
            old_comment, new_vvs, new_qos, new_type_name, new_type_id)

        LOG.debug("API_VERSION: %(ver_1)s ", {'ver_1': common.API_VERSION})

        LOG.info("Modifying %s comments.", volume_name)
        vol_wf = VolumeWorkflow(common.session_mgr)
        vol_wf.modify_volume(
            volume_name,
            {'comment': json.dumps(comment_dict)})
        self.needs_revert = True

    def revert(self, common, volume_name, old_snap_cpg, new_snap_cpg,
               old_comment, **kwargs):
        # snap_cpg not applicable for Alletra MP
        pass

class TuneVolumeTask(flow_utils.CinderTask):

    """Task to change a volume's CPG and/or provisioning type.

    This is a task for changing the CPG and/or provisioning type.
    It is intended for use during retype().

    This task has no revert.  The current design is to do this task last
    and do revert-able tasks first. Un-doing a tunevv can be expensive
    and should be avoided.
    """

    def __init__(self, action, **kwargs):
        super(TuneVolumeTask, self).__init__(addons=[action])

    def execute(self, common, old_tpvv, new_tpvv, old_tdvv, new_tdvv,
                old_cpg, new_cpg, volume_name, new_compression):
        common.tune_vv(old_tpvv, new_tpvv, old_tdvv, new_tdvv,
                       old_cpg, new_cpg, volume_name, new_compression)


class ModifySpecsTask(flow_utils.CinderTask):

    """Set/unset the QOS settings and/or VV set for the volume's new type.

    This is a task for changing the QOS settings and/or VV set.  It is intended
    for use during retype().  If changes are made during execute(), then they
    need to be undone if revert() is called (i.e., if a later task fails).

    For 3PAR, we ignore QOS settings if a VVS is explicitly set, otherwise we
    create a VV set and use that for QOS settings.  That is why they are lumped
    together here.  Most of the decision-making about VVS vs. QOS settings vs.
    old-style scoped extra-specs is handled in existing reusable code.  Here
    we mainly need to know what old stuff to remove before calling the function
    that knows how to set the new stuff.

    Basic task flow is as follows:  Remove the volume from the old externally
    created VVS (when appropriate), delete the old cinder-created VVS, call
    the function that knows how to set a new VVS or QOS settings.

    If any changes are made during execute, then revert needs to reverse them.
    """

    def __init__(self, action):
        self.needs_revert = False
        super(ModifySpecsTask, self).__init__(addons=[action])

    def execute(self, common, volume_name, volume, old_cpg, new_cpg,
                old_vvs, new_vvs, old_qos, new_qos,
                old_flash_cache, new_flash_cache):

        if (old_vvs != new_vvs or
                old_qos != new_qos or
                old_flash_cache != new_flash_cache):

            # Remove VV from old VV Set.
            vs_wf=VolumeSetWorkflow(common.session_mgr)
            if old_vvs is not None and old_vvs != new_vvs:
                vs_wf.removeVolumeFromVolumeSet(old_vvs,volume_name)
                self.needs_revert = True

            # If any extra or qos specs changed then remove the old
            # special VV set that we create.  We'll recreate it
            # as needed.
            vvs_name = common._get_3par_vvs_name(volume['id'])
            try:
                vs_wf.delete_volumeset(vvs_name)
                self.needs_revert = True
            except flowkit_exceptions.HTTPNotFound as ex:
                ex_str = str(ex)
                LOG.debug("flowkit HTTPNotFound: %s", ex_str)
                if str(constants.API_ERROR_102) not in ex_str:
                    LOG.error("Unexpected error when retype() tried to "
                              "deleteVolumeSet(%s)", vvs_name)
                    raise

            if new_vvs or new_qos or new_flash_cache:
                common._add_volume_to_volume_set(
                    volume, volume_name, new_cpg, new_vvs, new_qos,
                    new_flash_cache)
                self.needs_revert = True

    def revert(self, common, volume_name, volume, old_vvs, new_vvs, old_qos,
               old_cpg, **kwargs):
        if self.needs_revert:
            vs_wf = VolumeSetWorkflow(common.session_mgr)
            # If any extra or qos specs changed then remove the old
            # special VV set that we create and recreate it per
            # the old type specs.
            vvs_name = common._get_3par_vvs_name(volume['id'])
            try:
                vs_wf.delete_volumeset(vvs_name)
            except flowkit_exceptions.HTTPNotFound as ex:
                ex_str = str(ex)
                LOG.debug("flowkit HTTPNotFound: %s", ex_str)
                # HTTPNotFound(code=102) is OK.  Set does not exist.
                if str(constants.API_ERROR_102) not in ex_str:
                    LOG.error("Unexpected error when retype() revert "
                              "tried to deleteVolumeSet(%s)", vvs_name)
            except Exception:
                LOG.error("Unexpected error when retype() revert "
                          "tried to deleteVolumeSet(%s)", vvs_name)

            if old_vvs is not None or old_qos is not None:
                try:
                    common._add_volume_to_volume_set(
                        volume, volume_name, old_cpg, old_vvs, old_qos)
                except Exception as ex:
                    LOG.error("%(exception)s: Exception during revert of "
                              "retype for volume %(volume_name)s. "
                              "Original volume set/QOS settings may not "
                              "have been fully restored.",
                              {'exception': ex, 'volume_name': volume_name})

            if new_vvs is not None and old_vvs != new_vvs:
                try:
                    vs_wf.removeVolumeFromVolumeSet(new_vvs, volume_name)
                except Exception as ex:
                    LOG.error("%(exception)s: Exception during revert of "
                              "retype for volume %(volume_name)s. "
                              "Failed to remove from new volume set "
                              "%(new_vvs)s.",
                              {'exception': ex,
                               'volume_name': volume_name,
                               'new_vvs': new_vvs})
