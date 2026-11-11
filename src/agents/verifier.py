import re

from src.config import VERIFIER_MODEL
from src.tools.llm import get_llm


def check_citations(answer, allowed_citations):
    """Every [label] in the answer must be one the model was allowed to cite."""
    used_cited = re.findall(r"\[([^\]]+)\]", answer)

    #  no citations at all -> return False
    # loop over cited, any label thats not in our sources -> return False
    #  otherwise return True
    if not used_cited:
        return False

    # citations are what the model used, allowed_citations is what it can use 
    for citations in used_cited:
        if citations not in allowed_citations:
            return False
    return True 


def find_dollars(text):
    """Pull out every dollar amount, without the trailing comma from a sentence."""
    return [amount.rstrip(",") for amount in re.findall(r"\$\d[\d,]*", text)]


def check_numbers(answer, evidence):
    """Every dollar amount in the answer must appear in the evidence."""
    # get the dollars from the evidence

    # these are the dollars the model was given and can only use
    allowed_dollars = find_dollars(evidence)

    # # these are the dollars the model actually used 
    used_dollars = find_dollars(answer)
    # loop over the dollars in the answer, any not in the evidence -> return False
    for dollar in used_dollars:
            if dollar not in allowed_dollars:
                return False     
    return True 



def check_with_model(question, answer, evidence):
    """Ask the model if the evidence supports the answer. Fail closed if it errors."""
    # TODO: prompt: question + evidence + answer, "Reply with exactly SUPPORTED or NOT_SUPPORTED"

    instructions = """You are checking an answer about the NBA CBA and team salaries. Decide if every claim in the answer is supported by the evidence. Use only the evidence, not outside knowledge. The one exception: team codes like TOR or CLE are standard NBA abbreviations, so treat a code and its team name or city as the same team.

Reply with exactly SUPPORTED or NOT_SUPPORTED.
"""

    prompt = instructions + "\n\nEvidence:\n" + evidence + "\n\nQuestion: " + question + "\n\nAnswer to check:\n" + answer

    # TODO: try: invoke get_llm(VERIFIER_MODEL), return reply.text.strip() == "SUPPORTED"
    try: 
        model = get_llm(VERIFIER_MODEL)
        reply = model.invoke(prompt)
        return reply.text.strip() == "SUPPORTED"
    
    except Exception:
        return False



def verify_answer(question, composed):
    """Run the checks in order and stop at the first failure."""
    # pull these out so the checks stay readable
    answer = composed["answer"]
    sources = composed["sources"]
    evidence = composed["evidence"]

    # an abstain can't be a hallucination, nothing to check
    if composed["abstained"]:
        return {"passed": True, "reason": "abstained"}

   # every citation has to be one the model was given
    if not check_citations(answer, sources):
        return {"passed": False, "reason": "bad citation"}

    # every dollar amount has to be in the evidence
    if not check_numbers(answer, evidence):
        return {"passed": False, "reason": "number not in evidence"}

    # a second model call checks the evidence supports the answer
    if not check_with_model(question, answer, evidence):
        return {"passed": False, "reason": "not supported"}

    return {"passed": True, "reason": "ok"}