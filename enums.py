from dataclasses import dataclass, asdict
from enum import Enum


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    SUPPORT_STAFF = "support_staff"
    ADMIN = "admin"
    MANAGER = "manager"
    SUPERVISOR = "supervisor"
    WORKER = "worker"

class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"

class TicketPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class EstimateStatus(str, Enum):
    DRAFT = "draft"
    SENT = "sent"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"

class JobStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    RESCHEDULED = "rescheduled"

@dataclass
class EmailContext:
    """Context data for email templates"""
    business_name: str = ""
    client_name: str = ""
    client_email: str = ""
    estimate_id: str = ""
    amount: float = 0.0
    property_type: str = ""
    city: str = ""
    date: str = ""
    time: str = ""
    approval_link: str = ""
    review_link: str = ""

    def format_template(self, template: str) -> str:
        """Safely format email template with available context"""
        try:
            result = template
            for key, value in asdict(self).items():
                placeholder = f"{{{key}}}"
                if placeholder in result:
                    result = result.replace(placeholder, str(value) if value else f"[{key}]")
            return result
        except Exception:
            return template
