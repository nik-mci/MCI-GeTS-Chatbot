import os
import re
import json
import time
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
from typing import List, Dict, Set, Any

# --- Configuration ---
SEED_URLS = [
    "https://www.getsholidays.com/",
    "https://www.getsholidays.com/about-us",
    "https://www.getsholidays.com/who-we-are",
    "https://www.getsholidays.com/our-team",
    "https://www.getsholidays.com/why-us",
    "https://www.getsholidays.com/india-travel-tips",
    "https://www.getsholidays.com/awards-and-achievements",
    "https://www.getsholidays.com/contact-us",
    "https://www.getsholidays.com/careers",
    "https://www.getsholidays.com/partner-with-us",
    "https://www.getsholidays.com/e-tourist-visa",
    "https://www.getsholidays.com/activities",
    "https://www.getsholidays.com/packages",
    "https://www.getsholidays.com/tour-category/luxury-india-tour-packages",
    "https://www.getsholidays.com/tour-category/heritage-culture",
    "https://www.getsholidays.com/tour-category/adventure-wildlife",
    "https://www.getsholidays.com/tour-category/forts-palaces",
    "https://www.getsholidays.com/tour-category/sea-sun-sand",
    "https://www.getsholidays.com/tour-category/fairs-festivals",
    "https://www.getsholidays.com/tour-category/pilgrimage",
    "https://www.getsholidays.com/tour-category/ayurveda-yoga-spa",
    "https://www.getsholidays.com/tour-packages/kerala",
    "https://www.getsholidays.com/tour-packages/udaipur",
    "https://www.getsholidays.com/tour-packages/varanasi",
    "https://www.getsholidays.com/tour-packages/cochin12",
    "https://www.getsholidays.com/tour-packages/calicut1",
    "https://www.getsholidays.com/tour-packages/ahmedabad123",
    "https://www.getsholidays.com/tour-packages/golden-triangle",
    "https://www.getsholidays.com/tour-packages/rajasthan",
    "https://www.getsholidays.com/tour-packages/south-india",
    "https://www.getsholidays.com/tour-packages/north-india",
    "https://www.getsholidays.com/tour-packages/family",
    "https://www.getsholidays.com/tour-packages/honeymoon",
    "https://www.getsholidays.com/tour-packages/adventure",
    "https://www.getsholidays.com/tour-packages/luxury",
    "https://www.getsholidays.com/tour-packages/wildlife",
    "https://blog.getsholidays.com/",
    "https://blog.getsholidays.com/all-articles"
]

ALLOWED_DOMAINS = [
    "www.getsholidays.com",
    "blog.getsholidays.com",
    "packages.getsholidays.com"
]

EXCLUDE_PATTERNS = [
    r"tour\.getsholidays\.com",
    r"login", r"logout", r"cart", r"checkout", r"admin", r"wp-admin",
    r"\.pdf$", r"\.jpg$", r"\.png$", r"\.gif$", r"\.css$", r"\.js$",
    r"^mailto:", r"^tel:"
]

USER_AGENT = "Mozilla/5.0 (compatible; GeTSBot/1.0; +https://getsholidays.com)"
TIMEOUT = 10
CRAWL_DELAY = 1
MAX_PAGES = 500

OUTPUT_FILE = "data/raw/scraped_pages.json"
SUMMARY_FILE = "data/raw/scrape_summary.json"

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format="[SCRAPER] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class GeTSScraper:
    def __init__(self):
        self.visited: Set[str] = set()
        self.queue: List[str] = list(SEED_URLS)
        self.results: List[Dict[str, Any]] = []
        self.failed_urls: List[str] = []
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def is_valid_url(self, url: str) -> bool:
        """Checks if the URL is within allowed domains and doesn't match exclusion patterns."""
        parsed = urlparse(url)
        if parsed.netloc not in ALLOWED_DOMAINS:
            return False
        
        for pattern in EXCLUDE_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        return True

    def get_page_type(self, url: str) -> str:
        """Detects page type based on URL structure."""
        if "tour-packages" in url or "tour-category" in url:
            return "tour_package"
        if "blog.getsholidays.com" in url or "/blog/" in url:
            return "blog"
        if any(x in url for x in ["about-us", "who-we-are", "our-team", "why-us"]):
            return "about"
        if "contact-us" in url:
            return "contact"
        return "general"

    def clean_text(self, soup: BeautifulSoup) -> str:
        """Strips boilerplate and returns high-quality clean text."""
        # Step 1: Remove HTML elements entirely
        for tag_name in ["header", "footer", "nav", "script", "style"]:
            for tag in soup.find_all(tag_name):
                tag.decompose()

        # Keywords for class/id matching
        boilerplate_keywords = [
            "nav", "menu", "footer", "cookie", "newsletter", "follow", 
            "social", "sidebar", "popup", "modal", "overlay", "banner", 
            "enquir", "whatsapp"
        ]
        
        def is_boilerplate(tag):
            if not tag.name: return False
            attrs = tag.attrs
            for attr in ["class", "id"]:
                val = attrs.get(attr, "")
                if isinstance(val, list):
                    val = " ".join(val)
                if any(kw in val.lower() for kw in boilerplate_keywords):
                    return True
            return False

        for tag in soup.find_all(is_boilerplate):
            tag.decompose()

        # Step 2: Extract text from what remains
        text = soup.get_text(separator="\n")
        
        # Step 3: Apply text cleaning rules
        lines = text.splitlines()
        clean_lines = []
        
        exclude_keywords = [
            "toll free", "enquire now", "follow us", "newsletter", 
            "privacy policy", "terms & conditions", "site map", 
            "design by", "copyright", "cookie", "accept", 
            "call us", "whatsapp"
        ]
        
        phone_pattern = re.compile(r"^[\d\s\-\+\(\)]{7,}$")

        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Remove lines shorter than 30 characters
            if len(line) < 30:
                continue
            
            # Remove lines that are just numbers/phone numbers
            if phone_pattern.match(line):
                continue
            
            # Remove lines containing excluded keywords
            if any(kw in line.lower() for kw in exclude_keywords):
                continue
            
            # Filter out destination route strings
            if line.count(" - ") >= 3:
                continue
            
            # Filter out truncated package card previews
            if line.endswith("...") and len(line) < 60:
                continue
            
            clean_lines.append(line)

        # Collapse multiple blank lines into one (already handled by strip/if not line)
        return "\n".join(clean_lines)

    def extract_tour_highlights(self, soup: BeautifulSoup, page_type: str) -> Dict[str, Any]:
        """Extracts specific tour data if it's a tour package page."""
        highlights: Dict[str, Any] = {
            "duration": None,
            "inclusions": [],
            "destinations_covered": []
        }
        
        if page_type != "tour_package":
            return highlights

        text = soup.get_text()
        
        # Duration regex: e.g. "7 Nights / 8 Days"
        duration_match = re.search(r"(\d+\s*Nights?\s*/\s*\d+\s*Days?)", text, re.IGNORECASE)
        if duration_match:
            highlights["duration"] = duration_match.group(1).strip()

        # Destinations: look for "Destinations Covered:" or "Places Covered:"
        dest_match = re.search(r"(?:Destinations|Places)\s*Covered(?::|\s*-)(.*?)(?:\n|$|\.)", text, re.IGNORECASE)
        if dest_match:
            dests = re.split(r"[,|-]", dest_match.group(1))
            highlights["destinations_covered"] = [d.strip() for d in dests if d.strip()]

        # Inclusions: primitive check for list items in inclusion sections
        inclusion_header = soup.find(string=re.compile(r"Inclusions", re.IGNORECASE))
        if inclusion_header:
            parent = inclusion_header.find_parent()
            if parent:
                # Look for siblings or nested ULs
                ul = parent.find_next("ul")
                if ul:
                    highlights["inclusions"] = [li.get_text().strip() for li in ul.find_all("li")]

        return highlights

    def scrape_page(self, url: str) -> bool:
        """Fetches and parses a single page."""
        try:
            time.sleep(CRAWL_DELAY)
            response = self.session.get(url, timeout=TIMEOUT)
            
            # Handle 429 Rate Limiting
            if response.status_code == 429:
                logger.warning(f"Rate limited (429) on {url}. Retrying in 5s...")
                time.sleep(5)
                response = self.session.get(url, timeout=TIMEOUT)

            if response.status_code != 200:
                logger.error(f"Failed to fetch: {url} | Status: {response.status_code}")
                self.failed_urls.append(url)
                return False

            soup = BeautifulSoup(response.content, "lxml")
            
            title = soup.title.string.strip() if soup.title else soup.find("h1").get_text().strip() if soup.find("h1") else "No Title"
            meta_desc = ""
            desc_tag = soup.find("meta", attrs={"name": "description"})
            if desc_tag:
                meta_desc = desc_tag.get("content", "").strip()

            page_type = self.get_page_type(url)
            main_content = self.clean_text(soup)
            
            # Remove page title from first line if it matches exactly
            content_lines = main_content.splitlines()
            if content_lines and content_lines[0].strip() == title:
                main_content = "\n".join(content_lines[1:]).strip()
            
            if len(main_content) < 150:
                logger.info(f"Skipped: {url} | Reason: Content too short ({len(main_content)} chars post-cleaning)")
                return False

            headings = [h.get_text().strip() for h in soup.find_all(["h1", "h2", "h3"]) if h.get_text().strip()]
            
            # Extract internal links for queueing
            for a in soup.find_all("a", href=True):
                full_url = urljoin(url, a["href"]).split("#")[0].rstrip("/")
                if self.is_valid_url(full_url) and full_url not in self.visited and full_url not in self.queue:
                    self.queue.append(full_url)

            # Store result
            self.results.append({
                "url": url,
                "title": title,
                "meta_description": meta_desc,
                "page_type": page_type,
                "headings": headings,
                "main_content": main_content,
                "tour_highlights": self.extract_tour_highlights(soup, page_type),
                "scraped_at": datetime.now().isoformat()
            })

            logger.info(f"Fetched: {url} | Status: 200 | Content: {len(main_content)} chars")
            return True

        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            self.failed_urls.append(url)
            return False

    def crawl(self):
        """Main crawl loop."""
        logger.info(f"Starting crawl | Seed URLs: {len(SEED_URLS)}")
        
        while self.queue and len(self.visited) < MAX_PAGES:
            url = self.queue.pop(0)
            if url in self.visited:
                continue
            
            success = self.scrape_page(url)
            self.visited.add(url)
            
            if len(self.visited) % 10 == 0:
                logger.info(f"Progress: {len(self.visited)}/500 pages | Queue: {len(self.queue)}")

        self.save_results()

    def save_results(self):
        """Saves scraped data and summary report."""
        os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
        
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False)
        
        pages_by_type = {}
        for res in self.results:
            ptype = res["page_type"]
            pages_by_type[ptype] = pages_by_type.get(ptype, 0) + 1

        summary = {
            "total_pages": len(self.results),
            "pages_by_type": pages_by_type,
            "failed_urls_count": len(self.failed_urls),
            "failed_urls": self.failed_urls,
            "scraped_at": datetime.now().isoformat()
        }
        
        with open(SUMMARY_FILE, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
            
        logger.info(f"DONE | Total pages: {len(self.results)} | Failed: {len(self.failed_urls)}")

if __name__ == "__main__":
    scraper = GeTSScraper()
    scraper.crawl()
