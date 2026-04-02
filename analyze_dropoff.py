import json
from collections import defaultdict
import re

# We will read the first 10,000 lines to get a good sample size without taking too much memory/time.
FILE_PATH = r"C:\Github\MCI-GeTS-Chatbot\output\messages_dump.json"
NUM_LINES_TO_READ = 20000

print(f"Reading the first {NUM_LINES_TO_READ} lines of the dataset...")

conversations = defaultdict(list)

with open(FILE_PATH, 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i >= NUM_LINES_TO_READ:
            break
        try:
            data = json.loads(line)
            conv_id = data.get('conv_id')
            if conv_id:
                conversations[conv_id].append(data)
        except json.JSONDecodeError:
            continue

print(f"Found {len(conversations)} conversations in the sample.")

# Analysis of where customers stop
dropoff_stages = defaultdict(int)
completed_or_takeover = 0
abandoned = 0

def extract_clean_text(html_text):
    if not html_text:
        return "Unknown"
    # Remove HTML tags
    clean = re.sub('<[^<]+>', ' ', html_text)
    # Remove some common HTML entities
    clean = clean.replace('&nbsp;', ' ').replace('&#39;', "'")
    return " ".join(clean.split())[:100]  # truncate to 100 chars for readability

for conv_id, msgs in conversations.items():
    # Sort messages by time
    msgs.sort(key=lambda x: x.get('msg_time', 0))
    
    # Check if conversation had a takeover or handed to agent
    has_takeover = any(m.get('msg_type') == 'SYSTEM_TEXT' and m.get('payload', {}).get('text') == 'takeover' for m in msgs)
    has_live_agent = any(not m.get('isBotMsg', True) and m.get('sender_id', '').endswith('_ag') for m in msgs)
    
    if has_takeover or has_live_agent:
        completed_or_takeover += 1
        continue
    
    # If not taken over, it was abandoned. 
    abandoned += 1
    
    # Find the last message sent by the bot (which is usually the question the user didn't answer)
    last_bot_msg = None
    for m in reversed(msgs):
        if m.get('isBotMsg'):
            last_bot_msg = m
            break
    
    if last_bot_msg:
        payload = last_bot_msg.get('payload', {})
        text = payload.get('text', '')
        # Clean text to make counting easier
        clean_text = extract_clean_text(text)
        dropoff_stages[clean_text] += 1

print(f"\nConversations successfully handed to human / takeover: {completed_or_takeover}")
print(f"Conversations abandoned: {abandoned}")

print("\nTop 10 stages where customers abandoned the chat (Last Bot Message):")
# Sort descending by count
sorted_dropoffs = sorted(dropoff_stages.items(), key=lambda x: x[1], reverse=True)

for i, (stage, count) in enumerate(sorted_dropoffs[:10]):
    print(f"{i+1}. [{count} times] : {stage}")
