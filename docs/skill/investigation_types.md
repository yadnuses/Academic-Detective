## Special Investigation Types

The framework has been validated against three anonymized case studies representing distinct patterns. The following 12 investigation types map to the 7-step framework:

| Type | Focus | Key Checks | Typical Pattern |
|:---|:---|:---|:---|
| 1. Credential Fraud & Inflation | Stated vs. verifiable academic achievements | Paper counts, monograph verification, CV timeline gaps | +40% inflation in claimed paper counts; visiting scholar misrepresented as postdoc |
| 2. Plagiarism | Unauthorized use of others' work or ideas | Text duplication rates, side-by-side comparison, translated-as-original claims | High similarity without attribution; core chapters lack originality markers |
| 3. Data & Image Fabrication | Falsified or manipulated research data/images | Repeated images across papers, impossible statistics, unavailable raw data | Identical gel bands in unrelated experiments; stats contradict sample size |
| 4. Duplicate Publication / Salami Slicing | Same results split or republished across outlets | Dissertation-monograph overlap, bilingual duplication, fragmented outputs | 1 dissertation → 7+ derivative publications; overlap <5% with original thesis |
| 5. Paper Mill & Authorship Commerce | Commercial acquisition of papers or authorship slots | Tortured phrases, ultra-fast acceptance, topic-author mismatch | Nonsensical synonym-swapped phrases; acceptance within days |
| 6. Authorship Corruption | Author credits not matching actual contribution | First-author dominance by mentor, ghost writers, bought authorship | Mentor claims first authorship on all student work with no verifiable contribution |
| 7. Peer Review Manipulation | Improper influence on peer review outcomes | Fake reviewer emails, coercive citations, editorial collusion | Authors review own papers via false email domains; editors demand self-citations |
| 8. Dependency Pattern | Over-reliance on advisor/leader networks for publications and promotion | Co-author concentration with one superior, promotion gaps, absent independent mentorship | 15+ years without promotion yet continuous top-tier papers with same leader |
| 9. Academic Clique & Citation Manipulation | Monopolistic control of resources and metric gaming | Citation cartels, coercive citations, nepotism in evaluation | Mutual citation rates >30% within closed circle; evaluation manipulation via guanxi |
| 10. Grant Fraud & Financial Misconduct | Misuse, embezzlement, or fraudulent use of research funds | Abnormal reimbursements, related-party transactions, deliverable mismatches | 1,500 one-way train tickets to same city; funds channeled to family companies |
| 11. Conflict of Interest Concealment | Failure to disclose relationships that could bias research | Corporate funding with one-sided conclusions, undisclosed equity, undisclosed familial reviewing | Study conclusions systematically favor sponsor; reviewer fails to recuse on friends' papers |
| 12. Research Ethics Violations | Violations of human/animal/data protection norms | Missing IRB approval, unauthorized sensitive data, animal welfare breaches | Clinical trials without informed consent; 3R principles ignored in animal studies |
| 13. Ghost Writing & AI-Assisted Authorship | Suspected use of ghost writers or AI-generated content without disclosure | Stylometric consistency, AIGC statistical features, translation plagiarism, capability consistency | Sudden style rupture in a paper; perplexity/Burstiness scores matching AI patterns; author lacks training for methods used in the paper |

### International-Specific Investigation Types

The following patterns are primarily observed in **international academic contexts** (foreign graduate advisors, overseas scholars):

| Type | Focus | Key Checks | Typical Pattern | Detection Rule |
|:---|:---|:---|:---|:---|
| I01. Predatory Journal Publishing | Papers published in journals with rapid publication + high APC + low selectivity | Publisher name (Frontiers/MDPI/Hindawi), journal name patterns, OA ratio | >3 papers in Frontiers/MDPI journals with no Q1/Q2 publications | `international/heuristics_classifier.py` |
| I02. Paper Mill Patterns | Template-title papers, ghost author sets, rapid publication clusters | Title generalization with `{WORD} for {DISEASE}`, same ghost authors across papers, >8 papers/year | "Machine Learning for X Disease" series with identical structure; author overlap >80% | `international/heuristics_classifier.py` |
| I03. Image Manipulation | Duplicated/blurred/modified figures across papers | Gel band reuse, impossible statistics, figure overlay | Identical Western blot bands in unrelated experiments | Manual visual inspection + PubPeer comments |
| I04. Citation Cartel | Self-citation rings or reciprocal citation clusters | Self-citation ratio, mutual citation within closed group | Self-citation >30%; mutual citation >30% within 3-author circle | `international/heuristics_classifier.py` + `citation_profiler.py` |
| I05. P-hacking / Data Fabrication | Pressure to produce significant results; manipulated data | P-value distribution, impossible statistics, raw data unavailability | All p-values clustered at 0.049; effect sizes inconsistent with sample size | Statistical audit + `common_heuristics.py` |
| I06. Ghost Authorship | Author lists exceed actual contribution; honorary authorship | Author count vs. contribution, >20 authors in non-big-science fields | 25+ author papers in CS without CERN/LHC-type collaboration | `international/heuristics_classifier.py` |
| I07. Rapid Publication | Unusually high publication velocity in short time windows | Papers per month, batch submissions | 5+ papers in a single month; acceptance within days of submission | `international/heuristics_classifier.py` |
| I08. Ghost Writing & AI-Assisted Authorship | Suspected use of ghost writers or undisclosed AI tools | Stylometric drift, AIGC perplexity/Burstiness, file metadata anomalies, capability mismatch | Author's writing style suddenly shifts; paper contains methods beyond author's known training; file creation timestamps suggest ultra-rapid composition | `stylometry_profiler.py` + `aigc_statistical_profiler.py` + `capability_consistency_checker.py` |

**International evaluation benchmarks** (discipline-specific):
- **STEM tenure-track (R1)**: 15+ papers, 8+ first-author, 3+ Q1, h-index ≥12 at year 6
- **Humanities tenure-track (liberal arts)**: 6+ papers, 3+ first-author, 1+ Q1, h-index ≥5 at year 6
- See `scripts/evaluation_baselines.md` for full benchmarks by discipline and institution tier.

## Case Studies

Three foundational anonymized case studies demonstrating methodology:

1. **Case A** (华东某师范大学): "Salami slicing" pattern — one dissertation fragmented into 7+ publications
2. **Case B** (华东某师范大学): "Credential inflation" pattern — claimed paper counts exceeded verified counts by ~44%
3. **Case C** (北京某国家级研究机构): "Dependency" pattern — 16-year promotion stagnation coupled with leader-dependent top-tier publications

---

