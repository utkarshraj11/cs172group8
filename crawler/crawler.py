import sys
import json
import time
import requests
import os
import urllib.robotparser

from collections import deque
from urllib.parse import urlparse, urlunparse, urljoin
from bs4 import BeautifulSoup

# Rich imports for beautiful CLI output
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich.table import Table

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

        # # For robots.txt
        # self.rp = urllib.robotparser.RobotFileParser()
        # self.rp.set_url("https://en.wikipedia.org/robots.txt")
        # self.rp.read()

        # Calculate initial size if file already exists
        self.current_size_bytes = 0
        if os.path.exists(self.output_file):
            self.current_size_bytes = os.path.getsize(self.output_file)

        # rich print
        self.console = Console()

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
        for header in soup.find_all(["h1", "h2", "h3"]):
            text_content.append(header.get_text(strip=True))
        for para in soup.find_all("p"):
            text_content.append(para.get_text(strip=True))
        for li in soup.find_all("li"):
            text_content.append(li.get_text(strip=True))
        return "\n".join(text_content)

    @staticmethod
    def extract_links(soup, base_url):
        links = set()
        allowed_domains = ["en.wikipedia.org"]
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            full_url = urljoin(base_url, href)
            if (
                any(domain in full_url for domain in allowed_domains)
                and "/wiki/" in full_url
                and ":" not in full_url.split("/wiki/")[-1]
            ):  # Prevents Special:, Talk:, Category:
                links.add(full_url)
        return links

    def check_limits(self):
        if time.time() - self.crawler_start_time > self.time_limit_sec:
            self.console.print(f"\n[bold red][STOP][/bold red] Time limit of {self.time_limit_sec} seconds reached.")
            return True

        if self.current_size_bytes >= self.max_size_bytes:
            self.console.print(
                f"\n[bold red][STOP][/bold red] Size limit of {self.max_size_bytes / (1024 * 1024):.2f} MB reached."
            )
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
            response = requests.get(normalized_url, headers=HEADERS, timeout=5, allow_redirects=True)
            response.raise_for_status()
            final_url = self.normalize_url(response.url)
            if normalized_url in self.exisiting_visited_urls or normalized_url in self.current_session_visited_urls:
                return False

            # # Politeness Check
            # if not self.rp.can_fetch(HEADERS["User-Agent"], normalized_url):
            #     print(f"Skipping {normalized_url} (Blocked by robots.txt)")
            #     return False

            time.sleep(1)

            soup = BeautifulSoup(response.content, "html.parser")
            text_content = self.extract_text_content(soup)

            self.current_session_visited_urls.add(final_url)
            page_data = {"content": text_content}
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
        config_table = Table(show_header=False, box=None)
        config_table.add_row("Seed URLs:", f"{len(self.seed_urls)}")
        config_table.add_row("Max Depth:", f"{self.max_depth}")
        config_table.add_row("Time Limit:", f"{self.time_limit_sec}s")
        config_table.add_row("Max Size:", f"{self.max_size_bytes / (1024 * 1024):.2f} MB")

        self.console.print(Panel(config_table, title="[bold green]WikiCrawler Started", expand=False))

        try:
            # Setting up Rich Progress Bar
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                TextColumn("[progress.completed]{task.completed} pages"),
                TextColumn("•"),
                TimeElapsedColumn(),
                console=self.console,
            ) as progress:
                crawl_task = progress.add_task(
                    "Crawling...", total=None
                )  # None because we don't know the exact final count

                while self.url_frontier:
                    if self.check_limits():
                        break

                    url, depth = self.url_frontier.popleft()
                    time.sleep(1)

                    # Update progress with live stats
                    current_mb = self.current_size_bytes / (1024 * 1024)
                    progress.update(
                        crawl_task,
                        description=f"[bold blue]Crawling[/bold blue] [cyan](Depth {depth})[/cyan] | [yellow]Queue: {len(self.url_frontier)}[/yellow] | [magenta]Size: {current_mb:.2f} MB[/magenta]",
                    )

                    if self.crawl(url, depth):
                        self.pages_crawled_this_session += 1
                        progress.update(crawl_task, advance=1)
                        progress.console.print(f"[green]✔[/green] {url}")

                    if self.pages_crawled_this_session > 0 and self.pages_crawled_this_session % 50 == 0:
                        progress.console.print("[dim yellow]Autosaving progress...[/dim yellow]")
                        self.save_json_file(self.scraped_data, self.output_file)

        finally:
            self.console.print("\n[bold yellow]Saving data and wrapping up...[/bold yellow]")
            new_visited = {
                h: self.scraped_data[h]["url"] if "url" in self.scraped_data[h] else h
                for h in self.current_session_visited_urls
                if h in self.scraped_data
            }
            self.exisiting_visited_urls.update(new_visited)

            self.save_json_file(self.exisiting_visited_urls, self.visited_urls_file)
            self.save_json_file(self.scraped_data, self.output_file)

            # Final Summary Panel
            summary_table = Table(show_header=False, box=None)
            summary_table.add_row(
                "Pages Crawled:", f"[bold green]{len(self.current_session_visited_urls)}[/bold green]"
            )
            summary_table.add_row(
                "Final Size:", f"[bold cyan]{self.current_size_bytes / (1024 * 1024):.2f} MB[/bold cyan]"
            )

            self.console.print(Panel(summary_table, title="[bold blue]Session Summary", expand=False))


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
