import asyncio
import time
import re
import requests
from telethon import TelegramClient
from telethon.errors.rpcerrorlist import UsernameNotOccupiedError, UsernameInvalidError, FloodWaitError
from telethon.errors.rpcbaseerrors import RPCError

# Your Telegram API credentials
api_id = 21531783
api_hash = '980bb556179c437b0cc5a67eedd8c80'
session_name = 'userchecker_session'

client = TelegramClient(session_name, api_id, api_hash)

def read_usernames_from_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    return [line.strip() for line in lines if line.strip()]

def is_username_valid(username: str) -> bool:
    pattern = r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$'
    if not re.match(pattern, username):
        return False
    if '__' in username or username.endswith('_'):
        return False
    return True

def is_claimable(username):
    url = f'https://t.me/{username}'
    try:
        r = requests.get(url, timeout=5)
        text = r.text.lower()

        phrases_blocking = [
            "username is taken",
            "sorry, this username is not available",
            "username not available",
            "this username is available for purchase",
            "username is blocked",
            "this username is reserved",
        ]

        if any(phrase in text for phrase in phrases_blocking):
            return False, None

        if r.status_code == 200:
            if "tgme" in r.url:
                return True, None
            if "not found" in text:
                return True, None
            if len(text.strip()) < 100:
                return None, True

        return None, True

    except Exception as e:
        print(f"Web check error for @{username}: {e}")
        return None, True

async def check_username(username):
    if username.startswith('@'):
        username = username[1:]

    if not is_username_valid(username):
        print(f"@{username} is INVALID (failed validation rules)")
        return username, "INVALID"

    try:
        await client.get_entity(username)
        print(f"@{username} is TAKEN")
        return username, "TAKEN"
    except FloodWaitError as e:
        print(f"Flood wait of {e.seconds} seconds. Sleeping...")
        await asyncio.sleep(e.seconds + 1)
        try:
            await client.get_entity(username)
            print(f"@{username} is TAKEN")
            return username, "TAKEN"
        except Exception as ex:
            print(f"Error after waiting: {ex}")
            return username, "UNKNOWN"
    except UsernameNotOccupiedError:
        claimable, potentially = is_claimable(username)
        if claimable is True:
            print(f"@{username} is AVAILABLE")
            return username, "AVAILABLE"
        elif claimable is False:
            print(f"@{username} is UNAVAILABLE (reserved/blocked/auctioned)")
            return username, "UNAVAILABLE"
        elif potentially:
            print(f"@{username} is POTENTIALLY AVAILABLE (check manually)")
            return username, "POTENTIALLY AVAILABLE"
        else:
            print(f"@{username} is UNKNOWN")
            return username, "UNKNOWN"
    except UsernameInvalidError:
        print(f"@{username} is INVALID (Telegram rejected it)")
        return username, "INVALID"
    except ValueError as e:
        if "No user has" in str(e):
            claimable, potentially = is_claimable(username)
            if claimable is True:
                print(f"@{username} is AVAILABLE")
                return username, "AVAILABLE"
            elif claimable is False:
                print(f"@{username} is UNAVAILABLE (reserved/blocked/auctioned)")
                return username, "UNAVAILABLE"
            elif potentially:
                print(f"@{username} is POTENTIALLY AVAILABLE (check manually)")
                return username, "POTENTIALLY AVAILABLE"
            else:
                print(f"@{username} availability UNKNOWN")
                return username, "UNKNOWN"
        else:
            print(f"Error checking @{username}: {e}")
            return username, "UNKNOWN"
    except RPCError as e:
        print(f"Error checking @{username}: {e}")
        return username, "UNKNOWN"

async def main(usernames):
    await client.start()
    results = {}

    batch_size = 10
    max_requests_per_minute = 20
    requests_sent = 0
    start_time = time.time()

    for i in range(0, len(usernames), batch_size):
        batch = usernames[i:i + batch_size]

        elapsed = time.time() - start_time
        if requests_sent >= max_requests_per_minute:
            wait_time = 60 - elapsed
            if wait_time > 0:
                print(f"Rate limit reached. Sleeping for {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)
            requests_sent = 0
            start_time = time.time()

        for username in batch:
            result = await check_username(username)
            results[result[0]] = result[1]
            requests_sent += 1
            await asyncio.sleep(1)  # ⏱ 1-second delay between each individual check

    await client.disconnect()

    print("\nSummary:")
    for u, status in results.items():
        print(f"@{u}: {status}")

    # Write available and potentially available to available.txt
    with open('available.txt', 'w', encoding='utf-8') as f:
        for u, status in results.items():
            if status in ("AVAILABLE", "POTENTIALLY AVAILABLE"):
                f.write(f"@{u}\n")

if __name__ == '__main__':
    usernames_to_check = read_usernames_from_file('usernames.txt')
    asyncio.run(main(usernames_to_check))
