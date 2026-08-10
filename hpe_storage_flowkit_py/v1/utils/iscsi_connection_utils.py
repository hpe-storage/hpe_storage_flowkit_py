"""Utilities for iSCSI credential handling."""

import re


def create_iscsi_export_credentials(storage_client,vol_name, connector,
                                    chap_enabled, generate_password,
                                    volume_workflow_cls,
                                    host_workflow_cls,
                                    vlun_workflow_cls,
                                    flowkit_exceptions,
                                    constants,
                                    logger=None):
    if not chap_enabled:
        if logger is not None:
            logger.debug("iscsi_chap is not enabled. returning")
        return None, None

    vlun_wf = vlun_workflow_cls(storage_client.session_mgr)
    host_wf = host_workflow_cls(storage_client.session_mgr)
    vol_wf = volume_workflow_cls(storage_client.session_mgr)

    if logger is not None:
        logger.debug("iscsi_chap is enabled")

    chap_username = connector['host']
    chap_password = None

    try:
        if logger is not None:
            logger.debug("get VLUNs and host_info")
        vluns = vlun_wf.getHostVLUNs(chap_username)
        host_info = host_wf.get_host(chap_username)

        if not host_info['initiatorChapEnabled'] and logger is not None:
            logger.warning("Host has no CHAP key, but CHAP is enabled.")

    except flowkit_exceptions.HPEStorageException:
        chap_password = generate_password(16)
        if logger is not None:
            logger.warning("No host or VLUNs exist. Generating new "
                           "CHAP key.")
    else:
        chap_exists = False

        for vlun in vluns:
            if not vlun['active']:
                continue

            if ('remoteName' in vlun and re.match('iqn.*', vlun['remoteName'])):
                try:
                    chap_password = vol_wf.getVolumeMetaData(
                        vlun['volumeName'], constants.CHAP_PASS_KEY)[
                            'value']
                    chap_exists = True
                    break
                except flowkit_exceptions.HPEStorageException:
                    if logger is not None:
                        logger.debug("The VLUN %s is missing CHAP credentials "
                                     "but CHAP is enabled. Skipping.",
                                     vlun['remoteName'])
            elif logger is not None:
                logger.warning("Non-iSCSI VLUN detected.")

        if not chap_exists:
            chap_password = generate_password(16)
            if logger is not None:
                logger.warning("No VLUN contained CHAP credentials. "
                               "Generating new CHAP key.")

    vol_wf.setVolumeMetaData(
        vol_name, constants.CHAP_USER_KEY, chap_username)
    vol_wf.setVolumeMetaData(
        vol_name, constants.CHAP_PASS_KEY, chap_password)

    return chap_username, chap_password


def ensure_iscsi_export_credentials(storage_client, vol_name,
                                    volume_workflow_cls,
                                    flowkit_exceptions,
                                    constants,
                                    logger=None):
    vol_wf = volume_workflow_cls(storage_client.session_mgr)
    try:
        vol_wf.get_volume(vol_name)
    except flowkit_exceptions.HPEStorageException:
        if logger is not None:
            logger.error("Volume %s doesn't exist on array.", vol_name)
        return None

    if logger is not None:
        logger.debug("get all volume metadata")
    metadata = vol_wf.getAllVolumeMetaData(vol_name)

    username = None
    password = None
    for member in metadata['members']:
        if member['key'] == constants.CHAP_USER_KEY:
            username = member['value']
        elif member['key'] == constants.CHAP_PASS_KEY:
            password = member['value']

    return username, password