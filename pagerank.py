import json
import os
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from utils import extract_title,normalize_url,save_json_file

DAMPING = 0.85
CONVERGENCE = 0.0001

def extract_canonical_url(soup):
    # Links with <link rel="canonical" href="...">
    link = soup.find("link",{"rel": "canonical"})
    if link and link.get("href"):
        return normalize_url(link["href"])
    return None

def extract_valid_outlinks(soup,base_url):
    # Not exhaustive but works for what we have
    not_articles = (
    "/wiki/File:","/wiki/Special:","/wiki/Help:",
    "/wiki/Category:","/wiki/Wikipedia:","/wiki/Talk:",
    "/wiki/Template:","/wiki/Portal:","/wiki/User:")
    
    content = soup.find("div",{"id": "mw-content-text"})
    if not content:
        return []
    seen_links = set()
    for a in content.find_all("a",href=True):
        href = a["href"]
        if a["href"].startswith(not_articles):
            continue
        absolute = urljoin(base_url,href)
        if "en.wikipedia.org" not in absolute or "/wiki/" not in absolute:
            continue
        seen_links.add(normalize_url(absolute))
    return list(seen_links)

def build_graph(input_dir):
    url_to_title = {}
    pages = []  # (title,url,soup)

    for filename in os.listdir(input_dir):
        if not filename.endswith(".html"): # because outputs.json
            continue
        path = os.path.join(input_dir,filename)
        with open(path,"r",encoding="utf-8",errors="ignore") as f:
            soup = BeautifulSoup(f.read(),"html.parser")
        url = extract_canonical_url(soup)
        title = extract_title(soup)
        if url and title:
            url_to_title[url] = title
            pages.append((title,url,soup))

    print(f"built url->title map: {len(url_to_title)} pages")

    # Index files only stores title not url
    graph = {}
    for title,url,soup in pages:
        outlinks = extract_valid_outlinks(soup,url)
        targets = []
        for outlink in outlinks:
            if outlink in url_to_title and url_to_title[outlink] != title:
                targets.append(url_to_title[outlink])
        graph[title] = targets

    return graph

# Took from assignment 2
def page_rank(adjacency_list,d=DAMPING,threshold=CONVERGENCE):
    page_ranks = {page: 1.0 for page in adjacency_list}
    N = len(adjacency_list)
    constant = (1 - d) / N
    iterations = 0

    while True:
        next_pageranks = {}
        score_change = 0
        for target_page in adjacency_list:
            incoming_rank_sum = 0
            # Check for incoming links to current page
            for page,outgoing_links in adjacency_list.items():
                if target_page in outgoing_links:
                    incoming_rank_sum += page_ranks[page] / len(outgoing_links)
            new_rank = constant + d * incoming_rank_sum
            next_pageranks[target_page] = new_rank
            score_change = max(score_change,abs(new_rank - page_ranks[target_page]))
        page_ranks = next_pageranks
        iterations += 1
        if score_change < threshold:
            break
    print(f"  converged in {iterations} iterations")
    return page_ranks


def main():
    print(f"Building graph")
    graph = build_graph("combined_output")
    edges = sum(len(v) for v in graph.values())
    print(f"graph: {len(graph)} nodes,{edges} edges")

    print("Computing PageRank")
    scores = page_rank(graph)
    top = sorted(scores.items(),key=lambda kv: -kv[1])[:15]
    
    print("Top 15 by PageRank:")
    for title,score in top:
        print(f"  {score:.5f}  {title}")
        
    save_json_file(scores,"./pagerank.json")
        
if __name__ == "__main__":
    main()
