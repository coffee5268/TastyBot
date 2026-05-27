from tastytrade import Session
from tastytrade.account import Account   # Correct import
import os
from dotenv import load_dotenv

load_dotenv()

class TastySession:
    def __init__(self, is_test=True):
        self.client_secret = os.getenv("TASTY_CLIENT_SECRET")
        self.refresh_token = os.getenv("TASTY_REFRESH_TOKEN")
        self.is_test = is_test
        self.session = None
        self.accounts = None

    def login(self):
        """Create session with OAuth credentials"""
        if not self.client_secret or not self.refresh_token:
            raise ValueError(
                "Missing TASTY_CLIENT_SECRET or TASTY_REFRESH_TOKEN in .env file.\n"
                "Check for extra spaces or missing values."
            )

        self.session = Session(
            self.client_secret,
            self.refresh_token,
            is_test=self.is_test
        )
        
        print(f"✅ Successfully logged into {'SANDBOX' if self.is_test else 'LIVE'} tastytrade")
        return self.session

    async def load_accounts(self):
        """Load accounts (async)"""
        if not self.session:
            raise ValueError("Must login first")
            
        self.accounts = await Account.get(self.session)
        print(f"Found {len(self.accounts)} account(s)")
        for acc in self.accounts:
            print(f"   → Account: {acc.account_number} ({getattr(acc, 'account_type_name', 'Unknown')})")
        return self.accounts

    def get_main_account(self):
        """Return first account (sync wrapper - we'll handle async properly later)"""
        if self.accounts and len(self.accounts) > 0:
            return self.accounts[0]
        return None