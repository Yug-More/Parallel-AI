"""Quick script to check Plivo call logs and config."""
import requests
import json

auth = ('MAOGRIMGU3MGITY2M1MC', 'MDQ2YTZlMjQtNTA0ZS00ZGIzLTk3ZWEtN2Y0YWMx')
base = 'https://api.plivo.com/v1/Account/MAOGRIMGU3MGITY2M1MC'

# Get recent calls
r = requests.get(f'{base}/Call/', auth=auth, params={'limit': 10})
data = r.json()
print(f"=== RECENT CALLS (total: {data.get('meta', {}).get('total_count', 0)}) ===")
for c in data.get('objects', []):
    print(f"  UUID: {c.get('call_uuid')}")
    print(f"  From: {c.get('from_number')} -> To: {c.get('to_number')}")
    print(f"  Direction: {c.get('call_direction')}")
    print(f"  Status: {c.get('call_state')}  Hangup: {c.get('hangup_cause_name')}")
    print(f"  Duration: {c.get('call_duration')}s  Bill: {c.get('bill_duration')}s")
    print(f"  Init: {c.get('initiation_time')}  Answer: {c.get('answer_time')}  End: {c.get('end_time')}")
    print()

# App details
r2 = requests.get(f'{base}/Application/24932251210085791/', auth=auth)
app = r2.json()
print("=== APP CONFIG ===")
print(f"  answer_url: {app.get('answer_url')}")
print(f"  answer_method: {app.get('answer_method')}")
print(f"  hangup_url: {app.get('hangup_url')}")
print(f"  enabled: {app.get('enabled')}")
