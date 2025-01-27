import asyncio
from metaapi_cloud_sdk import MetaApi

async def list_accounts():
    token = "eyJhbGciOiJSUzUxMiIsInR5cCI6IkpXVCJ9.eyJfaWQiOiJjNmUxNmQwZTViZTdhOTRiYjc3NmRhNmE2OGRkYmE2NSIsInBlcm1pc3Npb25zIjpbXSwiYWNjZXNzUnVsZXMiOlt7ImlkIjoidHJhZGluZy1hY2NvdW50LW1hbmFnZW1lbnQtYXBpIiwibWV0aG9kcyI6WyJ0cmFkaW5nLWFjY291bnQtbWFuYWdlbWVudC1hcGk6cmVzdDpwdWJsaWM6KjoqIl0sInJvbGVzIjpbInJlYWRlciIsIndyaXRlciJdLCJyZXNvdXJjZXMiOlsiKjokVVNFUl9JRCQ6KiJdfSx7ImlkIjoibWV0YWFwaS1yZXN0LWFwaSIsIm1ldGhvZHMiOlsibWV0YWFwaS1hcGk6cmVzdDpwdWJsaWM6KjoqIl0sInJvbGVzIjpbInJlYWRlciIsIndyaXRlciJdLCJyZXNvdXJjZXMiOlsiKjokVVNFUl9JRCQ6KiJdfSx7ImlkIjoibWV0YWFwaS1ycGMtYXBpIiwibWV0aG9kcyI6WyJtZXRhYXBpLWFwaTp3czpwdWJsaWM6KjoqIl0sInJvbGVzIjpbInJlYWRlciIsIndyaXRlciJdLCJyZXNvdXJjZXMiOlsiKjokVVNFUl9JRCQ6KiJdfSx7ImlkIjoibWV0YWFwaS1yZWFsLXRpbWUtc3RyZWFtaW5nLWFwaSIsIm1ldGhvZHMiOlsibWV0YWFwaS1hcGk6d3M6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6Im1ldGFzdGF0cy1hcGkiLCJtZXRob2RzIjpbIm1ldGFzdGF0cy1hcGk6cmVzdDpwdWJsaWM6KjoqIl0sInJvbGVzIjpbInJlYWRlciIsIndyaXRlciJdLCJyZXNvdXJjZXMiOlsiKjokVVNFUl9JRCQ6KiJdfSx7ImlkIjoicmlzay1tYW5hZ2VtZW50LWFwaSIsIm1ldGhvZHMiOlsicmlzay1tYW5hZ2VtZW50LWFwaTpyZXN0OnB1YmxpYzoqOioiXSwicm9sZXMiOlsicmVhZGVyIiwid3JpdGVyIl0sInJlc291cmNlcyI6WyIqOiRVU0VSX0lEJDoqIl19LHsiaWQiOiJjb3B5ZmFjdG9yeS1hcGkiLCJtZXRob2RzIjpbImNvcHlmYWN0b3J5LWFwaTpyZXN0OnB1YmxpYzoqOioiXSwicm9sZXMiOlsicmVhZGVyIiwid3JpdGVyIl0sInJlc291cmNlcyI6WyIqOiRVU0VSX0lEJDoqIl19LHsiaWQiOiJtdC1tYW5hZ2VyLWFwaSIsIm1ldGhvZHMiOlsibXQtbWFuYWdlci1hcGk6cmVzdDpkZWFsaW5nOio6KiIsIm10LW1hbmFnZXItYXBpOnJlc3Q6cHVibGljOio6KiJdLCJyb2xlcyI6WyJyZWFkZXIiLCJ3cml0ZXIiXSwicmVzb3VyY2VzIjpbIio6JFVTRVJfSUQkOioiXX0seyJpZCI6ImJpbGxpbmctYXBpIiwibWV0aG9kcyI6WyJiaWxsaW5nLWFwaTpyZXN0OnB1YmxpYzoqOioiXSwicm9sZXMiOlsicmVhZGVyIl0sInJlc291cmNlcyI6WyIqOiRVU0VSX0lEJDoqIl19XSwiaWdub3JlUmF0ZUxpbWl0cyI6ZmFsc2UsInRva2VuSWQiOiIyMDIxMDIxMyIsImltcGVyc29uYXRlZCI6ZmFsc2UsInJlYWxVc2VySWQiOiJjNmUxNmQwZTViZTdhOTRiYjc3NmRhNmE2OGRkYmE2NSIsImlhdCI6MTczNzk4NjEwNSwiZXhwIjoxNzQ1NzYyMTA1fQ.PxZRmij1ErUkAB4Z0_-FKfnMFm3Lmt4qABNYFOMHx40Q1s4mKdM52AkhBGk-MYNnZgHN5jnCC9sfVIfwapg8PwWhX7MIjTSd0k3-UzfNblZY-dpRX7oJ9gtIYDeaqW4s3Qc7sIEsmCBAgm69bRXVfTnCSJ8rSvblelWoySuRi0BKhaSDmG_NxuiZr9QTbN_-BkBRGt5tREMJV1_Sl9lQBh8WWF-bm-s_j8DA1VBR1MFZNEyegP4PyI7NWPteyAGiRfDsNyveZVUmCjAkMu3bhV7bWg0GoQo_RHwPvhSXSJaj9ryaln-uV0mjMglsBqJttrWzTlh5DuwG5pja9WU7Iibd7jJy2kO_ZCu6e4bXVOfhwGZDD0siAj_e0HuY6kWqAI9HBzq_JPEaF-AJdBQCt3ppCzP53e7O4M0gzR-Iju5m6Uc788RVpuguCUzrjonkuc85SwK_pw6tFp4OvkS1RjPIV5xnkruG2ZbKouWuo5rIra62E0xZL-UwywqiAVJ6N4WAxpicZBxAvloHBb7MUArZQVkqbtrUXoPRIbar7h6P_rEn88iSE8FCOWxILAK35j4303EXngRbD_ic6pnz3YN5o9ouPAAOyk22YUz59K2Ow9nuX_K9O3Tsb3IpzmjBBHPoJ30U2JH37DZGFd76E41Y5nynJMgIlJo2k6G4gd0"
    api = MetaApi(token)
    
    # Fetch accounts with filtering
    accounts = await api.metatrader_account_api.get_accounts_with_infinite_scroll_pagination(accounts_filter={
        'limit': 10,
        'offset': 0,
        'query': 'GTCGlobalTrade-Server',  # Your server
        'state': ['DEPLOYED']  # Filter only deployed accounts
    })
    
    account = None

    for acc in accounts:  # Iterate directly over the list
        if acc.login == "11002847":  # Match your account's login
            account = acc
            break

    if account:
        # Print specific account details
        print(f"Account found: Login = {account.login}, Name = {account.name}, Server = {account.server}")
    else:
        print("Account not found.")

asyncio.run(list_accounts())
