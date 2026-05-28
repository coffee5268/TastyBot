from tastytrade import Session
from tastytrade.account import Account
import os
from dotenv import load_dotenv

load_dotenv()

class TastySession:
    def __init__(self, is_test=True):
        self.is_test = is_test
        self.session = None
        self.accounts = []

    def login(self):
        """Create a fresh session"""
        print("🔄 Creating fresh session...")
        self.session = Session(
            os.getenv("TASTY_CLIENT_SECRET"),
            os.getenv("TASTY_REFRESH_TOKEN"),
            is_test=self.is_test
        )
        print("✅ Fresh session created")
        return self.session

    async def load_accounts(self):
        if not self.session:
            self.login()
        self.accounts = await Account.get(self.session)
        print(f"Found {len(self.accounts)} account(s)")
        for acc in self.accounts:
            print(f"   → Account: {acc.account_number}")
        return self.accounts

    def is_offline(self):
        """Simple check"""
        return self.session is None