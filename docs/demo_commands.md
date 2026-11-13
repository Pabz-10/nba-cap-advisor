# Demo commands (copy and paste)

Dynamic is the default mode.

## 1. Cited answer
```bash
.venv/bin/python -m src.main "How long after signing can a draft rookie be traded?"
```
Check: CBA PDF page 285, 8(d)(i), thirty days.

## 2. Cited answer
```bash
.venv/bin/python -m src.main "Can a team trade cash in a trade?"
```
Check: CBA PDF page 284, 8(a), 5.15% of the Salary Cap.

## 3. Asks vs refuses
```bash
.venv/bin/python -m src.main "Can we trade him?" --mode static
```
```bash
.venv/bin/python -m src.main "Can we trade him?"
```
When it asks, reply: `Jakob Poeltl for Dyson Daniels`

## 4. Skipping work
```bash
.venv/bin/python -m src.main "What is the Raptors payroll?" --mode static
```
```bash
.venv/bin/python -m src.main "What is the Raptors payroll?"
```

## 5. Context change
```bash
.venv/bin/python -m src.main "How long after signing can a free agent be traded?" --top-k 5 --show-chunks
```
```bash
.venv/bin/python -m src.main "How long after signing can a free agent be traded?" --top-k 8 --show-chunks
```

## 6. A real failure
```bash
.venv/bin/python -m src.main "Can we trade Immanuel Quickley and Jakob Poeltl for Damian Lillard?"
```

## Eval results to open
`eval/results/FINAL_dynamic_k8.json`


## full eval
```bash
##.venv/bin/python -m eval.run_eval --top-k 5
```