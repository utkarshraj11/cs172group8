import re
from bs4 import BeautifulSoup
from utils import extract_title, extract_headings, extract_text_content, last_edited_date, extract_infobox
import logging, sys
logging.disable(sys.maxsize)


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


def create_index(input_dir, dir):
   if not os.path.exists(dir):
       os.mkdir(dir)
   store = SimpleFSDirectory(Paths.get(dir))
   analyzer = StandardAnalyzer()
   config = IndexWriterConfig(analyzer)
   config.setOpenMode(IndexWriterConfig.OpenMode.CREATE)
   writer = IndexWriter(store, config)

   metaType = FieldType()
   metaType.setStored(True)
   metaType.setTokenized(False)

   contextType = FieldType()
   contextType.setStored(True)
   contextType.setTokenized(True)
   contextType.setIndexOptions(IndexOptions.DOCS_AND_FREQS_AND_POSITIONS)

   infoboxType = FieldType()
   infoboxType.setStored(True)
   infoboxType.setTokenized(False) 

   count = 0
   for filename in os.listdir(input_dir):
       count += 1
       if filename.endswith(".html"):
           file_path = os.path.join(input_dir, filename)
           with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
               soup = BeautifulSoup(f.read(), "html.parser")
               title = extract_title(soup)
               headings = extract_headings(soup)
               text_content = extract_text_content(soup)
               last_modified_date = last_edited_date(soup)
               infobox = extract_infobox(soup)
               doc = Document()
               doc.add(Field('Title', str(title), metaType))
               doc.add(Field('Heading', str(headings), contextType))
               doc.add(Field('Context', str(text_content), contextType))
               doc.add(Field('Modify date', str(last_modified_date), metaType))
               doc.add(Field('Infobox', str(infobox), infoboxType))
               writer.addDocument(doc)
               print(count)
   writer.close()




lucene.initVM(vmargs=['-Djava.awt.headless=true'])
create_index('combined_output', 'index2')




def search(index_dir,query_str,field="Context",top_k =10):
   storer = NIOFSDirectory(Paths.get(index_dir))
   reader = DirectoryReader.open(storer)
   searcher = IndexSearcher(reader)

   parses = QueryParser(field,StandardAnalyzer())
   query = parses.parse(query_str)

   score_hits = searcher.search(query,top_k).scoreDocs
   results = []
   for hit in score_hits:
       doc = searcher.doc(hit.doc)
       content = doc.get("Context")[:250]
       results.append({
           "score": round(hit.score, 4),
           "title": doc.get("Title"),
           "modified_date": doc.get("Modify date"),
           "content_clip": re.sub(r"\s+", " ", content) + "...",
       })
   reader.close()
   return results

# testing code - David Beckham (query)
results = search("index", "David Beckham")

#only for search output purposes (probably not necessary for flask UI)
def show(results,query):
   print(f"\n Query: {query!r}   ({len(results)} hits)")
   print("-" * 78)
   for i, r in enumerate(results,1):
       print(f"{i}. [{r['score']:.3f}] {r['title']} {r['modified_date']}\n{r['content_clip']}")
       print("\n")

#testing code - David Beckham (query)
print(show(results,"David Beckham"))
