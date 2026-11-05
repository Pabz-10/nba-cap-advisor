# NBA Cap and Trade Advisor: Design Doc

Originally Oct 29, 2026. Updated Nov 5, 2026 (home team, data source, schedule). Owner: Pabil.
Deadline: ProCogia AI Intern in-person practical demo, Nov 12, 2026.

## 1. Problem and business value

An NBA front-office analyst needs fast, cited answers to cap and trade questions about a real team's trades. Today that means searching a very long CBA by hand and doing the salary math separately.

- **Who it is for:** a front-office analyst, or an agent or journalist, asking things like "can we take back this much salary in this trade, and which CBA article says so?"
- **The problem:** the answer lives in two places. The rules are in the CBA text (salary cap, aprons, trade salary matching, roster rules). The numbers are in the teams' contracts. A wrong answer is costly, and the language is dense and full of exceptions.
- **What the system does:** retrieves the right CBA articles, computes team numbers with tested functions, checks every claim, then answers with citations, asks a clarifying question, or abstains.

### How we measure success
- **Citation accuracy:** the cited article actually supports the answer.
- **Numeric accuracy:** computed figures match the contract data.
- **Correct abstention:** the system declines questions the CBA or the data cannot support.
- **Time to answer** compared with searching by hand.

### Why multiple agents
A single agent with tools could do this, and we should say so before they ask. We split it for three reasons: each part (retrieval, calculation, verification) can be tested on its own; a cheaper model can handle routing while a stronger one writes and checks answers; and the verifier is independent of the step that wrote the answer.

## 2. Decisions locked in and scope

| Decision | Choice |
| --- | --- |
| Domain | NBA cap and trade advisor. Home team: Toronto Raptors (default view) |
| Documents | The 2023 NBA CBA (the current one), chunked by article/section |
| Contract data | League-wide player salaries from Basketball Reference (CSV), one table, with an as-of date (figures are reported, not official) |
| Framework | Python with LangGraph |
| Vector database | Chroma to start (pgvector is the alternative) |
| Embeddings | A local open-source model, so no second key or rate limit |
| LLM | Gemini on the Google AI Studio free tier, no billing account |
| Coding help | Claude Code, disclosed in the presentation |

### In scope
- Three agents (rules, data, verifier) plus a router and a composer, with a trade check that runs once per team in a deal
- A static workflow and a dynamic workflow sharing the same agents and knowledge base
- A command-line demo, with a simple interface only if time allows
- An evaluation harness of about 25 questions
- One comparison of two context configurations on a representative query

### Out of scope
- Live data feeds, user accounts, a polished UI
- Hybrid retrieval and rerankers, unless evaluation shows retrieval is the weak spot
- Anything that depends on private or non-public data

## 3. Architecture

Three agents (rules, data, verifier) share one knowledge base. A router chooses the path, the rules and data agents gather evidence, a composer drafts the answer, and the verifier decides whether it is allowed out.

Flow: question -> router -> (rules agent and/or data agent, or ask to clarify) -> composer -> verifier -> answer, revise once, or abstain.

- The router can send a question to the rules agent, the data agent, or both.
- The verifier sends a draft back to the composer once. If a claim is still unsupported, the system abstains.
- If the router sees a detail is missing, it asks a clarifying question instead of guessing. The user's reply goes back through the router as a new run that keeps the earlier context.
- The router tracks a clarify count (clarify_count in state) and allows at most 2 clarifying questions per conversation.

### Agent responsibilities

| Agent | Responsibility | Tools and skills it calls | Hands off |
| --- | --- | --- | --- |
| Router | Reads the question, picks rules, data, or both, or asks to clarify | Classifier prompt (start rule-based, keywords), small state object (team, season, player) | Route and state to the next agent |
| Rules agent | Finds the CBA articles that answer the question | Vector search over Chroma, query rewrite, similarity threshold | Chunks with article numbers and scores |
| Data agent | Computes payroll and apron status for any team, and checks one side of a trade (run once per team in a deal) | Fixed functions: payroll, gap to each apron line, salary matching | Values with source and date |
| Composer | Drafts the answer from the evidence only | Answer prompt with citation format | Draft plus the evidence it used |
| Verifier | Checks citations exist, numbers match, claims are supported | Citation and number checks written as functions it calls, then a model check | Approve, send back once, or abstain |

We call a step an agent when it calls tools and decides what to do with the results. That makes the rules agent, data agent and verifier agents, while the router and composer are single model steps. Agents exchange information through a shared state object: the question, the route, retrieved chunks, computed values, the draft, and the verifier's verdict. Writing state down this way makes each handoff easy to log and test.

## 4. Data, RAG and vector database

The knowledge base is the CBA, split along its own article structure so every retrieved chunk carries the article number it needs to be cited.

- **Sources:** the 2023 NBA CBA (public) and league-wide contract data from Basketball Reference. Check the data source's terms of use; this is a non-commercial demo and the source is cited.
- **Preparation:** extract the CBA text, clean headers and page numbers, split by article and section. Printed page numbers differ from PDF page index (roman-numeral front matter). Watch for table of contents or index duplicates.
- **Metadata on every chunk:** article, section, page, CBA version, tier (core or maybe).
- **Chunking:** by article and section, not fixed size, and prepend the section title to the chunk text. A fixed-size split can separate a rule from its exceptions. Very long sections get split further with a small overlap and keep the same article metadata.
- **Scope tiers:** the CBA is 676 pages and many sections are not relevant. Core and maybe sections are embedded. Everything else is skipped.
  - Core: Article I (pp 1-14); Article VII Sections 2, 3, 4, 6, 8.
  - Maybe: Article II Sections 6, 7, 9, 10, 11; Article VII Sections 5, 7; Articles VIII and IX; Exhibits B and C; Articles XI, XIII, XXIV; Article XXIX Sections 1-3 and 5; Article VI Section 18.
- **Embeddings:** a local open-source model: free, no rate limits, fine for a document this size.
- **Retrieval:** dense similarity search, top-k, with a similarity threshold. Below the threshold the system treats retrieval as a miss and abstains instead of guessing.
- **Citations:** every answer lists the chunk IDs and article numbers it used. The verifier rejects any citation that was not actually retrieved.
- **Contracts store:** SQLite, one league-wide table keyed by player ID, queried by team through fixed functions. Not free-form SQL from the model.

### Data quality and limitations
- Salaries from third-party sites are reported figures, not official ones. Summed player salaries ignore dead money, cap holds and two-way contracts, so they will not match official payrolls. Say so in the presentation, and label the data with an as-of date.
- The CSV has quirks: cp1252 encoding, a junk first line, every line wrapped in outer quotes, damaged player names (use the player ID as the key), and 6 duplicated player IDs that would double count salary. Document the dedupe rule.
- The CBA changes over time and applies by season. The system answers only for the version loaded.
- Legal text has cross-references between articles. A chunk can be correct on its own and still miss an exception elsewhere. This is a known failure mode we should test for on purpose.

## 5. Workflows

Both workflows reuse the same agents, skills and knowledge base. The static one always takes the same steps. The dynamic one chooses its steps from the request and from what comes back.

### Static workflow (predefined steps)
1. Retrieve the top-k CBA chunks for the question.
2. Look up the relevant teams' numbers (both sides of a trade).
3. Compose an answer with citations.
4. Verify every claim.
5. Return the answer.

Predictable and easy to test, but it spends tokens on steps some questions do not need.

### Dynamic workflow (adapts to the request)

| Situation | What the router does |
| --- | --- |
| Pure rules question | Rules agent only |
| Pure numbers question | Data agent only |
| Question names a player or team and a rule | Both agents, then compose |
| Retrieval is weak (below the similarity threshold) | Rewrite the query and retry once, then abstain |
| Question is missing something needed (which player, which season) | Ask a clarifying question |
| Verifier finds an unsupported claim | Revise once with the failed claim flagged, then abstain or flag for human review |

### Error handling and stopping conditions
- A hard step cap and a time limit on every run so a loop cannot run away.
- At most one retry per failure type, then abstain. At most 2 clarifying questions per conversation (clarify_count in state). After that it answers with its assumptions stated, or abstains, and never asks a third time.
- Every tool call has a timeout. Rate-limit errors (expected on the free tier) trigger a short backoff.
- Fail closed: if the system cannot support a claim, it says so instead of answering.

## 6. Model selection and context management

- **Model choice:** a smaller, faster Gemini model for routing and simple steps, a stronger one for composing and verifying. Check which models and rate limits the account actually shows in AI Studio before locking this in, because limits differ by model and are not fixed.
- **Retrieved evidence:** pass only the top-k chunks, labelled with article numbers, and tell the model to answer only from them.
- **Conversation history:** keep the last few turns, and carry forward the facts that matter (team, season, player under discussion) as a small state object instead of the full transcript.
- **Token budget:** cap evidence tokens per call and drop the lowest-ranked chunks first when over it.

### Context comparison on one representative query
Run the same query, one that needs both a rule and a number, under two configurations and record the results.

| | Config A | Config B |
| --- | --- | --- |
| Retrieved chunks | top-3 | top-8 |
| Expected effect | Cheaper and faster, risks missing an exception | More complete, more noise and more tokens |
| Measure | Answer correctness, citation accuracy, tokens used, latency | Same |

Write down the prediction before running it, then compare. A surprise is fine if you can explain it.

## 7. Evaluation and hallucination handling

One command runs a fixed set of about 25 questions with known answers and prints a score table, so any change to a setting can be judged by its effect on the same test.

### Test set (write expected answers from the CBA text before running anything)

| Type | Count (about) | What it checks |
| --- | --- | --- |
| Clear rules question | 6 | Retrieval and citation |
| Clear numbers question | 5 | Data agent accuracy |
| Rule plus numbers | 6 | Routing to both agents |
| Ambiguous request | 3 | Asks a clarifying question |
| Missing information | 3 | Abstains instead of guessing |
| Deliberate failure case | 2 | A case we expect to fail, so we can show diagnosis |

A small extra set checks that the system never asks a third clarifying question.

### What the harness records
- Answer correct or not, against the expected answer
- Retrieval hit: was the right article in the retrieved chunks
- Citation valid: do the cited articles exist and support the claim
- Abstained or clarified when it should have (in tests, a clarifying question counts as the final outcome)
- Tokens and latency per question

### How unsupported claims arise, and the defense

| Cause | Defense |
| --- | --- |
| Retrieval misses the key article | Similarity threshold, then retry or abstain |
| Model fills the gap from general knowledge | Prompt forbids it, verifier checks each claim against evidence |
| A rule's exception sits in another article | Known limit, tested on purpose, flagged for human review |
| Wrong or stale contract data | Data agent returns source and date, verifier compares numbers to tool output |
| Invented citation | Code check that every cited chunk was retrieved |

The verifier has two layers. Code checks the cheap things (citations exist, numbers match). A model then checks that each claim is supported by the evidence. For the demo, use real scenarios: a legal trade, a rule-breaking trade, and an unclear question, using teams in different apron situations.

## 8. Infrastructure, cost and trade-offs

Everything runs on a laptop at zero cost. The main operational constraint is the free tier's rate limits.

- **Setup used:** Python project, local Chroma store on disk, local embedding model, SQLite for contracts, Gemini through the AI Studio free tier, a command-line demo.
- **Cost:** none. The free tier has no billing account to charge. The trade-off is that free-tier prompts can be used by Google to improve its products, which is acceptable here because we only send public documents.
- **Performance:** limits differ by model and are not published in a form we could confirm. Add a short delay between calls and retry with backoff. Run the full evaluation before the presentation, not live.
- **Operational decisions to mention:** cache embeddings so they are built once, save evaluation results to files, hard step cap on every run.

### What we would recommend for production
- A paid tier or provider with data-privacy terms that suit client data
- A managed or Postgres-based vector store with access control
- Tracing and logging of every step (an observability tool such as Langfuse) so decisions can be audited
- A process to reload the CBA when it is amended, with versioned chunks

## 9. Design choices and alternatives

| Decision | Our choice | Alternatives | Why ours | When we would switch |
| --- | --- | --- | --- | --- |
| Orchestration | LangGraph | Plain Python, LangChain agents, CrewAI, AutoGen | Explicit nodes, edges and state make routing and stopping easy to see and change | A simpler flow with no branching |
| Vector database | Chroma | pgvector, Pinecone, Qdrant, FAISS | Fast to set up, local, free | Need SQL joins with metadata or shared access (pgvector) |
| Chunking | By article and section, with metadata | Fixed size with overlap | Legal text is organised by article, and citations need the article number | Documents with no clear structure |
| Embeddings | Local open-source model | Hosted embedding API | Free, no rate limits, private | Retrieval quality turns out to be the weak spot |
| Retrieval | Dense, top-k, similarity threshold | Hybrid keyword plus dense, reranker | Simplest thing that can work, and we measure first | Evaluation shows exact terms like "Second Apron" are missed |
| Data agent | Fixed, tested functions | LLM writes SQL | Models should not do arithmetic from memory, and free-form SQL is harder to trust | Many unpredictable question types |
| Verifier | Code checks plus an LLM check | LLM-as-judge only | Code catches fake citations and wrong numbers cheaply | Claims that need judgment about meaning |
| Models | Smaller for routing, stronger for answers | One model everywhere | Matches cost and latency to difficulty | Free-tier limits make the split impractical |
| Evaluation | Golden set run by one command | Manual spot checks | Repeatable, and shows whether a change helped | Never |

### The question to prepare for
"Why multiple agents?" The honest answer is separation of concerns, testability, cost control and an independent verifier, not that one agent could not do it.

## 10. Live Q&A prep

They may ask for a small change during the 30 minutes of Q&A. For each likely change, write down the expected effect first, then test it during the build and record what actually happened.

| Likely change | Expected effect | Observed (fill in during the build) |
| --- | --- | --- |
| Raise or lower top-k | Higher: more recall, more noise, tokens and latency | |
| Change chunk size | Larger: more context per hit, blurrier matches. Smaller: sharper matches, rules split from exceptions | |
| Tighten the similarity threshold | Fewer wrong answers, more abstentions, risk of refusing answerable questions | |
| Change a routing condition | Different questions go to both agents, changes cost and accuracy | |
| Change retry limit, step cap or clarify limit | Higher: more recovery, more cost and latency. Needs a hard stop. A higher clarify limit means more questions to the user and fewer guesses | |
| Swap the model | Cheaper and faster, probably lower quality on hard questions | |
| Tighten or loosen the verifier | Stricter: fewer unsupported claims, more false abstentions | |
| Filter retrieval by tier or article (core only vs core plus maybe) | Faster and sharper if right, a total miss if wrong | |
| Add a new tool (for example a luxury tax calculation) | New function, clear description for the router, new test cases | |
| Add a test case and run the harness | Shows the effect on the score table | |

### Other questions to prepare for
- How would you handle a CBA amendment or a new season?
- What about prompt injection in a user question?
- What does one query cost, and how would it scale?
- What would you do with more time, data or compute?
- How did you use AI tools, and which parts can you explain line by line?

If a result surprises you live, say what you expected, what you saw, your best guess why, and how you would check.

## 11. How we build it

We build it the way we built Running Analytics: Pabil writes the code, Claude gives hints and explanations, and a full code answer comes only when he asks for it.

### Working method
- **One small task at a time.** Each task has a goal, a hint, and a way to check it worked.
- **Hints first, not code.** If stuck, ask for a bigger hint, then an example, then the code. His call.
- **Paste the error.** Errors and outputs get pasted in and Claude helps read them.
- **Predict, run, compare.** Before changing any setting, write the expected effect, then run and compare. This is the Q&A practice.
- **Understand before moving on.** If a piece cannot be explained, simplify or cut it.
- **Claude pushes back.** Claude says where the approach is going wrong, flags scope creep, and checks every claim against the real code before it goes on a slide or the resume.

### Build order (revised plan, Nov 5 to Nov 12)
The target is a thin working end-to-end version early, then deepening it.

**Phase 1: Foundations (Nov 5 to Nov 6)**
- [ ] Create a Google AI Studio key, check available models and rate limits
- [ ] Project setup: venv, folder layout, .env, git, .gitignore
- [ ] Put the CBA PDF and the salaries CSV in data/raw
- [ ] Extract the CBA text and check text quality
- [ ] Draft 8 to 10 test questions with expected answers from the CBA text

**Phase 2: Data and ingestion (Nov 6 to Nov 7)**
- [ ] Loader: clean the CSV, dedupe, load into SQLite with an as-of date
- [ ] Verify the Raptors total against a second source
- [ ] Chunk the core and maybe CBA sections with metadata, embed, store in Chroma
- [ ] Rules agent retrieves top-k and prints results with article numbers; first end-to-end answer with citations

**Phase 3: Data agent (Nov 7)**
- [ ] Fixed, tested functions: payroll, gap to each apron line, one-side trade check

**Phase 4: Orchestration (Nov 7 to Nov 9)**
- [ ] Static workflow in LangGraph
- [ ] Router, composer, and dynamic workflow
- [ ] Verifier (code checks first, then model check)
- [ ] Step cap, timeouts, retries, abstain and clarify paths

**Phase 5: Evaluation (Nov 9 to Nov 10)**
- [ ] About 25 questions with expected answers, harness and score table
- [ ] Context comparison (top-3 vs top-8)
- [ ] Q&A change experiments, fill in the observed column

**Phase 6: Presentation (Nov 10 to Nov 12)**
- [ ] Slides, about 8 to 10, one per topic
- [ ] Backup screenshots or recording of a success and a failure
- [ ] Two full rehearsals, including live changes
- [ ] Write the AI-tools disclosure

### Other deadlines to protect
- Amazon OA decision, CIBC and Shell updates are still open.
- Confirm the ProCogia start date and term.

## 12. Risks, open decisions and presentation outline

### Risks

| Risk | Mitigation |
| --- | --- |
| Too many parts built at once | Thin end-to-end version first, deepen only after it works |
| Cannot explain a piece live | Simplify or cut anything not understood, rehearse the Q&A changes |
| Free-tier rate limits slow evaluation | Delays and backoff, run the full evaluation before the day, keep backup recordings |
| CBA text is messy to extract or chunk | Check the document early, budget extra time for cleaning |
| Contract data is unofficial and has duplicates | Dedupe rule, as-of date, state it openly as a limitation |
| Less than a week left | Cut scope first (UI, extra tools), never cut the eval harness or verifier |
| Claims on slides or the resume that the code does not support | Check every claim against the real code first |

### Open decisions
- Which partner teams for the demos (decide after the deduped payrolls; likely one team over the second apron and one under the cap)
- How to resolve the 6 duplicate player rows (check Basketball Reference)
- Which Gemini models and limits the account actually shows

### Presentation outline (30 minutes, then 30 minutes of Q&A)
Presented as if the audience is the client and we are recommending the solution.

1. Problem and business value, how success is measured, why multiple agents
2. Data, RAG and vector database, with limitations
3. Architecture, agent skills and the two workflows
4. Model choice and the context comparison
5. Evaluation results, including a failure and what it taught us
6. Infrastructure and trade-offs
7. Live demo: a successful scenario and a failure or uncertainty scenario
8. Lessons learned, limitations and next steps

Disclose AI tool use plainly: Claude Code for coding help, with every component explainable and changeable by Pabil.
