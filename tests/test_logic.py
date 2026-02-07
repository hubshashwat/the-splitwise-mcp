import unittest
from unittest.mock import MagicMock, patch
from splitwise_mcp.client import SplitwiseClient

class TestSplitwiseLogic(unittest.TestCase):
    def setUp(self):
        # Mock environment variables
        self.patcher = patch.dict('os.environ', {
            'SPLITWISE_CONSUMER_KEY': 'fake_key',
            'SPLITWISE_CONSUMER_SECRET': 'fake_secret'
        })
        self.patcher.start()
        
        # Mock the external Splitwise library
        self.splitwise_patcher = patch('splitwise_mcp.client.Splitwise')
        self.MockSplitwise = self.splitwise_patcher.start()
        
        self.client_wrapper = SplitwiseClient()
        self.mock_client = self.client_wrapper.client

    def tearDown(self):
        self.patcher.stop()
        self.splitwise_patcher.stop()

    def test_find_friend_by_name(self):
        f1 = MagicMock()
        f1.getFirstName.return_value = "Sumeet"
        f1.getLastName.return_value = "Singh"
        f1.getId.return_value = 101

        f2 = MagicMock()
        f2.getFirstName.return_value = "Mridul"
        f2.getLastName.return_value = "Kumar"
        f2.getId.return_value = 102

        self.mock_client.getFriends.return_value = [f1, f2]

        found = self.client_wrapper.find_friend_by_name("Sumeet")
        self.assertEqual(found.getId(), 101)

        found_full = self.client_wrapper.find_friend_by_name("Mridul Kumar")
        self.assertEqual(found_full.getId(), 102)

        not_found = self.client_wrapper.find_friend_by_name("Rahul")
        self.assertIsNone(not_found)

    def test_add_expense_logic(self):
        # Mock user
        me = MagicMock()
        me.getId.return_value = 999
        self.mock_client.getCurrentUser.return_value = me

        # Mock friends
        f1 = MagicMock()
        f1.getFirstName.return_value = "Sumeet"
        f1.getId.return_value = 101
        
        self.mock_client.getFriends.return_value = [f1]

        self.mock_client.getFriends.return_value = [f1]

        # Mock createExpense return value
        self.mock_client.createExpense.return_value = (MagicMock(), None)

        # Call add_expense
        self.client_wrapper.add_expense("70", "Dinner", ["Sumeet"])

        # CreateExpense should be called once
        self.mock_client.createExpense.assert_called_once()
        
        # Inspect the expense object passed to createExpense
        args, _ = self.mock_client.createExpense.call_args
        expense = args[0]
        
        self.assertEqual(expense.getCost(), "70.00")
        self.assertEqual(expense.getDescription(), "Dinner")
        
        # Check users
        users = expense.getUsers()
        self.assertEqual(len(users), 2) # Me + Sumeet
        
        # Verify splits
        # Total 70, split 2 ways = 35 each.
        # User 0 (Me): Paid 70, Owed 35
        # User 1 (Sumeet): Paid 0, Owed 35
        
        u_me = users[0]
        u_sumeet = users[1]
        
        # Order in list depends on implementation: [me, friend]
        self.assertEqual(u_me.getId(), 999)
        self.assertEqual(u_me.getPaidShare(), "70.00")
        self.assertEqual(u_me.getOwedShare(), "35.00")

        self.assertEqual(u_sumeet.getId(), 101)
        self.assertEqual(u_sumeet.getPaidShare(), "0.0")
        self.assertEqual(u_sumeet.getOwedShare(), "35.00")

    def test_add_expense_unequal_split(self):
        # Mock user
        me = MagicMock()
        me.getId.return_value = 999
        self.mock_client.getCurrentUser.return_value = me

        # Mock friends
        f1 = MagicMock()
        f1.getFirstName.return_value = "Mridul"
        f1.getLastName.return_value = "Singh"
        f1.getId.return_value = 101
        
        self.mock_client.getFriends.return_value = [f1]

        # Mock createExpense return value
        self.mock_client.createExpense.return_value = (MagicMock(), None)

        # Call add_expense with split_map
        # Total 4.00. Me: 1.00, Mridul: 3.00
        split_map = {"me": "1.00", "Mridul Singh": "3.00"}
        self.client_wrapper.add_expense("4.00", "Unequal Split", ["Mridul Singh"], split_map=split_map)

        # Inspect the expense object passed to createExpense
        args, _ = self.mock_client.createExpense.call_args
        expense = args[0]
        
        self.assertEqual(expense.getCost(), "4.00")
        
        users = expense.getUsers()
        self.assertEqual(len(users), 2)
        
        u_me = users[0]
        u_mridul = users[1]
        
        # Verify me
        self.assertEqual(u_me.getId(), 999)
        self.assertEqual(u_me.getOwedShare(), "1.00")
        
        # Verify Mridul
        self.assertEqual(u_mridul.getId(), 101)
        self.assertEqual(u_mridul.getOwedShare(), "3.00")

    def test_add_expense_to_group(self):
        # Mock user
        me = MagicMock()
        me.getId.return_value = 999
        self.mock_client.getCurrentUser.return_value = me

        # Mock friends
        f1 = MagicMock()
        f1.getFirstName.return_value = "Roommate"
        f1.getId.return_value = 101
        self.mock_client.getFriends.return_value = [f1]
        
        # Mock groups
        g1 = MagicMock()
        g1.getName.return_value = "Apartment"
        g1.getId.return_value = 500
        self.mock_client.getGroups.return_value = [g1]

        # Mock createExpense return value
        self.mock_client.createExpense.return_value = (MagicMock(), None)

        # Call add_expense with group_name
        self.client_wrapper.add_expense("100.00", "Rent", ["Roommate"], group_name="Apartment")

        # Inspect the expense object
        args, _ = self.mock_client.createExpense.call_args
        expense = args[0]
        
        self.mock_client.createExpense.assert_called_once()
        self.assertEqual(expense.getGroupId(), 500)
        self.assertEqual(expense.getDescription(), "Rent")

if __name__ == '__main__':
    unittest.main()
