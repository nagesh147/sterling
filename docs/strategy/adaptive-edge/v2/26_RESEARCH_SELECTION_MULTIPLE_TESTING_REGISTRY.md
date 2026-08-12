# Adaptive Edge V2 — Research Selection / Multiple-Testing Registry Contract

**Artifact:** A50  
**Version:** 2.0.0-draft  
**Status:** FRAMEWORK / PARTIALLY-BLOCKED  
**Depends on:** A39, A47, A48, A49

## 1. Purpose

A50 records the full research candidate population and the selection process used to identify a candidate for later evaluation or promotion.

The purpose is to prevent a reported winner from being detached from the search process that produced it.

A50 does not select a multiple-testing correction, significance threshold, confidence level, promotion threshold, or economic acceptance rule.

## 2. Canonical research population

Every evaluated candidate is preserved as an auditable record containing:

```text
candidate_id
 evaluation_id
 code/version
 feature version
 label version
 execution version
 parameter fingerprint
 result fingerprint
 test-use state
 selection-influence state
```

Failed candidates are retained. They must not be deleted because they performed poorly.

## 3. Candidate identity

`candidate_id` must uniquely identify one candidate within an evaluation population.

A duplicate candidate identifier is invalid because it makes the research population ambiguous.

## 4. Selection population

The registry must represent the complete population supplied to the selection process:

```text
C = {c1, c2, ..., cN}
SelectedCandidate = SelectionFunction(C, ResearchPolicy)
```

A winner without its candidate population is insufficient evidence of a research result.

## 5. Selection decision

A selection decision records:

```text
selected candidate
selection policy identifier
selection rationale
selection decision version
```

The selected candidate must exist in the recorded candidate population.

## 6. Multiple testing

Testing many candidates increases the opportunity to observe favorable results by chance.

A50 therefore preserves the candidate population and its result lineage so that a later statistical artifact can account for the research-selection process.

A50 does not invent the correction method.

Possible future methods may include multiplicity adjustment, resampling, nested evaluation, or other methods justified by the final statistical design, but no method is selected here.

## 7. Validation versus final test

Validation observations may participate in candidate selection and tuning according to A39.

The final test must remain protected from selection influence.

If a test observation is inspected and its result influences candidate, parameter, model, policy, or execution selection, that test evidence is contaminated.

## 8. Test-use registry

The candidate record therefore distinguishes:

```text
test_observed
selection_influenced
```

The combination:

```text
test_observed = true
selection_influenced = true
```

makes the final test population ineligible as an untouched final-test claim without an appropriately reconstituted evaluation boundary.

## 9. No retroactive cleanup

A contaminated test observation must not be made valid by deleting the candidate or deleting the selection record.

The contamination is part of the research history.

## 10. Candidate lineage

Each candidate must remain linked to the exact versions used to produce its result:

```text
code_version
feature_version
label_version
execution_version
parameter_fingerprint
result_fingerprint
```

This prevents two candidates with superficially identical names from being treated as the same research object.

## 11. Deterministic registry identity

The registry fingerprint is derived from a canonical representation of the candidate population and selection decision.

Equivalent populations represented in different insertion order must produce the same fingerprint.

## 12. Relationship to A47

A47 determines whether OOS evidence can support a protected claim based on test-use history.

A50 supplies the research-selection population needed to establish whether the candidate was selected after observing test evidence.

A50 does not replace A47.

## 13. Relationship to A48

A48 preserves cycle-level evaluation evidence.

A50 preserves candidate-level research population and selection lineage.

Both are required:

```text
A48: what happened in each evaluation cycle
A50: what candidates were searched and how one was selected
```

## 14. Relationship to A49

A49 records the dependence structure required before uncertainty estimation.

A50 records the selection process that can create research-selection bias.

Neither artifact chooses the final statistical correction independently of the unresolved evaluation design.

## 15. Frozen architecture

The following are frozen:

```text
candidate preservation
candidate identity
selection decision lineage
test-use recording
selection-influence recording
version lineage
deterministic registry identity
negative-result preservation
```

## 16. Unresolved

```text
multiple-testing correction
family-wise error policy
false-discovery policy
selection-adjusted confidence procedure
nested-CV policy
research stopping rule
promotion threshold
```

These require a later statistical/economic specification.

## 17. Completion criterion

A50 is resolved when every research candidate can be reconstructed from its source/version lineage, the complete candidate population is preserved, every selection decision is auditable, and any test observation that influenced selection is permanently identifiable as contaminated.

## 18. Governing rule

```text
Never report only the winner.
Preserve the search that produced the winner.
```
