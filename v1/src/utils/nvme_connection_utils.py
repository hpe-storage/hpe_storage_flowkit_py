"""Utilities for assembling NVMe/TCP connection data from backend state."""

import logging
logger = logging.getLogger('flowkit')

def get_configured_nvme_ip_map(storage_client, nvme_ips, vlun_workflow_cls,
                               logger=None):
    
    vlun_wf = vlun_workflow_cls(storage_client.session_mgr)
    nvme_ip_list, nvme_port_list = vlun_wf.get_matched_array_ips_and_ports(
        nvme_ips)

    if logger is not None:
        logger.debug("nvme_ip_list: %(ip_list)s", {'ip_list': nvme_ip_list})
        logger.debug("nvme_port_list: %(ports)s", {'ports': nvme_port_list})

    return nvme_ip_list, nvme_port_list


def create_vlun_nvme(vlun_wf, vol_name_3par, host, nvme_ips):
    """Create a VLUN for NVMe host.
    :param vlun_wf: VLUNWorkflow instance.
    :param vol_name_3par: The name of the volume on 3PAR.
    :param host: The host object containing host information.
    :param nvme_ips: The NVMe IPs to use for the VLUN.
    :returns: A tuple containing a list of portals and target NQNs.
    :rtype: tuple
    """

    # Collect all existing VLUNs for this volume/host combination.
    existing_vluns = vlun_wf.find_existing_vluns(vol_name_3par, host)
    logger.debug("existing_vluns: %(ev)s", {'ev': existing_vluns})
    host_name = host['name']
    portals = []
    target_nqns = []
    lun_id = None
    # check for an already existing VLUN matching the
    # nsp for this nvme IP. If one is found, use it
    # instead of creating a new VLUN.
    if existing_vluns:
        for v in existing_vluns:
            lun_id = v['lun']
            logger.info("vlun exists for host name: %(host)s"
                         " with lun: %(lun)s",
                         {'host': host_name, 'lun': v['lun']})
            break
    else:
        params = {}
        logger.info("Lun ID is None so setting autoLun to True")
        params['autoLun'] = True
        params['maxAutoLun'] = 0
        params['lun'] = 0
        vlun_wf.create_vlun(vol_name_3par, host_name, params)

    target_portal_ips = list(nvme_ips.keys())
    for nvme_ip in target_portal_ips:
        portals.append(
            (nvme_ip, nvme_ips[nvme_ip]['ip_port'], 'tcp')
            )
    vlun = vlun_wf.getVLUN(vol_name_3par)
    nqn_of_vlun = vlun['Subsystem_NQN']
    logger.info("nqn_of_vlun: %(nqn)s", {'nqn': nqn_of_vlun})
    target_nqns.append(nqn_of_vlun)

    ret_vals = (portals, target_nqns)
    return ret_vals


def initialize_nvme_connection(storage_client, vol_name, connector, nvme_ips,
                               vlun_workflow_cls, volume_workflow_cls,
                               logger=None):
    vlun_wf = vlun_workflow_cls(storage_client.session_mgr)
    vol_wf = volume_workflow_cls(storage_client.session_mgr)
    host_nqn = connector['nqn']

    host = vlun_wf.getHostByNqn(host_nqn)
    if logger is not None:
        logger.debug("host: %(host)s", {'host': host})

    if not host:
        raise LookupError(host_nqn)

    portals, target_nqns = create_vlun_nvme(vlun_wf, vol_name, host, nvme_ips)
    vlun = vlun_wf.getVLUN(vol_name)
    storage_volume = vol_wf.get_volume(vol_name)

    return {
        'portals': portals,
        'target_nqn': target_nqns[0],
        'host_nqn': host_nqn,
        'target_lun': vlun.get('lun', 0),
        'vol_uuid': storage_volume['nguid'],
        'access_mode': 'rw',
    }


