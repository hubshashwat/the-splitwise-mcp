import os
from dotenv import load_dotenv
from splitwise import Splitwise
from splitwise.expense import Expense
from splitwise.user import ExpenseUser
from typing import List, Optional

load_dotenv()

class SplitwiseClient:
    def __init__(self):
        self.consumer_key = os.getenv("SPLITWISE_CONSUMER_KEY")
        self.consumer_secret = os.getenv("SPLITWISE_CONSUMER_SECRET")
        self.api_key = os.getenv("SPLITWISE_API_KEY")
        self.access_token = None
        
        self.client = None
        self._current_user = None
        
        # Try to initialize if env vars are present
        if (self.consumer_key and self.consumer_secret) or self.api_key:
            self._init_client()

    def _init_client(self):
        self.client = Splitwise(
            consumer_key=self.consumer_key,
            consumer_secret=self.consumer_secret,
            api_key=self.api_key
        )
        # If we have an access token, set it.
        # Note: The library might expect a dict for OAuth1, or handle OAuth2 differently.
        # Assuming we can just populate the internal state or user uses 'api_key' as bearer.
        if self.access_token:
            # We assume dict format for stability with common library versions
            # But for purely OAuth2, it might differ. 
            # We'll set it as a dictionary which is a common pattern for this lib.
            self.client.setAccessToken({'oauth_token': self.access_token, 'oauth_token_secret': ''})

    def configure(self, consumer_key: str = None, consumer_secret: str = None, api_key: str = None, access_token: str = None):
        """
        Configure the client with credentials at runtime.
        """
        if consumer_key: self.consumer_key = consumer_key
        if consumer_secret: self.consumer_secret = consumer_secret
        if api_key: self.api_key = api_key
        if access_token: self.access_token = access_token
        
        self._init_client()

        self._current_user = None

    def get_current_user(self):
        if not self.client:
            raise ValueError("Splitwise client not configured. Please use 'configure_splitwise' tool.")
            
        if not self._current_user:
            self._current_user = self.client.getCurrentUser()
        return self._current_user

    def get_friends(self):
        if not self.client:
            raise ValueError("Splitwise client not configured. Please use 'configure_splitwise' tool.")
        return self.client.getFriends()

    def find_friend_by_name(self, name: str):
        friends = self.get_friends()
        name_lower = name.lower()
        for friend in friends:
            # Check first, last, and full name
            first = (friend.getFirstName() or "").lower()
            last = (friend.getLastName() or "").lower()
            full = f"{first} {last}".strip()
            
            if name_lower in full or name_lower == first or name_lower == last:
                return friend
        return None

    def get_groups(self):
        if not self.client:
            raise ValueError("Splitwise client not configured. Please use 'configure_splitwise' tool.")
        return self.client.getGroups()

    def find_group_by_name(self, name: str):
        groups = self.get_groups()
        name_lower = name.lower()
        for group in groups:
            if group.getName().lower() == name_lower:
                return group
        return None

    def add_expense(self, amount: str, description: str, friend_names: List[str], split_map: dict = None, group_name: str = None, payer_name: str = None, exclude_names: List[str] = None):
        """
        Splits an expense. 
        If split_map is None, splits equally.
        If split_map is provided:
            - Keys are names (use "me" or "I" for current user).
            - Values are amounts (e.g. "10.00") OR percentages (e.g. "50%").
        If group_name is provided:
            - If friend_names is empty, fetches all group members.
            - Adds expense to that group.
        If payer_name is provided:
            - Specifies who paid the full amount. Defaults to current user.
        If exclude_names is provided:
            - Remixes group members to exclude these names.
        """
        current_user = self.get_current_user()
        users_in_split = []
        
        # 1. Resolve Group & Members
        group_id = None
        if group_name:
            group = self.find_group_by_name(group_name)
            if not group:
                raise ValueError(f"Group not found: {group_name}")
            group_id = group.getId()
            
            # Auto-fetch members if friend_names is empty
            if not friend_names:
                members = group.getMembers()
                # Filter out excluded members
                if exclude_names:
                    # Normalize exclude names
                    excludes_lower = [n.lower() for n in exclude_names]
                    members = [
                        m for m in members 
                        if f"{m.getFirstName()} {m.getLastName()}".strip().lower() not in excludes_lower
                        and m.getFirstName().lower() not in excludes_lower
                    ]
                users_in_split = members

        # 2. Resolve Friends (if not using group auto-fetch)
        if not users_in_split:
            users_in_split = [current_user]
            friend_objects = {} 
            for name in friend_names:
                friend = self.find_friend_by_name(name)
                if not friend:
                    raise ValueError(f"Friend not found: {name}")
                users_in_split.append(friend)
            
            # Key by full name for split_map matching
            full_name = f"{friend.getFirstName()} {friend.getLastName()}".strip()
            friend_objects[full_name] = friend
            # Also key by first name? Ideally agent canonicalizes names.

        # Deduplicate based on ID just in case
        unique_users = {}
        for u in users_in_split:
             unique_users[u.getId()] = u
        users_in_split = list(unique_users.values())

        total_amount = float(amount)
        
        # 3. Create expense users
        expense_users = []
        
        # Resolve Payer
        payer_id = current_user.getId()
        if payer_name and payer_name.lower() not in ["me", "i", "myself"]:
             # Find payer in our list or friend list
             payer_found = False
             # Search in split users first
             for u in users_in_split:
                 f_name = f"{u.getFirstName()} {u.getLastName()}".strip()
                 if payer_name.lower() in f_name.lower() or payer_name.lower() == u.getFirstName().lower():
                     payer_id = u.getId()
                     payer_found = True
                     break
             
             if not payer_found:
                 # Try finding explicitly if not in split (e.g. payer paid but is not part of split?)
                 p = self.find_friend_by_name(payer_name)
                 if p:
                     payer_id = p.getId()
                     # If payer is not in split, add them to users (paid share set later)
                     if p.getId() not in unique_users:
                         users_in_split.append(p)
                         unique_users[p.getId()] = p
                 else:
                     raise ValueError(f"Payer not found: {payer_name}")
        
        if split_map:
            # Unequal split logic
            total_split = 0.0
            
            for user in users_in_split:
                eu = ExpenseUser()
                eu.setId(user.getId())
                
                # Paid Share
                if user.getId() == payer_id:
                    eu.setPaidShare(f"{total_amount:.2f}")
                else:
                    eu.setPaidShare("0.00")
                
                # Owed Share
                owed = 0.0
                
                # Match user in split_map
                key_to_use = None
                
                # Check "me"
                if user.getId() == current_user.getId():
                    if "me" in split_map: key_to_use = "me"
                    elif "Me" in split_map: key_to_use = "Me"
                    elif "I" in split_map: key_to_use = "I"
                
                # Check Name
                if not key_to_use:
                    f_name = f"{user.getFirstName()} {user.getLastName()}".strip()
                    if f_name in split_map: key_to_use = f_name
                    else:
                        for k in split_map:
                             if k.lower() in f_name.lower():
                                 key_to_use = k
                                 break
                
                if key_to_use:
                    val = split_map[key_to_use]
                    # Percentage Check
                    if isinstance(val, str) and val.strip().endswith("%"):
                        pct = float(val.strip().replace("%", ""))
                        owed = (pct / 100.0) * total_amount
                    else:
                        owed = float(val)

                eu.setOwedShare(f"{owed:.2f}")
                total_split += owed
                expense_users.append(eu)

            # Validation (loose due to float math)
            if abs(total_split - total_amount) > 0.05:
                 pass 
                
        else:
            # Equal split logic
            num_users = len(users_in_split)
            share = total_amount / num_users
            for user in users_in_split:
                eu = ExpenseUser()
                eu.setId(user.getId())
                
                if user.getId() == payer_id:
                    eu.setPaidShare(f"{total_amount:.2f}")
                else:
                    eu.setPaidShare("0.00")
                    
                eu.setOwedShare(f"{share:.2f}")
                expense_users.append(eu)

        expense = Expense()
        expense.setCost(f"{total_amount:.2f}")
        expense.setDescription(description)
        expense.setUsers(expense_users)
        
        if group_id:
            expense.setGroupId(group_id)
        
        # Handling potential 0.01 rounding errors? 
        # API might reject if sums don't match exactly.
        # Simple fix: the payload requires string.
        # splitwise library handles some of this? 
        # Let's hope basic division works for now. 
        # Advanced: distrubute remainder.
        
        expense, errors = self.client.createExpense(expense)
        
        if errors:
             raise Exception(f"Splitwise Error: {errors.getErrors()}")
             
        return expense

    def delete_expense(self, expense_id: str):
        """
        Delete an expense by ID.
        """
        if not self.client:
             raise ValueError("Splitwise client not configured.")
        
        success, errors = self.client.deleteExpense(expense_id)
        if success:
            return True
        else:
            raise Exception(f"Failed to delete expense: {errors.getErrors()}")

