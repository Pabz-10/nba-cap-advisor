# NBA Cap and Trade Advisor

## What this is
Multi-agent AI demo for the ProCogia AI Intern in-person practical on Nov 12, 2026.
30 min presentation (as if recommending to a client), then 30 min Q&A with possible live changes.
CLI demo is enough. AI tool use is allowed but must be disclosed.
Full design is in docs/design_doc.md. The official brief is in docs/procogia_brief.md and wins if they conflict. Read both before suggesting anything.

## How to work with me (important)
- I write the code. You give hints, explanations and review. Do NOT write code unless I ask.
- One small task at a time. I will paste errors.
- Tell me where I'm going wrong and suggest improvements.
- Casual tone, no em dashes. Explain the "why" so I can defend design choices in Q&A.
- Verify numbers by running things. Never state figures you have not computed.
- Before I change a setting (top-k, threshold, etc.), have me write down a prediction first.

## Project
- Home team: Toronto Raptors. Demo partner teams chosen after checking deduped payrolls.
- RAG over the 2023 NBA CBA (Chroma, local open-source embeddings) plus a league-wide
  contracts table (SQLite) queried by fixed, tested functions.
- A trade is checked on both sides by calling the same function per team.
- LLM: Gemini via Google AI Studio free tier (no billing, rate limits, backoff needed).
- Framework: LangGraph. Python.

## Architecture
- 3 agents: rules agent (vector search, query rewrite, similarity threshold),
  data agent (payroll, apron status, one-side trade check), verifier (citation exists in
  retrieved chunks, numbers match tool output, then model check; approve / revise once / abstain).
- Router (start rule-based, move to LLM classifier if eval shows misrouting) and composer.
- Static workflow: retrieve, look up numbers for both teams, compose with citations, verify, return.
- Dynamic workflow: router picks rules / data / both / clarify; retry weak retrieval once
  with rewrite then abstain; max 2 clarifying questions (clarify_count in state);
  verifier fail -> revise once then abstain; step cap, time limit, tool timeouts, fail closed.
- Both workflows share the same agents, skills and knowledge base.

## CBA ingestion
- Chunk by article/section, prepend the section title to chunk text.
- Metadata: article, section, page, cba_version, tier (core/maybe).
- Strip headers/footers/page numbers, watch for TOC/index duplicates.
- Printed page numbers differ from PDF page index (roman-numeral front matter).
- Core: Art I (pp 1-14); VII s2 (169-197), s3 (198-210), s4 (211-225), s6 (231-248), s8 (260-265).
- Maybe: Art II s6,7,9,10,11; VII s5, s7; VIII; IX; Exhibits B, C; XI; XIII; XXIV;
  XXIX s1-3,5; VI s18. Skip everything else.

## Contracts data (data/raw/NBA_Player_Salaries.csv, from Basketball Reference)
- cp1252 encoding, CRLF. Every line is wrapped in outer double quotes: strip them, then csv-split.
- Line 1 is a junk banner. Real header is line 2. Last column is the BR player ID.
- 461 player rows, 30 team codes. Key on player ID, not name (13 names have damaged "?" characters).
- Columns: Rk, Player, Tm, 2026-27 ... 2031-32, Guaranteed, player ID. Blank = no contract that year.
- 6 duplicate player IDs (same 2026-27 salary under two teams): Lillard MIL/POR, Beal PHO/LAC,
  Caldwell-Pope MEM/PHI, Klay Thompson DAL/MIA, Prosper MEM/DAL, Isaac ORL x2.
  Need a dedupe rule, verify against Basketball Reference, document as a limitation.
- Summed salaries are NOT official payrolls (dead money, cap holds, two-way contracts).
  Store an as-of date (file received Nov 5, 2026).
- Naive Raptors total from the file: about $201.19M (just over the tax line, under the first apron).
  Recheck after dedupe against Spotrac / Hoops Rumors.
- Never edit the raw file. Cleaning happens in the loader, output goes to data/processed and SQLite.

## 2026-27 figures (official, pr.nba.com)
Cap $164.961M; min team salary $148.465M; tax line $200.428M; first apron $209.015M;
second apron $221.686M; non-taxpayer MLE $15.044M; taxpayer MLE $6.064M; room MLE $9.366M.
Apron restriction details and matching tiers must be checked against the CBA text, not memory.

## Evaluation
- About 25 questions: 6 rules, 5 numbers, 6 rules+numbers, 3 ambiguous, 3 missing info,
  2 deliberate failures, plus a few testing the clarify cap.
- Metrics: correct answer, retrieval hit, valid citation, correct abstain/clarify, tokens, latency.
- One-command harness (eval/run_eval.py).

## Demo requirements to cover
Problem/value, data/RAG, architecture, model and context management (compare two context
configs on one query, e.g. top-3 vs top-8), evaluation and hallucination handling
(success, ambiguous, missing info, a failure), infrastructure/trade-offs, live demo
(success + failure/uncertainty), limitations/next steps.

## Likely live Q&A changes (predict, run, compare, write down)
top-k, chunk size, similarity threshold, routing condition, retry/step/clarify limits,
swap model, verifier strictness, metadata filter (core only vs core+maybe), new tool, new test case.

## Status and plan (today is Nov 5, about 7 days left)
1. Env, key, data in place, CBA text extraction, first 8-10 draft test questions
2. Loader: CSV -> SQLite with dedupe + as-of date; ingest CBA -> Chroma with tiers
3. Rules agent, bare end-to-end version
4. Data agent
5. Router, composer, verifier
6. Full static + dynamic workflows, eval harness
7. Experiments, slides (8-10), backup screen recording, AI-tools disclosure, rehearsals

## Folder structure
nba-cap-advisor/: .env, .gitignore, README.md, requirements.txt, data/raw, data/processed,
vectorstore/, src/{config.py, ingest/, tools/, agents/, graph/, main.py},
eval/{questions.json, run_eval.py, results/}, tests/, docs/
.gitignore: .env, data/raw, vectorstore/
