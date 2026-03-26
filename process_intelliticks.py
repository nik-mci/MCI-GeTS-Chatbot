"""
Data Ingestion Pipeline for GeTS Travel Chatbot
Transforms raw IntelliTicks JSONL exports into high-quality RAG-ready datasets.
"""
import argparse
import json
import logging
import re
import hashlib
from collections import defaultdict
from pathlib import Path

try:
    from tqdm import tqdm
except ImportError:
    print("tqdm not installed. Continuing without progress bars.")
    def tqdm(iterable, *args, **kwargs): return iterable

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Constants
GREETINGS = {"hi", "hello", "hey", "thanks", "thank you", "good morning", "good evening", "good afternoon", "greetings"}
SHORT_RESPONSE_THRESHOLD = 5
MAX_CHUNK_WORDS = 350
MIN_CHUNK_WORDS = 100

class DataIngestor:
    """Handles memory-efficient reading of large JSONL files."""
    def __init__(self, input_path):
        self.input_path = Path(input_path)
        
    def load_conversations(self):
        """Read JSONL file line-by-line and group by conversation ID."""
        logger.info(f"Loading data from {self.input_path}...")
        conversations = defaultdict(list)
        malformed_lines = 0
        total_lines = 0
        
        try:
            with open(self.input_path, 'r', encoding='utf-8') as f:
                for line in tqdm(f, desc="Ingesting JSONL"):
                    total_lines += 1
                    try:
                        msg = json.loads(line.strip())
                        conv_id = msg.get('conv_id')
                        if conv_id:
                            conversations[conv_id].append(msg)
                    except json.JSONDecodeError:
                        malformed_lines += 1
        except Exception as e:
            logger.error(f"Failed to read input file: {e}")
            raise
            
        logger.info(f"Loaded {len(conversations)} conversations. "
                    f"Read {total_lines} lines. Malformed lines: {malformed_lines}.")
        return conversations

class DataCleaner:
    """Handles advanced text cleaning and normalization."""
    @staticmethod
    def remove_html(text):
        if not text:
            return ""
        clean = re.compile('<.*?>')
        return re.sub(clean, '', str(text))
        
    @staticmethod
    def remove_urls(text):
        if not text:
            return ""
        return re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
        
    @staticmethod
    def normalize_whitespace(text):
        if not text:
            return ""
        # Remove zero-width spaces and normalize newlines/tabs
        text = re.sub(r'[\u200b\u200c\u200d\uFEFF]', '', text)
        text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        return re.sub(r'\s+', ' ', text).strip()
        
    @staticmethod
    def clean_text(text, remove_urls=False):
        text = DataCleaner.remove_html(text)
        if remove_urls:
            text = DataCleaner.remove_urls(text)
        text = DataCleaner.normalize_whitespace(text)
        
        # Normalize repeated characters (e.g., helloooo -> helloo)
        text = re.sub(r'(.)\1{2,}', r'\1\1', text)
        return text

class ConversationNormalizer:
    """Normalizes raw messages into a standard structure, handling inconsistent fields."""
    def __init__(self, remove_urls=False):
        self.remove_urls = remove_urls

    def determine_role(self, msg):
        """Determine role based on assumed logic."""
        sender_id = msg.get('sender_id', '')
        # Bot is explicitly marked
        if msg.get('isBotMsg', False):
            return 'assistant_bot'
            
        # Analyze sender_id
        if isinstance(sender_id, str):
            if sender_id.endswith('_cu'):
                return 'user'
            if sender_id.endswith('_ag'):
                return 'assistant_human'
                
        # System messages like "takeover"
        if msg.get('msg_type') == 'SYSTEM_TEXT':
            return 'system'
            
        return 'unknown'

    def extract_text(self, msg):
        """Extract text from variable message formats."""
        text_parts = []
        payload = msg.get('payload', {})
        
        # Standard text
        if payload.get('text'):
            text_parts.append(str(payload['text']))
            
        # Form fields might be stored in 'fields' list
        if 'fields' in payload and isinstance(payload['fields'], list):
            for field in payload['fields']:
                name = field.get('name', '')
                value = field.get('value', '')
                if value:
                    text_parts.append(f"{name}: {value}")
                    
        return " | ".join(text_parts)

    def is_valid_conversation(self, msgs):
        """Filter out low-value conversations before further processing."""
        user_msgs = [m for m in msgs if m['role'] == 'user']
        assistant_msgs = [m for m in msgs if m['role'].startswith('assistant')]
        
        # Rule 1: We need at least 1 user message and 1 assistant message to form a Q&A
        if not user_msgs or not assistant_msgs:
            return False
            
        # Rule 2: Minimum 2 messages total (already covered by Rule 1, but explicitly > 1)
        if len(msgs) < 2:
            return False
            
        # Rule 3: Check if all user messages are just greetings
        all_user_greetings = True
        for m in user_msgs:
            # simple greeting check
            content = m['content'].lower().strip()
            # remove punctuation for greeting check
            content_clean = re.sub(r'[^\w\s]', '', content)
            if content_clean not in GREETINGS:
                all_user_greetings = False
                break
                
        if all_user_greetings:
            return False
            
        return True

    def normalize(self, conversations):
        """Process and normalize grouped conversations."""
        normalized_data = []
        filtered_out = 0
        
        for conv_id, msgs in tqdm(conversations.items(), desc="Normalizing Data"):
            # Sort messages chronologically
            msgs.sort(key=lambda x: x.get('msg_time', 0))
            
            norm_msgs = []
            for m in msgs:
                role = self.determine_role(m)
                
                # Exclude system messages immediately
                if role in ['unknown', 'system']:
                    continue
                    
                raw_text = self.extract_text(m)
                clean_text = DataCleaner.clean_text(raw_text, self.remove_urls)
                
                # Skip if empty after cleaning
                if not clean_text:
                    continue
                    
                msg_id = m.get('_id', f"{conv_id}_{len(norm_msgs)}")
                
                norm_msgs.append({
                    "role": role,
                    "content": clean_text,
                    "timestamp": m.get('msg_time', 0),
                    "message_id": msg_id
                })
                
            if self.is_valid_conversation(norm_msgs):
                normalized_data.append({
                    "conversation_id": conv_id,
                    "messages": norm_msgs
                })
            else:
                filtered_out += 1
                
        logger.info(f"Normalized {len(normalized_data)} valid conversations. Filtered {filtered_out} noise conversations.")
        return normalized_data, filtered_out

class QAExtractor:
    """Extracts intelligent Q&A pairs and enriches with metadata/chunks."""
    def __init__(self):
        self.seen_hashes = set()
        
    def merge_user_messages(self, msgs):
        """Merge consecutive user messages into a cohesive query if close in time."""
        merged = []
        current_user_msg = None
        TIME_WINDOW_MS = 60000 # 60 seconds
        
        for m in msgs:
            if m['role'] == 'user':
                if current_user_msg:
                    time_diff = m['timestamp'] - current_user_msg['timestamp']
                    # Merge if within time window or if previous was short
                    if time_diff < TIME_WINDOW_MS or len(current_user_msg['content'].split()) < 10:
                        current_user_msg['content'] += f". {m['content']}"
                        current_user_msg['message_id'] += f",{m['message_id']}"
                        current_user_msg['timestamp'] = m['timestamp'] # Update to latest
                    else:
                        merged.append(current_user_msg)
                        current_user_msg = m.copy()
                else:
                    current_user_msg = m.copy()
            else:
                if current_user_msg:
                    merged.append(current_user_msg)
                    current_user_msg = None
                merged.append(m.copy())
                
        if current_user_msg:
            merged.append(current_user_msg)
            
        return merged

    def extract_entities(self, text):
        """Extract basic travel metadata/entities using keyword matching."""
        entities = {}
        text_lower = text.lower()
        
        # Budget
        if any(w in text_lower for w in ["price", "cost", "budget", "quote", "rs", "rupees", "dollar"]):
            entities['budget'] = "mentioned"
            
        # Duration
        if any(w in text_lower for w in ["days", "nights", "week", "month"]):
            entities['duration'] = "mentioned"

        # Date 
        if any(w in text_lower for w in ["date", "start", "traveling on"]):
            entities['travel_date'] = "mentioned"
            
        # Generic destinations 
        destinations = []
        famous_places = ["delhi", "mumbai", "kerala", "goa", "jaipur", "agra", "rajasthan", "shimla", "manali", "india"]
        for place in famous_places:
            if place in text_lower:
                destinations.append(place.capitalize())
        if destinations:
            entities['destination'] = destinations
            
        return entities

    def get_tags(self, text):
        """Generate topic tags."""
        tags = set()
        text_lower = text.lower()
        if any(w in text_lower for w in ["price", "cost", "budget", "quote", "pay"]):
            tags.add("pricing")
        if any(w in text_lower for w in ["flight", "book", "hotel", "ticket", "reserve"]):
            tags.add("booking")
        if any(w in text_lower for w in ["tour", "trip", "package", "visit", "destination", "itinerary"]):
            tags.add("destination")
        return list(tags)

    def calculate_confidence(self, answer, entities):
        """Determine quality of the answer."""
        word_count = len(answer.split())
        has_entities = len(entities) > 0
        
        if word_count > 20 and has_entities:
            return "high"
        elif word_count >= 8:
            return "medium"
        return "low"

    def split_into_chunks(self, text):
        """Chunk long answers maintaining RAG constraints."""
        words = text.split()
        if len(words) <= MAX_CHUNK_WORDS:
            return [text]
            
        chunks = []
        for i in range(0, len(words), MAX_CHUNK_WORDS):
            # Ensuring we don't end up with a tiny isolated chunk at the end
            if i > 0 and (len(words) - i) < MIN_CHUNK_WORDS:
                # Merge remainder into the last chunk
                continue
            
            end_idx = min(i + MAX_CHUNK_WORDS, len(words))
            if end_idx < len(words) and (len(words) - end_idx) < MIN_CHUNK_WORDS:
                end_idx = len(words) # Take the rest
                
            chunk = " ".join(words[i:end_idx])
            chunks.append(chunk)
            
            if end_idx == len(words):
                break
                
        return chunks

    def deduplicate(self, question, answer):
        """Check uniqueness based on content hash."""
        content_hash = hashlib.md5(f"{question.lower().strip()}|{answer.lower().strip()}".encode()).hexdigest()
        if content_hash in self.seen_hashes:
            return True
        self.seen_hashes.add(content_hash)
        return False

    def is_greeting(self, text):
        clean = re.sub(r'[^\w\s]', '', text.lower().strip())
        return clean in GREETINGS or clean.startswith("hi ") or clean.startswith("hello ")

    def extract_pairs(self, norm_convs):
        """Transform normalized conversations into RAG-ready Q&A pairs."""
        qa_pairs = []
        stats = {
            "low_confidence": 0, 
            "medium_confidence": 0, 
            "high_confidence": 0, 
            "total_pairs": 0, 
            "deduplicated": 0
        }
        
        for conv in tqdm(norm_convs, desc="Extracting Q&A Pairs"):
            conv_id = conv['conversation_id']
            msgs = self.merge_user_messages(conv['messages'])
            
            i = 0
            while i < len(msgs) - 1:
                cur = msgs[i]
                nxt = msgs[i+1]
                
                # Find User -> Assistant transition
                if cur['role'] == 'user' and nxt['role'].startswith('assistant'):
                    question = cur['content']
                    
                    # Filter pure greetings at extraction time
                    if self.is_greeting(question):
                        i += 1
                        continue
                        
                    # Accumulate assistant responses
                    answer_parts = [nxt['content']]
                    source_ids = [cur['message_id'], nxt['message_id']]
                    assistant_type = nxt['role'].split('_')[1] # 'bot' or 'human'
                    
                    j = i + 2
                    while j < len(msgs) and msgs[j]['role'].startswith('assistant'):
                        answer_parts.append(msgs[j]['content'])
                        
                        # Add tracking
                        if msgs[j]['message_id'] not in source_ids:
                            source_ids.append(msgs[j]['message_id'])
                        
                        # Adjust assistant type if human intervened
                        if msgs[j]['role'] == 'assistant_human':
                            assistant_type = 'human'
                        j += 1
                        
                    answer = " ".join(answer_parts)
                    
                    # Filter short responses completely
                    if len(answer.split()) < SHORT_RESPONSE_THRESHOLD:
                        i = j
                        continue
                        
                    # Deduplication
                    if self.deduplicate(question, answer):
                        stats["deduplicated"] += 1
                        i = j
                        continue
                        
                    # Enrichment
                    combined_text = f"{question} {answer}"
                    entities = self.extract_entities(combined_text)
                    tags = self.get_tags(combined_text)
                    confidence = self.calculate_confidence(answer, entities)
                    
                    # Chunking
                    chunks = self.split_into_chunks(answer)
                    
                    for chunk_idx, chunk in enumerate(chunks):
                        pair = {
                            "question": question,
                            "answer": chunk,
                            "conversation_id": conv_id,
                            "assistant_type": assistant_type,
                            "source_message_ids": source_ids,
                            "confidence": confidence,
                            "source": "intelliticks",
                            "tags": tags,
                            "entities": entities
                        }
                        if len(chunks) > 1:
                            pair["chunk_index"] = chunk_idx + 1
                            pair["total_chunks"] = len(chunks)
                            
                        qa_pairs.append(pair)
                    
                    stats[f"{confidence}_confidence"] += 1
                    stats["total_pairs"] += 1
                    
                    i = j
                else:
                    i += 1
                    
        return qa_pairs, stats

def main():
    parser = argparse.ArgumentParser(description="Production Data Ingestion Pipeline for GeTS Travel Chatbot")
    parser.add_argument("input", help="Path to input JSONL file (e.g., messages_dump.json)")
    parser.add_argument("--output-dir", default="./output", help="Directory where processed files will be saved")
    parser.add_argument("--remove-urls", action="store_true", help="Toggle removal of URLs from text")
    
    args = parser.parse_args()
    
    input_file = Path(args.input)
    output_dir = Path(args.output_dir)
    
    if not input_file.exists():
        logger.error(f"Input file not found: {input_file}")
        return
        
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Init Pipeline Components
    ingestor = DataIngestor(input_file)
    normalizer = ConversationNormalizer(remove_urls=args.remove_urls)
    extractor = QAExtractor()
    
    # Execute Pipeline
    raw_convs = ingestor.load_conversations()
    
    norm_convs, filtered_count = normalizer.normalize(raw_convs)
    
    with open(output_dir / "cleaned_conversations.json", "w", encoding="utf-8") as f:
        json.dump(norm_convs, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved cleaned conversations to {output_dir / 'cleaned_conversations.json'}")
        
    qa_pairs, extraction_stats = extractor.extract_pairs(norm_convs)
    
    with open(output_dir / "qa_pairs.json", "w", encoding="utf-8") as f:
        json.dump(qa_pairs, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved Q&A pairs to {output_dir / 'qa_pairs.json'}")
        
    # Compile and save stats
    final_stats = {
        "pipeline_config": {
            "remove_urls": args.remove_urls,
            "min_words_threshold": SHORT_RESPONSE_THRESHOLD,
            "max_chunk_words": MAX_CHUNK_WORDS
        },
        "ingestion": {
            "total_raw_conversations": len(raw_convs),
            "filtered_noise_conversations": filtered_count,
            "valid_conversations": len(norm_convs)
        },
        "qa_extraction": extraction_stats
    }
    
    with open(output_dir / "stats.json", "w", encoding="utf-8") as f:
        json.dump(final_stats, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved stats to {output_dir / 'stats.json'}")
    
    logger.info("Pipeline Execution Completed Successfully.")

if __name__ == "__main__":
    main()
