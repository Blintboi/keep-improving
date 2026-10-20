"""Compute an approval fingerprint locally without sending/revealing the code."""
import getpass
import hashlib
import hmac
import re

def fingerprint(code):
    normalized=code.replace('-','').replace(' ','').lower()
    if not re.fullmatch('[0-9a-f]{32}',normalized): raise ValueError('A generated 128-bit connection code is required.')
    authorization=hmac.digest(bytes.fromhex(normalized),b'GameTimeMonitor/authorization/v1','sha256').hex()
    return hashlib.sha256(authorization.encode('ascii')).hexdigest()

if __name__=='__main__':
    try: print(fingerprint(getpass.getpass('Connection code (hidden; processed locally): ')))
    except (ValueError,EOFError,KeyboardInterrupt): raise SystemExit('No valid fingerprint generated.') from None
