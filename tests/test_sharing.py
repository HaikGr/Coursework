import unittest

from dbmanager.model.sharing import (
    describe_permissions, pending_count, permission_label, received_groups, sent_for_connection,
    shares_by_connection
)

ANN, BOB, CAROL = 7, 9, 11


def invitation(invitation_id, sender, recipient, connection_id, permission, status):
    names = {ANN: "ann", BOB: "bob", CAROL: "carol"}
    return {"id": invitation_id, "fromUserId": sender, "fromUsername": names[sender], "toUserId": recipient,
            "toUsername": names[recipient], "dbConnectionId": connection_id, "dbName": f"db{connection_id}",
            "dbType": "POSTGRESQL", "permission": permission, "status": status}


class PermissionTextTest(unittest.TestCase):
    def test_permissions_read_as_sql_verbs_in_a_fixed_order(self):
        self.assertEqual(permission_label("UPDATE_ROLE"), "UPDATE")
        self.assertEqual(describe_permissions(["DELETE_ROLE", "SELECT_ROLE", "SELECT_ROLE"]), "SELECT, DELETE")


class ReceivedTest(unittest.TestCase):
    def setUp(self):
        # Newest first, as the API lists them
        self.invitations = [
            invitation(6, ANN, BOB, 1, "SELECT_ROLE", "PENDING"),     # sent by ann: not hers to answer
            invitation(5, CAROL, ANN, 3, "SELECT_ROLE", "ACCEPTED"),
            invitation(4, BOB, ANN, 2, "INSERT_ROLE", "PENDING"),
            invitation(3, BOB, ANN, 2, "SELECT_ROLE", "PENDING"),
            invitation(2, BOB, ANN, 2, "DELETE_ROLE", "DECLINED"),
            invitation(1, CAROL, ANN, 3, "UPDATE_ROLE", "REVOKED"),
        ]

    def test_offers_are_grouped_per_database_and_sender_waiting_ones_first(self):
        groups = received_groups(self.invitations, ANN)
        self.assertEqual([(group["status"], group["fromUsername"], group["dbConnectionId"]) for group in groups],
                         [("PENDING", "bob", 2), ("ACCEPTED", "carol", 3)])
        self.assertEqual([item["id"] for item in groups[0]["invitations"]], [4, 3])
        self.assertEqual(pending_count(self.invitations, ANN), 1)

    def test_only_accepted_permissions_count_as_shared(self):
        self.assertEqual(shares_by_connection(self.invitations, ANN), {3: ("carol", ["SELECT_ROLE"])})


class SentTest(unittest.TestCase):
    def test_the_newest_invitation_per_person_and_permission_is_what_stands(self):
        invitations = [
            invitation(5, ANN, BOB, 1, "INSERT_ROLE", "PENDING"),     # sent again after a decline
            invitation(4, ANN, CAROL, 1, "SELECT_ROLE", "REVOKED"),
            invitation(3, ANN, BOB, 1, "SELECT_ROLE", "ACCEPTED"),
            invitation(2, ANN, BOB, 1, "INSERT_ROLE", "DECLINED"),
            invitation(1, ANN, BOB, 2, "SELECT_ROLE", "ACCEPTED"),    # another database
        ]
        rows = sent_for_connection(invitations, ANN, 1)
        self.assertEqual([(row["toUsername"], row["permission"], row["status"]) for row in rows],
                         [("bob", "SELECT_ROLE", "ACCEPTED"), ("bob", "INSERT_ROLE", "PENDING")])


if __name__ == "__main__":
    unittest.main()
