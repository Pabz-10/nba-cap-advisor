from src.config import COMPOSER_MODEL
from src.tools.llm import get_llm

NOT_FOUND = "I couldn't find this in the CBA, so I won't guess."


def format_chunks(chunks):
    """Turn the retrieved chunks into one block of text, each labeled with its citation and pages."""
    # build one string with each chunk's citation, pages and text
    
    chunk_blocks = []
    # loop through each chunk and build the string block form each chunk
    for chunk in chunks:
        citation = chunk["citation"]
        pages= chunk["pages"]
        text = chunk["text"]
        chunk_text = f"[{citation}] (pages {pages})\n{text}"
        chunk_blocks.append(chunk_text)

    # glues all of our blocks to one string 
    res = "\n\n".join(chunk_blocks)
    return res

def compose_answer(question, rules_result):
    """Answer the question using only the retrieved CBA chunks, with citations."""
    
    if rules_result["passed"] == False:
        return {
                    "answer" : NOT_FOUND,
                    "abstained" : True,
                    "sources" : []
                }

    # write the prompt: instructions + labeled chunks + the question
    instructions = """You are answering a question about the NBA Collective Bargaining Agreement (CBA). Use only the CBA sections below. Do not use outside knowledge.

Rules:
1. Every claim must cite the section it came from, using the exact label in square brackets, for example [Article VII, Section 8(d)].
2. Only cite labels that appear in the sections below.
3. If the sections do not answer the question, reply with exactly: """ + NOT_FOUND + """
4. Keep the answer short and in plain language.

CBA sections:
"""
    prompt = instructions + format_chunks(rules_result["chunks"]) + "\n\nQuestion: " + question

    # send it to the composer model, fail closed if it errors
    try:
        reply = get_llm(COMPOSER_MODEL).invoke(prompt)
    except Exception:
        return {
                    "answer" : NOT_FOUND,
                    "abstained" : True,
                    "sources" : []
                }
    # return the answer, whether we abstained, and the citations we gave the model
       # return the answer, whether we abstained, and the citations we gave the model
    answer = reply.text.strip()

    sources = []
    for chunk in rules_result["chunks"]:
        sources.append(chunk["citation"])

    return {
        "answer": answer,
        "abstained": answer == NOT_FOUND,
        "sources": sources
    }