"""Utilities for assembling NVMe/TCP connection data from backend state."""


def get_configured_nvme_ip_map(storage_client, nvme_ips, vlun_workflow_cls,
                               logger=None):
    
    vlun_wf = vlun_workflow_cls(storage_client.session_mgr)
    nvme_ip_list, nvme_port_list = vlun_wf.get_matched_array_ips_and_ports(
        nvme_ips)

    if logger is not None:
        logger.debug("nvme_ip_list: %(ip_list)s", {'ip_list': nvme_ip_list})
        logger.debug("nvme_port_list: %(ports)s", {'ports': nvme_port_list})

    return nvme_ip_list, nvme_port_list


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

    portals, target_nqns = vlun_wf.create_vlun_nvme(
        vol_name, host, nvme_ips)
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


