# APEX-v1-extended — structure of the benchmark

> **Read this if you're asking:** "What kinds of tasks does the
> Consulting domain test? What does task 1588 ask? Which domain has the
> heaviest attachments? Should I pilot on Consulting or Legal?"
>
> **TL;DR:** per-domain task characterization, plus a full per-task
> index (task_id + first-sentence summary + attachment count + rubric
> size) for all 100 public tasks.

What follows is the *operational* picture of the 100 public dev tasks: how
they're split, what each domain actually tests, and a per-task index so you
can pick exactly which tasks to run.

## At a glance

- **One single CSV**: `data/APEX-v1-extended/data/train.csv`, 100 rows. There
  is no train/val/test split inside the public release. The 400-task heldout
  *test* set is private to Mercor (leaderboard submission only).
- **Domain is a column**, not a split. Four domains, exactly 25 tasks each:
  `Consulting`, `Finance`, `Legal`, `Medicine`.
- **Tasks are independent.** No state carries between them. Multiple runs of
  the same task are independent samples, not a curriculum.
- **Every task has attachments.** 176 unique files total — 132 PDFs, 42 CSVs,
  1 XLSX, 1 DOCX. Reducto handles all four formats; a PDF-only parser is
  insufficient.

## What each domain is testing

### Consulting (25 tasks)

**Skill tested:** quantitative business-strategy analysis on a single CSV.
Tasks read like McKinsey/Bain case prompts: "we have data, compute these
metrics, then make a recommendation."

- **Inputs:** 28 CSVs, 1 PDF across the 25 tasks (most tasks ship a single
  CSV).
- **Math:** Aggregations, percentages, ratios. Some tasks demand a specific
  rounding policy (e.g., "round to two decimals").
- **Output shape:** Numbers in named units (dollars, percent, counts) plus a
  short qualitative recommendation.
- **Rubric style:** Mostly numeric assertions with acceptable ranges, e.g.
  *"States the money freed up as $702,062.52 (acceptable $698,000–$705,000)"*.
  Some criteria are weight=`Primary objective(s)`; some are `Not primary
  objective` (they still count but the leaderboard weights them less).

### Finance (25 tasks)

**Skill tested:** investment-banking analytics. LBO models, DCF, M&A
purchase-price allocation, capital structure, securitization.

- **Inputs:** 24 PDFs, 14 CSVs, 1 XLSX. Some prompts reference real public
  filings (e.g., Nike's 2025 Form 10-K, Heineken's rating actions). Others
  ship a CSV "financial model" that the model is supposed to extend.
- **Math:** Multi-step DCF/IRR/MOIC math with intermediate values that the
  rubric checks one-by-one.
- **Output shape:** Numbers in specified units (USD millions, percentages,
  multiples), often dozens of them per task.
- **Rubric style:** Tight numeric acceptance ranges, e.g. *"calculates the
  Net IRR for LPs as 29.79% (acceptable 29.49%–30.09%)"*. Reading is on the
  hard end — rubrics here are 3.5k–28k characters with 6–15 criteria.

### Legal (25 tasks)

**Skill tested:** writing a legal opinion or analysis given a fact pattern,
citing statutes and case law from attached PDFs.

- **Inputs:** Pure PDFs. 1–9 PDFs per task; this is the heaviest-attachment
  domain. Median attachment payload ~430 KB, max 5.3 MB.
- **Documents:** Statutes (`FlaStat.319.30.pdf`), court opinions
  (`PEOPLE v. CROMER.pdf`), pattern jury instructions
  (`CACI-1801-1802.pdf`), federal regulations.
- **Output shape:** A legal memorandum: factual summary, analysis, conclusion,
  references to statute and case law. Some rubrics also check the
  jurisdiction the analysis was framed in.
- **Rubric style:** Mostly *qualitative* checks ("identifies the jurisdiction
  as Florida", "concludes that Libby will fail on her negligence claim"). One
  fact pattern can have a rubric of 8–25 criteria covering both the legal
  framework and the factual conclusion.

### Medicine (25 tasks)

**Skill tested:** clinical decision-making given a patient presentation and
a reference document (immunization schedule, pathology images, clinical
guidelines).

- **Inputs:** 26 PDFs, 1 DOCX. Most tasks have a single attached document.
- **Documents:** Patient history & physicals, pathology slides (as images
  embedded in PDFs — note these will be read as images by Reducto, not OCR
  to text), reference guidelines (AAP immunization schedule).
- **Output shape:** Diagnoses, treatment recommendations, classifications
  (e.g., "Forrest grade 2b"), specialty consultations to order.
- **Rubric style:** Mix of multiple-choice-style assertions
  ("Recommends consulting infectious disease") and named-grade outputs
  ("States that the first ulcer is Forrest grade 2b").
- **Notable: shortest prompts of any domain** (median 575 chars), highest
  rubric density.

---

## Per-domain median sizes

| Domain | Prompt chars (med) | Rubric chars (med) | Attachment MB (med) | Dominant file types |
|---|---:|---:|---:|:---|
| Consulting | 244 | 2,554 | 0.04 | `.csv` |
| Finance | 490 | 2,684 | 0.07 | `.pdf`, `.csv`, `.xlsx` |
| Legal | 349 | 2,707 | 0.43 | `.pdf` (heavy) |
| Medicine | 107 | 2,686 | 0.04 | `.pdf` |

---

## Picking and running a subset

Three independent filters, composable:

```bash
# Browse all tasks in one domain.
apex-bench list --domain Consulting

# Browse first 5 of two domains.
apex-bench list --domain Consulting --domain Medicine --limit 5

# Read one task end-to-end (prompt + rubric + attachment list).
apex-bench show 1588
```

For runs (once `apex-bench run` lands per `IMPLEMENTATION_PLAN.md` §3), the
same `--domain`, `--start-index`, `--limit` flags map straight through to
the upstream harness. Pick tasks either by index range or by listing IDs:

```bash
# Equivalent to DC2's --max-examples 5: first 5 Consulting tasks.
apex-bench run --domain Consulting --limit 5

# A specific subset by id (future flag).
apex-bench run --task-ids 1588,2108,2120
```

Project policy: **always one run per (task, model)**. There is no
`--runs-per-task` flag and there will not be one. See
`docs/REPRODUCIBILITY.md` for the rationale.

---

## Full per-task index

What follows is every task in the public split, grouped by domain and
sorted by `Task ID` ascending. Use the `Task ID` column to pick.

The "What it asks" column is the first sentence of each prompt, truncated to
~120 chars. For the full prompt, run `apex-bench show <task_id>`.

> **Numbers:** `Attach` = file count and extensions seen across this task's
> attachments. `Prompt chars` and `Rubric chars` are raw character counts —
> for tokens, multiply ~4× as a rough rule.

## Consulting

| Task ID | Attach | Prompt chars | Rubric chars | What it asks |
|---:|:---|---:|---:|:---|
| 145 | 1 (.csv) | 802 | 11456 | I'm making a plan for our client's next campaign cycle using the attached data, where Payment ($) is equivalent to the… |
| 283 | 1 (.csv) | 2300 | 13113 | Our client, a food delivery app focused on Mexican food, is requesting assistance using the enclosed dataset on all of… |
| 352 | 1 (.csv) | 1150 | 9513 | The COO of my client, an apparel e-commerce website, has raised questions about the high turnaround time reported by mu… |
| 772 | 1 (.csv) | 1689 | 10034 | A large consumer goods company is launching a new plant-based snack box. |
| 804 | 1 (.csv) | 1151 | 5370 | My client, Paw Prints, is a B2B manufacturer of digital pet portraits that is looking for an assessment of its producti… |
| 828 | 1 (.csv) | 1787 | 7956 | I'm working to optimize the distribution of marketing spend for my client for the next cycle to better fit their Family… |
| 1080 | 1 (.csv) | 1455 | 9570 | A US-based private medical practice business would like to understand the financial performance of the 'Offices of Phys… |
| 1091 | 1 (.csv) | 825 | 7575 | The Company operates in the Aerospace industry with focus on 4 categories: propulsion, materials, mechanics, and contro… |
| 1122 | 1 (.csv) | 682 | 5169 | The client is a fast-casual Mexican-style restaurant chain. |
| 1149 | 1 (.csv) | 2145 | 13047 | One View Bank is a European card issuer with 3 flagship cards: "One View Standard", "One View Premium", and "One View A… |
| 1150 | 1 (.csv) | 1317 | 17087 | Our client, a multi-specialty retailer called BudgetBuy, wants to launch a new promotional campaign focused on only one… |
| 1166 | 1 (.csv) | 1221 | 6487 | My client is a grocery chain based in the US that is trying to evaluate their scope 1 and scope 3 greenhouse gas (GHG)… |
| 1169 | 3 (.csv) | 1240 | 10004 | My client, a small airline company, is looking to expand its geographic reach. |
| 1170 | 1 (.csv) | 880 | 11475 | Our client, ABC Incorporation, manufactures spare parts for automobiles. |
| 1171 | 1 (.csv) | 1360 | 10757 | The attached file contains the data of a sedan manufacturing firm. |
| 1172 | 1 (.csv) | 1405 | 4629 | My client, a large toy company, wants to develop a new product to compete with Lego, focusing on the US market in 2032. |
| 1188 | 1 (.csv) | 1042 | 8945 | Our insurance carrier partner has entered into a PoC agreement with Scribe, a vendor that is utilizing generative AI to… |
| 1191 | 3 (.csv,.pdf) | 1276 | 16603 | A European supermarket chain is considering expanding into Africa and wants your help choosing the target countries usi… |
| 1192 | 1 (.csv) | 1861 | 13978 | The client is a big food delivery app that is analyzing merchant loyalty and performance in the Mexican food industry. |
| 1242 | 1 (.csv) | 1063 | 16734 | The CHRO of a multinational investment bank wants to determine which employee grade levels (M1, M2, M3, M4, M5) give th… |
| 1259 | 1 (.csv) | 1717 | 20583 | Our client is a health insurance payer in the US looking to reprice their insurance policy for this subset of existing… |
| 1265 | 1 (.csv) | 1461 | 13910 | Titan Capital Partners is preparing to launch a late-stage PE fund targeting high-growth unicorns and has asked our fir… |
| 1269 | 1 (.csv) | 1177 | 6573 | An international surfing company is planning on expanding into the USA and wants to begin by launching its surfboard pr… |
| 1288 | 1 (.csv) | 1494 | 7759 | Our Healthcare system client's internal analytics team is reporting strong performance from its CDI pilot, indicating b… |
| 1384 | 1 (.csv) | 1023 | 6022 | We want to optimize workforce deployment, compensation, and retention. |

## Finance

| Task ID | Attach | Prompt chars | Rubric chars | What it asks |
|---:|:---|---:|---:|:---|
| 1588 | 1 (.xlsx) | 1854 | 11101 | TPG is currently in conversations to acquire a wholesale distributor of HVAC supplies in Europe. |
| 2107 | 1 (.csv) | 1348 | 11053 | Mariner Cloud plc (acquirer) plans to acquire Orion Metrics AG (Target). |
| 2108 | 1 (.pdf) | 2092 | 3954 | Using Nike Inc's 2025 Form 10-K and the assumptions below, conduct a 3 year DCF analysis, and calculate: Nike's Enterpr… |
| 2120 | 2 (.pdf) | 922 | 7930 | To allocate funds to relatively low-risk investments while still achieving a decent return, refer to the 'S&P500' and '… |
| 2121 | 1 (.csv) | 1745 | 5512 | Investment Banking firm BLT is advising fund ART with a whole loan bid for a pool of reperforming ("RPL") and nonperfor… |
| 2145 | 2 (.pdf) | 1833 | 6205 | We are doing Discounted Cash Flow Analysis ("DCF") on Coupang (NYSE: CPNG) as they are a competitor to one of our clien… |
| 2157 | 1 (.csv) | 1923 | 8721 | A well-known U.S. |
| 2186 | 1 (.pdf) | 910 | 3560 | Produce an EV to Equity Bridge that would be used in a Locked Box Paper for a regulated, asset and wealth management co… |
| 2192 | 1 (.csv) | 1851 | 3552 | Italian bank UniCredit S.p.A. |
| 2205 | 1 (.csv) | 1042 | 4173 | On 08 October 2025, rating agency upgraded its rating on Dutch beer maker Heineken (Ticker: HEIANA) from BBB+ to A- by… |
| 2217 | 3 (.pdf) | 2283 | 11583 | Build a fully diluted market capitalization and an enterprise value valuation analysis for Coinbase. |
| 2228 | 1 (.csv) | 3263 | 5529 | A Real Estate Private Equity company (LP) is teaming up with a real estate developer to acquire a property for $25 mill… |
| 2230 | 1 (.csv) | 3169 | 9089 | Albion Technologies plc (a UK company, GBP as the functional currency) will acquire Horizone Sistemas S.A. |
| 2232 | 1 (.csv) | 4710 | 11159 | A developer (Operating Partner), along with a Private Equity firm (LP), wants to acquire a property for $25 million wit… |
| 2261 | 2 (.pdf) | 2425 | 11849 | As part of Lloyd's liquidity review in relation to a potential M&A transaction, you have been tasked with assessing the… |
| 2266 | 1 (.csv) | 617 | 3684 | A company is considered "efficient" if it has a waste recycled percentage greater than 45%. |
| 2269 | 1 (.pdf) | 3034 | 13235 | Hermion plc. |
| 2287 | 1 (.pdf) | 686 | 11074 | KatNip Co. |
| 2288 | 3 (.pdf) | 2500 | 13989 | Build a fully diluted market capitalization and an enterprise value valuation analysis for Ford Motor Company, excludin… |
| 2294 | 1 (.csv) | 2452 | 11398 | Borealis Components, Inc. |
| 2302 | 2 (.csv) | 3724 | 6843 | Prepare a five-year forecast of the company's balance sheet that will be used to perform a Free Cash Flow to Firm (FCFF… |
| 2308 | 1 (.csv) | 1497 | 11985 | An Equity Capital Markets (ECM) syndicate desk of a major investment bank is exploring a pro rata allocation or an allo… |
| 2315 | 1 (.csv) | 2845 | 16319 | The securitization capital markets team at SPO Capital has been actively working with rating agencies on an upcoming se… |
| 2317 | 5 (.pdf) | 1980 | 9799 | In June 2020, Telefonica Deutschland sold its portfolio of communication sites to Telxius. |
| 2333 | 3 (.pdf) | 3050 | 9199 | Objective: Assess whether a sponsor should pursue a Nasdaq Global Market IPO or a same-day underwritten Term Loan B (TL… |

## Legal

| Task ID | Attach | Prompt chars | Rubric chars | What it asks |
|---:|:---|---:|---:|:---|
| 13 | 5 (.pdf) | 1901 | 12062 | Our client, Alex Jones, was involved in an automobile collision on July 15, 2025. |
| 845 | 4 (.pdf) | 3027 | 12292 | A renowned art collective calling themselves "The Roamers" has been touring the country with a pop-up art exhibit calle… |
| 942 | 1 (.pdf) | 1061 | 8604 | On January 11th, 2025, in Compton, California, Christy Rothschild, aged 24, was babysitting Jontae Rodriguez, aged 15. |
| 1022 | 4 (.pdf) | 2714 | 16658 | Our client has been arrested and charged in connection with a series of thefts at a gas station where he works. |
| 1031 | 6 (.pdf) | 757 | 9609 | A defendant was arrested in Puerto Rico and charged with illegal possession of a firearm and ammunition as a felon, in… |
| 1041 | 2 (.pdf) | 608 | 9596 | John was a member of the Navajo Nation. |
| 1078 | 6 (.pdf) | 1594 | 7531 | Steven Smith was driving on Route 53 in Indianapolis, Indiana on June 28, 2025. |
| 1148 | 2 (.pdf) | 754 | 16660 | Frank Bader is a claimant for Social Security Disability Insurance benefits. |
| 1167 | 1 (.pdf) | 1241 | 7872 | Mr. (case study with a single referenced opinion; see full prompt) |
| 1184 | 5 (.pdf) | 2595 | 9738 | The US Environmental Protection Agency (EPA) is conducting a remedial action under the Comprehensive Environmental Resp… |
| 1189 | 1 (.pdf) | 887 | 12357 | Chen operates an immigration consulting firm in California through an LLC. |
| 1226 | 8 (.pdf) | 1851 | 11057 | The client is a Virginia logistics and packaging company ("Company") that specializes in designing and manufacturing cu… |
| 1230 | 3 (.pdf) | 5239 | 10277 | Our client, Homes, a large international residential property ownership group, has come to us seeking advice. |
| 1246 | 8 (.pdf) | 2349 | 14698 | Erika lives with her roommate and their two dogs in a condo next to a community park owned by the local parks district… |
| 1318 | 1 (.pdf) | 991 | 13448 | Jenn Castro has been one of the firm's clients for Supplemental Security Income (SSI) benefits since September 2023 whe… |
| 1319 | 1 (.pdf) | 2013 | 10810 | The client is a Virginia-based sanitation services contractor ("Company") that provides portable restroom and hand-wash… |
| 1323 | 1 (.pdf) | 2751 | 20231 | On October 20, 2025, in Vista, California, Beatrice Restrepo, aged 21, parked in front of the apartment complex where h… |
| 1346 | 1 (.pdf) | 1196 | 28369 | On October 19th, 2024, our client, Gerald Jefferson, aged 54, was found guilty of a violation of Penal Code (PC) sectio… |
| 1361 | 1 (.pdf) | 2247 | 19212 | Our client, BackUp, is a boutique IT services firm specializing in backup and disaster recovery. |
| 1366 | 9 (.pdf) | 2152 | 10734 | Angela Brown was driving home from college on July 5, 2025 in Andover, Connecticut, when her vehicle was struck by a se… |
| 1367 | 1 (.pdf) | 2131 | 16494 | The client is a Virginia biotechnology company ("Company") that develops proprietary hemp seed genetics used in produci… |
| 1371 | 5 (.pdf) | 1952 | 17185 | On May 23, 2025, at about 3:40 p.m., Jim, carrying a black handgun, entered the front door of a Wells Fargo Bank in Ric… |
| 1382 | 1 (.pdf) | 744 | 8837 | Belgium and Spain are both Contracting Parties to the attached "Convention on Conduct of Fishing Operations in the Nort… |
| 1398 | 2 (.pdf) | 1010 | 12030 | Lily Strum is a potential client with a pending claim for Social Security Disability Insurance (SSDI) Benefits. |
| 1757 | 2 (.pdf) | 684 | 8350 | Berry met with his attorney in 2015 and executed two wills. |

## Medicine

| Task ID | Attach | Prompt chars | Rubric chars | What it asks |
|---:|:---|---:|---:|:---|
| 1155 | 1 (.pdf) | 1252 | 5890 | Note: For the following clinical scenario, please refer to the most up to date American Academy of Pediatrics Immunizat… |
| 1340 | 1 (.pdf) | 479 | 10080 | A middle-aged man presents to the ER with abdominal pain and fever. |
| 1344 | 1 (.pdf) | 411 | 7271 | During an esophagogastroduodenoscopy (EGD), the endoscopist—accompanied by a medical student—describes two gastric ulce… |
| 1345 | 1 (.pdf) | 254 | 18714 | A patient presents with right lower extremity pain as described in the attached history and physical (1345_historyAndPh… |
| 1352 | 1 (.pdf) | 407 | 8886 | A patient recently underwent a prostate MRI that is still pending formal reporting. |
| 1354 | 1 (.pdf) | 901 | 12111 | An 18-year-old male presents with chronic fatigue, muscle cramps, and intermittent perioral tingling one year after und… |
| 1359 | 2 (.pdf) | 549 | 13678 | For the following clinical scenario, please refer to the attached documents: American Academy of Pediatrics (AAP) immun… |
| 1368 | 1 (.pdf) | 373 | 9577 | A 75-year-old male patient presents to the primary care clinic for new onset skin dryness and pruritus. |
| 1389 | 1 (.pdf) | 841 | 11888 | A 66-year-old man with history of hypertension presents to clinic for follow up after a witnessed syncopal episode whil… |
| 1407 | 1 (.docx) | 222 | 9901 | A patient whose medical information is in the attached document comes to your clinic. |
| 1415 | 1 (.pdf) | 946 | 9458 | A 45-year-old man presents with 4 weeks of non-bloody, watery diarrhea, occurring 4 to 5 times daily. |
| 1426 | 1 (.pdf) | 1401 | 12118 | A 32-year-old woman from Puerto Rico with a history of systemic lupus erythematosus (previously treated with hydroxychl… |
| 1431 | 1 (.pdf) | 999 | 9922 | Note: Please refer to the attached document, Patient info for task 1431.pdf to answer this task. |
| 1436 | 1 (.pdf) | 197 | 12307 | Note: refer to the attached General Practitioner (GP) home visit document for the following task. |
| 1439 | 1 (.pdf) | 461 | 21454 | A 7-year-old male with asthma comes to the clinic to recheck his asthma. |
| 1452 | 1 (.pdf) | 1092 | 5973 | A 37-year-old farmer presents to the clinic for management of seborrheic dermatitis. |
| 1476 | 1 (.pdf) | 886 | 18549 | An 8-year-old female presents to a pediatric clinic with concerns of a possible UTI. |
| 1477 | 1 (.pdf) | 383 | 21306 | Hematoxylin and Eosin (H&E) sections of a brain tumour from a 48-year-old man are submitted for pathological examinatio… |
| 1481 | 2 (.pdf) | 842 | 16283 | A CSF sample is sent to you from a 59-year-old man with a 4-month history of metastatic lung adenocarcinoma. |
| 1494 | 1 (.pdf) | 543 | 13380 | A 45-year-old male with psoriasis was getting a knee injection at his orthopedic office. |
| 1495 | 1 (.pdf) | 323 | 17580 | A 5-year-old previously healthy male is admitted to the hospital. |
| 1501 | 1 (.pdf) | 835 | 10366 | A 58-year-old woman with invasive ductal carcinoma of the right breast undergoes planned breast-conserving surgery (lum… |
| 1508 | 1 (.pdf) | 300 | 5743 | A 30-year-old female is brought in by paramedics for a suicide attempt. |
| 1513 | 1 (.pdf) | 1309 | 13736 | Note: For the following clinical scenario, refer to the latest and most appropriate clinical practice guidelines as of… |
| 1555 | 1 (.pdf) | 1406 | 17972 | Charles is a 63-year-old man with a past medical history of hypertension, type 2 diabetes, and hyperlipidemia who prese… |

---

## Picking tasks well

Some opinionated guidance from a research-budget point of view:

- **Cheapest domain to run:** **Consulting** — short prompts, single-file
  CSV attachments, small total payload. Median Consulting task likely costs
  <$0.05 to run on a frontier model + Opus 4.6 judge.
- **Most expensive domain to run:** **Legal** — 1–9 PDFs, median attachment
  payload ~430 KB, max 5.3 MB. A single heavy Legal task can run 30–50× the
  cost of a typical Consulting task because parsed attachment text dominates
  input tokens.
- **Best domain to *start* a smoke run on:** Consulting. Lowest variance,
  fastest, cheapest. If a Consulting smoke fails, the failure isn't because
  the input is huge — it's because the pipeline is broken.
- **Medicine** is interesting because rubric chars are large but prompt
  chars are *very* small — the model has to retrieve clinical reasoning from
  the attached patient docs, not from the prompt. This is a good
  attention/retrieval probe.
- **Legal** is the domain where DC's accumulated cheatsheet has the highest
  upside, in principle: each Legal task is a self-contained legal question
  with statutes the model has seen variations of in earlier Legal tasks. A
  cheatsheet that captures, e.g., "in Florida property-damage diminished-value
  claims, the controlling case is X" would transfer to other Florida-tort
  Legal tasks. This is worth designing the curriculum around when we get to
  Phase 4 of `IMPLEMENTATION_PLAN.md`.
