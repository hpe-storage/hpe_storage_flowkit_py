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
from hpe_storage_flowkit_py.v1.src.validators.volume_validator import validate_volume_params

def convert_to_binary_multiple(size, size_unit):
    size_mib = 0
    if size_unit == 'GiB':
        size_mib = size * 1024
    elif size_unit == 'TiB':
        size_mib = size * 1048576
    elif size_unit == 'MiB':
        size_mib = size
    return int(size_mib)

def get_volume_type(volume_type):
    enum_type = ''
    if volume_type == 'thin':
        enum_type = ['TPVV', 1]
    elif volume_type == 'thin_dedupe':
        enum_type = ['TDVV', 3]
    elif volume_type == 'full':
        enum_type = ['FPVV', 2]
    return enum_type

def preprocess_create_volume(name, cpg, size, size_unit, params):
    """
    Enhanced: Handles Primera logic and optional params with full validation.
    """
    # Extract and validate parameters
    type = params["type"]
    snapCPG = params["snap_cpg"]
    size_in_mib = convert_to_binary_multiple(size=size, size_unit=size_unit)
    validate_volume_params(name, size_in_mib, cpg)

    # Build payload with type-specific settings
    payload = {
        "name": name,
        "cpg": cpg,
        "sizeMiB": size_in_mib
    }

    tpvv = False
    tdvv = False
    if type == 'thin':
        tpvv = True
    elif type == 'thin_dedupe':
        tdvv = True
    optional = {
        'tpvv': tpvv,
        'reduce': tdvv,
        'snapCPG': snapCPG,
        'objectKeyValues': [
            {'key': 'type', 'value': 'ansible-3par-client'}
        ]
    }
    if optional:
        payload.update(optional)

    return payload


def preprocess_delete_volume(name):
    validate_volume_params(name)
    return name

def preprocess_grow_volume(name,prev_size,operation,params):
    validate_volume_params(name)
    mod_size=convert_to_binary_multiple(size=params["size"] ,size_unit=params["size_unit"])
    if operation=="grow":
        new_size=mod_size+prev_size
        return new_size
    else:
        if prev_size>=mod_size:
            return 0
        return int(convert_to_binary_multiple(size=params["size"] ,size_unit=params["size_unit"]))-int(prev_size)
    

def preprocess_tune_volume( name, operation,volume_info,params):
        """
        Tune volume with full parameter processing and validation.
        """
        validate_volume_params(name)
        
        if operation == 'convert_type':
            type = params["type"]
            cpg = params["cpg"]
            keep_vv = params["keep_vv"]
            compression = params["compression"]
            
            # Get current volume properties
            # volume_info = self.get_volume(name=name)
            compression_state = volume_info.get("compressionState", None)
            if compression_state == 2 or compression_state == 3 or compression_state == 4 or compression_state is None:
                compression_state = False
            else:
                compression_state = True
                
            provisioning_type = volume_info.get("provisioningType", 0)
            if provisioning_type == 1:
                volume_type = 'FPVV'
            elif provisioning_type == 2:
                volume_type = 'TPVV'
            elif provisioning_type == 6:
                volume_type = 'TDVV'
            else:
                volume_type = 'UNKNOWN'
                
            if (volume_type != get_volume_type(type)[0] or volume_type == 'UNKNOWN' or compression != compression_state):
                new_vol_type = get_volume_type(type)[1]
                usr_cpg = 1
                optional = {'userCPG': cpg, 'conversionOperation': new_vol_type, 'keepVV': keep_vv}
                
                info = {'action': 6, 'tuneOperation': usr_cpg}
                if optional:
                    dict3 = info.copy()
                    dict3.update(optional)
                    info = dict3
                    
                return info
                
        elif operation == 'change_snap_cpg':
            snap_cpg = params['snap_cpg']
            # current_snap_cpg = self.get_volume(name).get('snapCPG', 0)
            current_snap_cpg = volume_info.get('snapCPG', 0)
            if current_snap_cpg != snap_cpg:
                snp_cpg = 2
                info = {'action': 6, 'tuneOperation': snp_cpg, 'snapCPG': snap_cpg}
                return info
                
        elif operation == 'change_user_cpg':
            cpg = params['cpg']
            # current_cpg = self.get_volume(name).get('usrCPG', 0)
            current_cpg = volume_info.get('userCPG', 0)
            if current_cpg != cpg:
                usr_cpg = 1
                info = {'action': 6, 'tuneOperation': usr_cpg, 'userCPG': cpg}
                return info