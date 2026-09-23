from enum import Enum

class DataQualityEnum(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"

class FreshnessEnum(str, Enum):
    FRESH = "FRESH"
    ACCEPTABLE = "ACCEPTABLE"
    STALE = "STALE"
    EXPIRED = "EXPIRED"

class OperationalStatusEnum(str, Enum):
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    BLOCKED = "BLOCKED"
    RESTRICTED = "RESTRICTED"
    OPEN = "OPEN"
    LIMITED = "LIMITED"
    CLOSED = "CLOSED"

class StateTypeEnum(str, Enum):
    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    PREDICTED = "PREDICTED"
    SIMULATION = "SIMULATION"

class PriorityClassEnum(str, Enum):
    IMMEDIATE = "IMMEDIATE"
    SHORT_TERM = "SHORT_TERM"
    MEDIUM_TERM = "MEDIUM_TERM"

class ResourceCategoryEnum(str, Enum):
    SHELTER = "SHELTER"
    WATER = "WATER"
    HEALTHCARE = "HEALTHCARE"
    SANITATION = "SANITATION"
    FOOD = "FOOD"
    UTILITIES = "UTILITIES"
    EMERGENCY_SERVICES = "EMERGENCY_SERVICES"

class AllocationStatusEnum(str, Enum):
    RECOMMENDED = "RECOMMENDED"
    ACCEPTED = "ACCEPTED"
    OVERRIDDEN = "OVERRIDDEN"
    REJECTED = "REJECTED"
    UNMET = "UNMET"

class RoleEnum(str, Enum):
    ADMIN = "ADMIN"
    AUTHORITY = "AUTHORITY"
    DATA_OPERATOR = "DATA_OPERATOR"
    VIEWER = "VIEWER"

class JobStatusEnum(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
