"""Invitations without widgets: what each permission allows, and how invitations are grouped for display.

An invitation grants one permission on one database, so sharing SELECT and INSERT with someone is two
invitations. The screens show them per person and database instead."""

# (name in the API, what a shared user may then do) in the order they are offered
PERMISSIONS = [
    ("SELECT_ROLE", "read the tables and their rows"),
    ("INSERT_ROLE", "add rows"),
    ("UPDATE_ROLE", "change rows"),
    ("DELETE_ROLE", "delete rows"),
]
_ORDER = {name: index for index, (name, _) in enumerate(PERMISSIONS)}

# Invitations still in force: waiting for an answer, or granting access
ACTIVE = ("PENDING", "ACCEPTED")


def permission_label(name):
    """SELECT_ROLE -> SELECT"""
    return name[:-len("_ROLE")] if name and name.endswith("_ROLE") else (name or "?")


def describe_permissions(names):
    """The permissions as one line, in the order they are offered: 'SELECT, INSERT'."""
    ordered = sorted(set(names), key=lambda name: _ORDER.get(name, len(_ORDER)))
    return ", ".join(permission_label(name) for name in ordered)


def received_groups(invitations, user_id):
    """Pending and accepted invitations sent to this user, one group per database and sender.

    [{"status", "fromUsername", "dbConnectionId", "dbName", "dbType", "invitations": [...]}],
    the pending groups first."""
    groups = {}
    for invitation in invitations:
        if invitation.get("toUserId") != user_id or invitation.get("status") not in ACTIVE:
            continue
        key = (invitation["status"], invitation.get("fromUserId"), invitation.get("dbConnectionId"))
        group = groups.setdefault(key, {
            "status": invitation["status"],
            "fromUsername": invitation.get("fromUsername") or f"user {invitation.get('fromUserId')}",
            "dbConnectionId": invitation.get("dbConnectionId"),
            "dbName": invitation.get("dbName") or f"database {invitation.get('dbConnectionId')}",
            "dbType": invitation.get("dbType") or "",
            "invitations": [],
        })
        group["invitations"].append(invitation)
    return sorted(groups.values(), key=lambda group: group["status"] != "PENDING")


def pending_count(invitations, user_id):
    """How many invitations rows wait for this user's answer."""
    return sum(1 for group in received_groups(invitations, user_id) if group["status"] == "PENDING")


def shares_by_connection(invitations, user_id):
    """For each database shared with this user: connection id -> (owner's username, [permission names])."""
    shares = {}
    for group in received_groups(invitations, user_id):
        if group["status"] != "ACCEPTED":
            continue
        owner, names = shares.setdefault(group["dbConnectionId"], (group["fromUsername"], []))
        names.extend(invitation.get("permission") for invitation in group["invitations"])
    return shares


def sent_for_connection(invitations, user_id, connection_id):
    """What this user currently offers on one database: the newest invitation per person and permission,
    unless it was revoked. Older ones (declined, then sent again) only tell history."""
    current = {}
    for invitation in invitations:  # the API lists the newest first
        if invitation.get("fromUserId") != user_id or invitation.get("dbConnectionId") != connection_id:
            continue
        current.setdefault((invitation.get("toUserId"), invitation.get("permission")), invitation)
    rows = [invitation for invitation in current.values() if invitation.get("status") != "REVOKED"]
    return sorted(rows, key=lambda invitation: ((invitation.get("toUsername") or "").lower(),
                                                _ORDER.get(invitation.get("permission"), len(_ORDER))))
