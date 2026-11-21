## Decision differences between strategies (same emergencies)

A "different decision" means the sequence of EVA launches/aborts (time, crew, repair) differs. At hour 0 all strategies hold identical information, so identical early decisions are expected.

| pair | emergencies with different decisions | median first-divergence hour | caused by evidence / in-EVA readings | same final outcome anyway |
|---|---|---|---|---|
| B vs C | 128/400 (32%) | 28.5 | 66% | 48 |
| C vs D | 154/400 (38%) | 20.0 | 65% | 68 |
| B vs D | 148/400 (37%) | 20.0 | 76% | 64 |

### What separated them first

- **B vs C** kind: {'same decision, different time': 80, 'one strategy makes an extra decision': 36, 'different repair': 12}; cause: {'estimated risk fell on opposite sides of the gate': 48, 'in-EVA assessment differed': 36, 'post-abort crew reassessment': 36, 'repair held after radiation abort': 8}
- **C vs D** kind: {'same decision, different time': 96, 'one strategy makes an extra decision': 32, 'different action': 18, 'different repair': 8}; cause: {'in-EVA assessment differed': 54, 'estimated risk fell on opposite sides of the gate': 46, 'post-abort crew reassessment': 24, 'post-EVA review hold': 20, 'repair held after radiation abort': 8, 'forecast coverage': 2}
- **B vs D** kind: {'same decision, different time': 96, 'one strategy makes an extra decision': 28, 'different action': 18, 'different repair': 6}; cause: {'in-EVA assessment differed': 56, 'estimated risk fell on opposite sides of the gate': 56, 'post-abort crew reassessment': 36}

### Decision profile per strategy (per emergency)

| strategy | launches | aborts | retries after abort | work hours credited | hold/wait decisions by rule |
|---|---|---|---|---|---|
| B | 1.56 | 0.51 | 0.30 | 1.26 | {'risk gate': 8058, 'post-abort crew reassessment': 3788, 'operational timing': 592, 'repair held after radiation abort': 88, 'forecast coverage': 32} |
| C | 1.57 | 0.54 | 0.24 | 1.25 | {'risk gate': 9230, 'post-abort crew reassessment': 6336, 'operational timing': 610, 'post-EVA review hold': 278, 'repair held after radiation abort': 94, 'forecast coverage': 48, 'other': 4} |
| D | 1.69 | 0.61 | 0.29 | 1.35 | {'risk gate': 9422, 'post-abort crew reassessment': 7704, 'operational timing': 604, 'repair held after radiation abort': 118, 'forecast coverage': 42, 'post-EVA review hold': 18, 'other': 4} |
