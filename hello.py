from flask import Flask
from flask import render_template, request
import re
import lucene
import os

from utils import load_json_file
from org.apache.lucene.store import MMapDirectory, NIOFSDirectory
from java.nio.file import Paths
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.document import Document, Field, FieldType
from org.apache.lucene.queryparser.classic import QueryParser, MultiFieldQueryParser
from org.apache.lucene.index import FieldInfo, IndexWriter, IndexWriterConfig, IndexOptions, DirectoryReader
from org.apache.lucene.search import IndexSearcher, BoostQuery, Query, BooleanQuery, BooleanClause
from org.apache.lucene.search.similarities import BM25Similarity

app = Flask(__name__)

lucene.initVM(vmargs=['-Djava.awt.headless=true'])

PAGERANK = load_json_file("./pagerank.json")
print(f"Loaded {len(PAGERANK)} PageRank scores")

def snippet(content, query):
    sentences = content.split('.')
    query_terms = query.lower().split()
    best_sentence = ""
    score = 0
    for sentence in sentences:
        if len(sentence) < 10:
            continue
        sentence_score = sum(1 for term in query_terms if term in sentence.lower())
        if sentence_score > score:
            score = sentence_score
            best_sentence = sentence 
    if best_sentence:
        return best_sentence.strip() + "..."
    return content[:250] + "..."


def search(index_dir,query_str,field="Context",top_k =10):
   lucene.getVMEnv().attachCurrentThread()
   storer = NIOFSDirectory(Paths.get(index_dir))
   reader = DirectoryReader.open(storer)
   searcher = IndexSearcher(reader)

   parses = QueryParser(field,StandardAnalyzer())
   query = parses.parse(query_str)

   score_hits = searcher.search(query,top_k).scoreDocs
   results = []
   for hit in score_hits:
       doc = searcher.doc(hit.doc)
       content = doc.get("Context")
       results.append({
           "score": round(hit.score, 4),
           "title": doc.get("Title"),
           "modified_date": doc.get("Modify date"),
           "content_clip": snippet(content, query_str),
       })
   reader.close()
   return results
# multi field search function 
def multifield_search(index_dir,query_str,fields=["Title","Heading","Context"],top_k =10,rank_mode="lucene"):
    lucene.getVMEnv().attachCurrentThread()
    storer = NIOFSDirectory(Paths.get(index_dir))
    reader = DirectoryReader.open(storer)
    searcher = IndexSearcher(reader)
    analyzer = StandardAnalyzer()
    builder = BooleanQuery.Builder()
    for field in fields:
        parsed = QueryParser(field, analyzer).parse(query_str)
        builder.add(parsed, BooleanClause.Occur.SHOULD)
    query = builder.build()
    
    # Fetch more than we need so PageRank can re rank them.
    fetch_k = top_k if rank_mode == "lucene" else top_k * 5
    score_hits = searcher.search(query,fetch_k).scoreDocs
    results = []
    for hit in score_hits:
        doc = searcher.doc(hit.doc)
        title = doc.get("Title")
        lucene_score = hit.score
        page_rank_score = PAGERANK.get(title,0)
        if rank_mode == "pagerank":
            final_score = page_rank_score
        else:  # lucene
            final_score = lucene_score
        content = doc.get("Context")
        results.append({
            "title": title,
            "score": round(final_score,4),
            "lucene_score": round(lucene_score,4),
            "pagerank_score": round(page_rank_score,6),
            "modified_date": doc.get("Modify date"),
            "content_clip": snippet(content, query_str),
            "infobox": doc.get("Infobox"),
        })
    reader.close()
    
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k] #take top_k

@app.route("/", methods=["GET", "POST"])
def hello_world():
    results=None
    query_str=""
    rank_mode = "lucene"
    if request.method == "POST":
        query_str = request.form.get("query")
        # results = search("index", query_str)
        rank_mode = request.form.get("rank_mode","lucene")
    #add multi field search
        results = multifield_search("index1", query_str,rank_mode=rank_mode)

    return render_template('hello.html',results=results,query=query_str,rank_mode=rank_mode,pagerank_available=bool(PAGERANK))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)