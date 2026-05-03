import sys
import json
import time
import requests
import os

from collections import deque
from urllib.parse import urlparse, urlunparse, urljoin
from bs4 import BeautifulSoup

ENCODING = "utf-8"
HEADERS = {"User-Agent": "CS172_CATEGORY1Scraper/0.0 (your_actual@ucr.edu)"}

class WikiCrawler:
    def __init__(
        self,
        seed_urls: str,
        max_depth=5,
        time_limit_sec=1800,
        max_size_MB=120,
        output_file="./data/pop.json",
    ):
        self.seed_urls = seed_urls.split()
        self.max_depth = max_depth
        self.time_limit_sec = time_limit_sec
        self.max_size_bytes = max_size_MB * 1024 * 1024
        self.output_file = output_file

        self.visited_urls_file = "../visited_urls.json"
        self.exisiting_visited_urls = self.load_json_file(self.visited_urls_file)
        self.current_session_visited_urls = set()
        self.scraped_data = self.load_json_file(output_file)
        self.url_frontier = deque([(url, 0) for url in self.seed_urls])

        self.crawler_start_time = time.time()
        self.pages_crawled_this_session = 0
        
        # Calculate initial size if file already exists
        self.current_size_bytes = 0
        if os.path.exists(self.output_file):
            self.current_size_bytes = os.path.getsize(self.output_file)

    @staticmethod
    def load_json_file(filename):
        try:
            with open(filename, "r", encoding=ENCODING) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_json_file(self, data, file):
        # Ensure directory exists before saving
        os.makedirs(os.path.dirname(file), exist_ok=True)
        with open(file, "w", encoding=ENCODING) as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    @staticmethod
    def normalize_url(url) -> str:
        parsed_url = urlparse(url)
        return urlunparse(parsed_url._replace(fragment="", query=""))
    
    @staticmethod
    def extract_text_content(soup):
        text_content = []
        for header in soup.find_all(['h1', 'h2', 'h3']):
            text_content.append(header.get_text(strip=True))
        for para in soup.find_all('p'):
            text_content.append(para.get_text(strip=True))
        for li in soup.find_all('li'):
            text_content.append(li.get_text(strip=True))
        return "\n".join(text_content)
    
    @staticmethod
    def extract_links(soup, base_url):
        links = set()
        allowed_domains = ['en.wikipedia.org']
        for a_tag in soup.find_all('a', href=True):
            href = a_tag['href']
            full_url = urljoin(base_url, href)
            if (any(domain in full_url for domain in allowed_domains) and 
                '/wiki/' in full_url and 
                ':' not in full_url.split('/wiki/')[-1]): # Prevents Special:, Talk:, Category:
                links.add(full_url)
        return links
    
    def check_limits(self):
        if time.time() - self.crawler_start_time > self.time_limit_sec:
            print(f"\n[STOP] Time limit of {self.time_limit_sec} seconds reached.")
            return True
            
        if self.current_size_bytes >= self.max_size_bytes:
            print(f"\n[STOP] Size limit of {self.max_size_bytes / (1024*1024):.2f} MB reached.")
            return True
            
        return False

    def crawl(self, url, depth):
        normalized_url = self.normalize_url(url)

        if normalized_url in (
            self.exisiting_visited_urls,
            self.current_session_visited_urls,
        ):
            return False

        try:
            response = requests.get(normalized_url, headers=HEADERS,timeout=5, allow_redirects=True)
            response.raise_for_status()
            final_url = self.normalize_url(response.url)
            if normalized_url in self.exisiting_visited_urls or normalized_url in self.current_session_visited_urls:
                return False

            time.sleep(2)
            
            soup = BeautifulSoup(response.content, 'html.parser')
            text_content = self.extract_text_content(soup)
            
            self.current_session_visited_urls.add(final_url)
            page_data = {
                "content": text_content
            }
            self.scraped_data[final_url] = page_data
            self.current_size_bytes += len(json.dumps(page_data).encode(ENCODING))
            
            if depth < self.max_depth:
                new_links = self.extract_links(soup, final_url)
                for new_url in new_links:
                    normalized_new_url = self.normalize_url(new_url)
                    if normalized_new_url not in self.exisiting_visited_urls:
                        self.url_frontier.append((normalized_new_url, depth + 1))
                        
            return True
        except requests.exceptions.RequestException as err:
            print(f"Skipping {url} due to error: {err}")
            return False
        finally:
            pass

    def run(self):
        try:
            while self.url_frontier:
                if self.check_limits():
                    break
                url, depth = self.url_frontier.popleft()
                if self.crawl(url, depth):
                    self.pages_crawled_this_session += 1
                    print(f"Depth {depth} | Crawled: {url} | Size: {self.current_size_bytes / (1024*1024):.2f} MB")
                    
                if self.pages_crawled_this_session % 50 == 0:
                    print("Autosaving progress...")
                    self.save_json_file(self.scraped_data, self.output_file)

        finally:
            print("\nSaving data and wrapping up...")
            new_visited = {h: self.scraped_data[h]["url"] for h in self.current_session_visited_urls if h in self.scraped_data}
            self.exisiting_visited_urls.update(new_visited)
            self.save_json_file(self.exisiting_visited_urls, self.visited_urls_file)
            self.save_json_file(self.scraped_data, self.output_file)
            print(f"Final session stats: {len(self.current_session_visited_urls)} pages crawled.")


if __name__ == "__main__":
    if len(sys.argv) < 6:
        print("Usage: python scrape.py <seed_urls> <max_depth> <time_limit_sec> <max_size_mb> <output_file>")
        sys.exit(1)
    seed_urls = sys.argv[1]
    max_depth = int(sys.argv[2])
    time_limit_sec = int(sys.argv[3])
    max_size_MB = int(sys.argv[4])
    output_file = sys.argv[5]

    crawler = WikiCrawler(seed_urls, max_depth, time_limit_sec, max_size_MB, output_file)
    crawler.run()
