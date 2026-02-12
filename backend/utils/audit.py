from datetime import datetime

from .. import database


def log_action(action: str, entity_type: str, entity_id: str, entity_name: str, changes: dict = None):
    """Log an action to the audit log"""
    if not database.connected or database.audit_logs is None:
        return

    try:
        database.audit_logs.insert_one({
            "action": action,
            "entity_type": entity_type,
            "entity_id": str(entity_id),
            "entity_name": entity_name,
            "changes": changes or {},
            "created_at": datetime.utcnow()
        })
    except Exception as e:
        print(f"Error logging action: {e}")
