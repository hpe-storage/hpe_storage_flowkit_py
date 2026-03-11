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
from hpe_storage_flowkit_py.v1.src.validators.host_validator import validate_host_params
from hpe_storage_flowkit_py.v1.src.core.exceptions import InvalidParameterValue


# Stable explicit mapping (avoid globals() for clarity & safety)
# Added 2 more persona values
Host_Persona_Value = {
    'GENERIC': 1,
    'GENERIC_ALUA': 2,
    'GENERIC_LEGACY': 3,
    'HPUX_LEGACY': 4,
    'AIX_LEGACY': 5,
    'EGENERA': 6,
    'ONTAP_LEGACY': 7,
    'VMWARE': 8,
    'OPENVMS': 9,
    'HPUX': 10,
    'WINDOWS_SERVER': 11,
    'AIX': 12,
    'SOLARIS': 13
}

# CHAP operation modes
CHAP_INITIATOR = 1
CHAP_TARGET = 2

# Host edit operations (path / chap add/remove)
HOST_EDIT_ADD = 1
HOST_EDIT_REMOVE = 2

# Host path operations (for adding/removing iSCSI / FC paths)
PATH_OPERATION_ADD = 1
PATH_OPERATION_REMOVE = 2

def preprocess_create_host(name,iscsiNames=None, FCWwns=None, host_domain=None, host_persona=None):
    validate_host_params(name, iscsiNames, FCWwns, host_domain, host_persona)
    payload = {}
    if iscsiNames:
        payload['iSCSINames'] = iscsiNames
    if FCWwns:
        payload['FCWWNs'] = FCWwns
    if host_domain is not None:
        payload['domain'] = host_domain
    if host_persona is not None:
        payload['persona'] = Host_Persona_Value[host_persona]
    return payload


def preprocess_modify_host(name, new_name=None, persona=None):
    validate_host_params(name=name)
    validate_host_params(name=new_name, host_persona=persona)
    payload = {"newName": new_name}
    if persona is not None:
        payload['persona'] = persona
    return payload

def preprocess_initiator_chap(name, chap_name, chap_secret, chap_secret_hex=False):
    validate_host_params(name=name, chap_name=chap_name, chap_secret=chap_secret, chap_secret_hex=chap_secret_hex)
    # Custom CHAP parameter validations per requirement
    if chap_name is None:
        raise InvalidParameterValue('chap_name', "Chap name must be a non-empty string.")
    if chap_secret is None:
        raise InvalidParameterValue('chap_secret', "Chap secret is null.")
    if chap_secret_hex and len(chap_secret) != 32:
        raise InvalidParameterValue('chap_secret', "Chap secret hex is false and chap secret less than 32 characters.")
    if (not chap_secret_hex) and (len(chap_secret) < 12 or len(chap_secret) > 16):
        raise InvalidParameterValue('chap_secret', "Chap secret hex is true and chap secret not between 12 and 16 characters.")
    payload = {
				'chapOperationMode': CHAP_INITIATOR,
				'chapOperation': HOST_EDIT_ADD,
				'chapName': chap_name,
				'chapSecret': chap_secret,
				'chapSecretHex': chap_secret_hex
			}
    return payload

def preprocess_target_chap(name, chap_name, chap_secret, chap_secret_hex=False):
    validate_host_params(name=name, chap_name=chap_name, chap_secret=chap_secret, chap_secret_hex=chap_secret_hex)
    # Custom CHAP parameter validations per requirement
    if chap_name is None:
        raise InvalidParameterValue('chap_name', "Chap name must be a non-empty string.")
    if chap_secret is None:
        raise InvalidParameterValue('chap_secret', "Chap secret is null.")
    if chap_secret_hex and len(chap_secret) != 32:
        raise InvalidParameterValue('chap_secret', "Chap secret hex is false and chap secret less than 32 characters.")
    if (not chap_secret_hex) and (len(chap_secret) < 12 or len(chap_secret) > 16):
        raise InvalidParameterValue('chap_secret', "Chap secret hex is true and chap secret not between 12 and 16 characters.")
    payload = {
				'chapOperationMode': CHAP_TARGET,
				'chapOperation': HOST_EDIT_ADD,
				'chapName': chap_name,
				'chapSecret': chap_secret,
				'chapSecretHex': chap_secret_hex
			}
    return payload

def prepare_iqn_wwn_queryurl(iqns=None, wwns=None):
    """Prepare query URL parameters for iSCSI names and WWNs.

    Returns a string suitable for appending to a URL.
    """
    wwnsQuery = ''
    if wwns:
        tmpQuery = []
        for wwn in wwns:
            tmpQuery.append('wwn==%s' % wwn)
        wwnsQuery = 'FCPaths[%s]' % ' OR '.join(tmpQuery)

    iqnsQuery = ''
    if iqns:
        tmpQuery = []
        for iqn in iqns:
            tmpQuery.append('name==%s' % iqn)
        iqnsQuery = 'iSCSIPaths[%s]' % ' OR '.join(tmpQuery)

    query = ''
    if wwnsQuery and iqnsQuery:
        query = '%s OR %s' % (wwnsQuery, iqnsQuery)
    elif wwnsQuery:
        query = wwnsQuery
    elif iqnsQuery:
        query = iqnsQuery

    query = '"%s"' % query if query else ''

    return query


def normalize_wwn(wwn):
    """Normalize WWN by removing separators and converting to lowercase.
    
    Args:
        wwn: WWN string to normalize
        
    Returns:
        Normalized WWN string or None if input is None
    """
    if wwn is None:
        return None
    return ''.join(ch for ch in str(wwn).lower() if ch not in {':', '-', ' '})
