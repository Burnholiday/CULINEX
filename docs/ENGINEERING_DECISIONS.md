CULINEX Import Engine – Engineering Decisions



Version: v1.7.0



This document records architectural decisions made during development of the CULINEX Import Engine.



Its purpose is to explain why decisions were made, not only what was implemented.



All future parser improvements should follow these principles.



Core Engineering Principles

1\. Accuracy over Recovery



The parser must never recover additional rows by inventing data.



A discarded row is preferable to an incorrect validated row.



Recovery is only acceptable when supported by deterministic evidence.



2\. Evidence before Implementation



Every parser improvement follows this workflow:



Investigate

↓

Collect benchmark evidence

↓

Group into repeated patterns

↓

Implement only universal fixes

↓

Benchmark

↓

Keep or revert



Single examples are never sufficient justification for new parser logic.



3\. Supplier Agnostic Design



Parser logic must never rely on supplier names, invoice layouts, or supplier-specific rules.



All improvements must generalize across invoices.



4\. Mathematical Validation is Sacred



The validation engine is the final authority.



No sprint may weaken:



validate\_invoice\_math()

strict validation

quantity × unit\_price validation

VAT validation



Parser intelligence may improve extraction but may never bypass mathematical validation.



Important Decisions

Sprint 17 – Adaptive Header Intelligence



Decision:



Adaptive header confidence was introduced.



Finding:



Header confidence improved header recognition.



Result:



Kept.



Sprint 18 – Table Boundary Framework



Decision:



Built a geometry framework.



Finding:



Framework completed but parser integration caused regressions.



Result:



Framework retained but parser integration reverted.



Sprint 19 – Extraction Reliability



Decision:



Fix parser crashes before improving recovery.



Finding:



Metadata values (column\_confidence) were incorrectly treated as OCR cells.



Result:



Universal defensive fix implemented.



Outcome:



Extraction errors reduced to zero.



Sprint 20 – Sparse OCR Recovery Investigation



Three recovery strategies were investigated.



Decimal Repair



Finding:



Only one invoice safely demonstrated decimal corruption.



Decision:



Not enough evidence.



Result:



Rejected.



Adjacent Fragment Merge



Finding:



No universally safe fragment merges.



Decision:



Rejected.



Multi-product Segmentation



Finding:



Merged OCR rows required inference.



Decision:



Rejected.



Sprint 21 – Geometry Shadow Mode



Decision:



Run geometry without affecting extraction.



Finding:



Geometry framework works correctly.



Confidence scores do not correlate with parser success.



Result:



Shadow mode retained.



Integration postponed.



Current Engineering Philosophy



Future work should prioritize:



Better confidence calibration

Better diagnostics

Better geometry understanding



Future work should avoid:



Guessing values

Borrowing neighbouring totals

Supplier-specific heuristics

Lowering validation thresholds

Definition of Success



A sprint is successful when one of the following occurs:



Benchmark improves without regression.

Unsafe ideas are disproven through evidence.

The parser becomes more reliable.

New diagnostics improve understanding.



Not every sprint needs to increase validated rows.



Preventing unsafe implementations is considered successful engineering.

