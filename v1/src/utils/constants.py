
VLUN_TYPE_EMPTY = 1
VLUN_TYPE_PORT = 2
VLUN_TYPE_HOST = 3
VLUN_TYPE_MATCHED_SET = 4
VLUN_TYPE_HOST_SET = 5


THIN = 2
DEDUP = 6
CONVERT_TO_THIN = 1
CONVERT_TO_FULL = 2
CONVERT_TO_DEDUP = 4

# v2 replication constants
SYNC = 1
PERIODIC = 2
EXTRA_SPEC_REP_MODE = "replication:mode"
EXTRA_SPEC_REP_SYNC_PERIOD = "replication:sync_period"
#EXTRA_SPEC_PEER_PERSISTENCE = "replication:peer_persistence"
RC_ACTION_CHANGE_TO_PRIMARY = 7
DEFAULT_REP_MODE = 'periodic'
DEFAULT_SYNC_PERIOD = 900
#DEFAULT_PEER_PERSISTENCE = 'classic'
RC_GROUP_STARTED = 3
SYNC_STATUS_COMPLETED = 3
FAILBACK_VALUE = 'default'
ACTIVE_PP_REP_POLICY = 'active-active'

#API version constants
API_VERSION_R5 = 100500000
COMPRESSION_API_VERSION = 30301215


# Valid values for volume type extra specs
# The first value in the list is the default value
valid_prov_values = ['thin', 'full', 'dedup']
valid_persona_values = ['2 - Generic-ALUA',
                        '1 - Generic',
                        '3 - Generic-legacy',
                        '4 - HPUX-legacy',
                        '5 - AIX-legacy',
                        '6 - EGENERA',
                        '7 - ONTAP-legacy',
                        '8 - VMware',
                        '9 - OpenVMS',
                        '10 - HPUX',
                        '11 - WindowsServer']

hpe_qos_keys = ['minIOPS', 'maxIOPS', 'minBWS', 'maxBWS', 'latency',
                'priority']
qos_priority_level = {'low': 1, 'normal': 2, 'high': 3}
hpe3par_valid_keys = ['cpg', 'snap_cpg', 'provisioning', 'persona', 'vvs',
                      'flash_cache', 'compression', 'group_replication',
                      'convert_to_base']


TASK_DONE = 1
TASK_ACTIVE = 2
TASK_CANCELLED = 3
TASK_FAILED = 4

SET_MEM_ADD = 1
SET_MEM_REMOVE = 2
SET_RESYNC_PHYSICAL_COPY = 3
SET_STOP_PHYSICAL_COPY = 4

PORT_MODE_TARGET = 2
PORT_MODE_INITIATOR = 3
PORT_MODE_PEER = 4

PORT_TYPE_HOST = 1
PORT_TYPE_DISK = 2
PORT_TYPE_FREE = 3
PORT_TYPE_IPORT = 4
PORT_TYPE_RCFC = 5
PORT_TYPE_PEER = 6
PORT_TYPE_RCIP = 7
PORT_TYPE_ISCSI = 8
PORT_TYPE_CNA = 9

PORT_PROTO_FC = 1
PORT_PROTO_ISCSI = 2
PORT_PROTO_FCOE = 3
PORT_PROTO_IP = 4
PORT_PROTO_SAS = 5
PORT_PROTO_NVME = 6

PORT_STATE_READY = 4
PORT_STATE_SYNC = 5
PORT_STATE_OFFLINE = 10

HOST_EDIT_ADD = 1
HOST_EDIT_REMOVE = 2

EXISTENT_PATH = 73

# WSAPI error codes
API_ERROR_150 = 150
API_ERROR_187 = 187
API_ERROR_102 = 102
API_ERROR_23 = 23
API_ERROR_215 = 215
API_ERROR_29 = 29
API_ERROR_40 = 40
API_ERROR_34 = 34
API_ERROR_151 = 151
API_ERROR_32 = 32


# reqd by iSCSI protocol
DEFAULT_ISCSI_PORT = 3260
CHAP_USER_KEY = "HPQ-cinder-CHAP-name"
CHAP_PASS_KEY = "HPQ-cinder-CHAP-secret"


# Input/output (total read/write) operations per second.
THROUGHPUT = 'throughput'
# Data processed (total read/write) per unit time: kilobytes per second.
BANDWIDTH = 'bandwidth'
# Response time (total read/write): microseconds.
LATENCY = 'latency'
# IO size (total read/write): kilobytes.
IO_SIZE = 'io_size'
# Queue length for processing IO requests
QUEUE_LENGTH = 'queue_length'
# Average busy percentage
AVG_BUSY_PERC = 'avg_busy_perc'

# general constants
HOST_DOES_NOT_EXISTS = "host does not exist"