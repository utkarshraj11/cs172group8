from flask import Flask
from flask import render_template, request
import re
import lucene
import os
from org.apache.lucene.store import MMapDirectory, SimpleFSDirectory, NIOFSDirectory
from java.nio.file import Paths
from org.apache.lucene.analysis.standard import StandardAnalyzer
from org.apache.lucene.document import Document, Field, FieldType
from org.apache.lucene.queryparser.classic import QueryParser
from org.apache.lucene.index import FieldInfo, IndexWriter, IndexWriterConfig, IndexOptions, DirectoryReader
from org.apache.lucene.search import IndexSearcher, BoostQuery, Query
from org.apache.lucene.search.similarities import BM25Similarity

app = Flask(__name__)

lucene.initVM(vmargs=['-Djava.awt.headless=true'])

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
   results.sort(key=lambda x: x["score"], reverse=True)
   return results

@app.route("/", methods=["GET", "POST"])
def hello_world():
    results=None
    query_str=""
    if request.method == "POST":
        query_str = request.form.get("query")
        results = search("index", query_str)

    return render_template('hello.html', results=results, query=query_str)

if __name__ == "__main__":
    app.run(debug=True)