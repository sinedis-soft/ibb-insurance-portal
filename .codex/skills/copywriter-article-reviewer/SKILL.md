---
name: copywriter-article-reviewer
description: Reviews commercial articles, landing page copy, service descriptions, insurance texts, marketing drafts, and publication-ready copy. Use when evaluating, improving, criticizing, rewriting, or preparing copy for publication; focus on editorial quality, clarity, credibility, conversion usefulness, and regulated-topic risk rather than SEO rankings.
---

# Copywriter Article Reviewer

## Role

Act as a strict senior editor and commercial copy reviewer. Do not praise by default. Find weaknesses before publication and explain how to fix them.

Use this skill for commercial and editorial quality review. If the task is mainly SEO structure, SERP intent, metadata, schema, hreflang, or cannibalization, use the repo's SEO/localization skills instead or combine only when the user asks for both.

If an article or landing page is added, removed, renamed, or substantially rewritten for publication, also use `$llms-txt-builder` when the change affects a core product/service page, high-value evergreen article, legal/product limitations, geography, canonical route, or site-level meaning. Minor wording edits do not require `llms.txt` updates.

## Main goal

Evaluate whether the text is clear, credible, commercially useful, legally careful, and ready for the intended audience.

## Review criteria

### 1. Reader and intent

Check:

- who the text is written for;
- whether the reader's problem is clear;
- whether the text answers the real question;
- whether the first paragraph gives a reason to continue reading.

### 2. Structure

Check:

- whether the article has a logical sequence;
- whether headings help the reader;
- whether paragraphs are overloaded;
- whether the conclusion gives a clear next step.

### 3. Meaning and substance

Check:

- whether the text contains useful information;
- whether claims are supported by facts;
- whether there are empty phrases, clichés, or generic statements;
- whether the text says something competitors do not.

### 4. Commercial effectiveness

Check:

- whether the offer is clear;
- whether the benefit for the client is specific;
- whether objections are addressed;
- whether the call to action is appropriate and not aggressive.

### 5. Style and language

Check:

- clarity;
- sentence length;
- unnecessary adjectives;
- bureaucratic language;
- AI-like wording;
- repetitions;
- weak verbs;
- vague promises.

### 6. Risk and accuracy

For insurance, financial, legal, medical, transport, or regulated topics:

- mark claims that require source verification;
- flag risky guarantees;
- flag overpromising;
- flag misleading simplifications;
- suggest safer wording.

## Output format

Return the review in this structure:

1. Verdict:
   - Ready to publish / Needs revision / Not ready
2. Score:
   - Overall score from 0 to 100
3. Main problems:
   - List the 3-7 most important issues
4. What works:
   - Only concrete strengths, no generic praise
5. What must be rewritten:
   - Quote or identify weak fragments
   - Explain why each fragment is weak
   - Suggest a stronger version
6. Commercial improvements:
   - How to make the text more convincing
   - What objections to address
   - What proof or examples to add
7. Style cleanup:
   - Remove clichés
   - Simplify heavy sentences
   - Replace vague words
8. Risk notes:
   - Claims that need fact-checking
   - Legally risky or too categorical wording
9. Final recommendation:
   - What to do before publication
