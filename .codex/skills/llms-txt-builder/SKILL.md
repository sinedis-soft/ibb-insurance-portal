---
name: llms-txt-builder
description: Build, update, and audit llms.txt files and Markdown AI-readable page versions for SEO/AI Search websites. Use when the task mentions llms.txt, AI Search, LLM-readable content, Markdown versions of pages, AI crawlers, ChatGPT Search, Perplexity, Claude, Gemini, AI optimization for a website, or when a core article/page is added, removed, renamed, or substantially updated.
---

# llms.txt Builder

## Role

Act as an SEO-aware technical content engineer. Create, update, and audit `llms.txt` and optional AI-readable Markdown page versions so AI search systems can understand the website accurately, concisely, and safely.

Do not write marketing copy. Prefer exact, restrained, factual language.

## When to use

Use this skill when a task involves:

- `llms.txt`, AI Search, LLM-readable content, Markdown page versions, AI crawlers, ChatGPT Search, Perplexity, Claude, Gemini, or AI optimization;
- a new core product, service, landing, legal, contact, locale, or article route;
- a renamed, removed, or substantially changed article/page that may alter site meaning, canonical routes, product conditions, legal disclaimers, or sitemap priorities.

Minor copy edits do not require a `llms.txt` update unless they change products, geography, legal limitations, route structure, or authoritative page priorities.

## Preferred files

For Next.js and most static websites, prefer:

```text
public/llms.txt
```

Expose it at:

```text
https://example.com/llms.txt
```

Do not place `llms.txt` in `app/`, `pages/`, or `src/` unless the project intentionally generates it dynamically. For multilingual sites, start with one root `public/llms.txt`; add localized versions only when the routing/static-file strategy already supports them.

If Markdown page versions are explicitly requested and safe to expose, the llmstxt.org proposal prefers a clean Markdown version at the same URL as the source page with `.md` appended:

```text
https://example.com/path/page.html.md
https://example.com/path/index.html.md
```

For URLs without file names, append `index.html.md`. Use a separate pattern such as `public/ai-pages/<locale>-<slug>.md` only when the site's framework cannot safely serve same-URL `.md` versions; treat that as a project-specific fallback, not the llmstxt.org default.

Do not create `.md` versions that expose drafts, private routes, or misleading/broken URLs.

## What belongs in llms.txt

`llms.txt` explains site meaning and priorities. It is not a crawler-control file or a sitemap dump.

- `robots.txt`: crawler access.
- `sitemap.xml`: indexable URL list.
- `llms.txt`: factual AI-readable guide to the site, products, important pages, limitations, and authoritative sources.

Follow the llmstxt.org order:

1. Optional byte-order mark.
2. H1 with the project/site name. This is the only required section.
3. Optional blockquote summary with key context.
4. Optional Markdown content without headings for additional interpretation notes.
5. Optional H2 sections. Each H2 section must be a file list: Markdown bullets with a required hyperlink and optional `: notes`.

Use `## Optional` only for secondary URLs that can be skipped when a shorter context is needed.

Usually use this shape:

```markdown
# Site or brand name

> One short factual description of the site.

One or two short paragraphs about the website, audience, geography, and main subject matter.

Important limitations:

- Limitation one.
- Limitation two.

Key topics:

- Topic one.
- Topic two.

## Main pages

- [Page title](https://example.com/page.md): short factual explanation.

## Articles

- [Article title](https://example.com/article.html.md): short factual explanation.

## Contact or authority pages

- [Contact](https://example.com/contact.md): official contact page.

## Optional

- [Secondary page](https://example.com/secondary.md): useful but skippable detail.
```

The H1 is mandatory. The blockquote after H1 is recommended. Do not put non-link bullet lists under H2 headings; keep limitations and topical notes in the pre-H2 freeform Markdown area. Keep the file concise; 100-350 lines is usually enough.

## Language policy

Use English by default for the root file because many AI systems handle English technical summaries consistently. Preserve original localized page titles and legal/product names when translating would distort meaning. For IBB Portal, keep Russian and Georgian context visible and link to every implemented public locale where applicable.

## Insurance guardrails

For insurance websites, always distinguish broker, agent, insurer, assistance company, policy, application, quote, coverage, liability insurance, medical insurance, and cargo insurance.

Do not imply:

- the site is the insurer unless repository content confirms it;
- guaranteed issuance, guaranteed acceptance, or guaranteed coverage;
- one policy covers an entire international route;
- motor liability insurance covers own vehicle damage, medical treatment, cargo, fines, downtime, evacuation, or all travel risks unless the page explicitly says so.

For international motor insurance, note that requirements can depend on vehicle registration country, route, destination, dates, driver/client status, and current border or regulatory rules.

## Build/update workflow

1. Inspect project structure and SEO files:

```bash
find . -maxdepth 3 -type f | sort | head -200
find public app pages src -iname '*sitemap*' -o -iname '*robots*' 2>/dev/null
```

2. Identify framework, routes, domain, locales, content sources, sitemap generation, robots rules, canonical helpers, and metadata.
3. Map vertical and horizontal project relationships before choosing links.
4. Read only relevant home, product, landing, article index, key article, contact, about, legal, sitemap, and route files.
5. Decide whether linked URLs should point to clean Markdown page versions. Prefer same-URL `.md` links when the project serves them correctly; otherwise link to the canonical HTML pages and note the limitation if needed.
6. Draft or update `public/llms.txt` with only stable and important pages. Do not include every blog post unless the site is small or the article is strategically important.
7. Keep all H2 sections as file lists with linked URLs. Put general topics, warnings, and insurance limitations before the first H2.
8. Use absolute production URLs. Do not use localhost, staging URLs, unpublished routes, private admin URLs, CRM URLs, Bitrix webhooks, payment URLs with tokens, secrets, or personal data.
9. Check that wording is factual, concise, legally careful, and not a sales landing page.
10. Ensure sitemap, robots, canonical structure, and `llms.txt` do not contradict each other.
11. Run available checks from `package.json` where practical, such as `npm run lint`, `npx tsc --noEmit`, or `npm run build`.

## Project relationship analysis

Before adding or updating `llms.txt`, identify both vertical and horizontal relationships. This prevents the file from becoming a random URL list and helps AI systems understand site hierarchy.

### Vertical relationships

Vertical relationships are hierarchy, ownership, and canonical authority:

- root domain -> locale routes -> section/page -> article/detail page;
- language variants and hreflang/canonical equivalents;
- sitemap priorities, robots visibility, and metadata authority;
- product families -> product pages -> calculators/forms -> legal limitations;
- blog index -> article pages -> author pages -> article metadata;
- policy/legal pages that constrain product or marketing claims.

For an insurance portal, expect the main vertical chain to be similar to:

```text
production-domain
  locale routes, when implemented
    home
    products
    applications or lead form
    blog or knowledge base, when present
    contacts
    about
    privacy and legal pages
```

Use the repository's sitemap, robots, SEO helpers, route files, and content files as the main sources for vertical authority.

### Horizontal relationships

Horizontal relationships are cross-links and peer-to-peer context:

- navigation links in header/footer and product directories;
- product-to-product links such as Green Card -> OSAGO Russia and OSAGO Russia -> Green Card;
- product pages -> contact/order/calculator anchors;
- article frontmatter relationships such as `requiredSlugs` and `nextSlugs`;
- related-article blocks, author article lists, RSS, breadcrumbs, and JSON-LD references;
- localized equivalents across implemented locales;
- trust/legal links from product pages to privacy, regulation, contact, and about pages.

When a changed page has many horizontal links, include it in `llms.txt` only if it is authoritative for a core topic. Otherwise, prefer its parent product/category page and mention the topic in pre-H2 context.

### Link selection rule

Choose links for `llms.txt` in this order:

1. Vertical authority pages: homepage, product pages, main product directory, contact/about/legal pages, blog index.
2. High-value evergreen articles that explain major routes, documents, or insurance limitations.
3. Horizontal support pages only when they add necessary context not already covered by a vertical authority page.
4. `## Optional` for secondary but useful pages that can be skipped when context is short.

Do not select links only because they appear frequently in navigation or CTAs. Select them because they are authoritative for site meaning.

## Auto-update expectation for page/article work

When another skill or task adds, removes, renames, or substantially updates a page or article, treat `public/llms.txt` as part of the SEO maintenance checklist:

- update it immediately if the changed page is a core product, service, landing, legal/contact/about page, locale entry point, or high-value evergreen article;
- update it if product conditions, route/geography, limitations, disclaimers, canonical URLs, or sitemap priorities changed;
- skip it for minor wording edits and ordinary blog posts that do not affect site-level priorities, but mention the decision in the final summary when relevant.

## Markdown page versions

If requested, create clean `.md` versions only for important public pages. The llmstxt.org convention is to expose them at the same URL with `.md` appended, for example:

- `/docs/page.html` -> `/docs/page.html.md`
- `/docs/` -> `/docs/index.html.md`

Use:

```markdown
# Page title

Canonical URL: https://example.com/page
Language: ru
Last updated: YYYY-MM-DD

Short factual summary.

## Main content

Clean page content without navigation, footer, scripts, cookie banners, or repeated CTA noise.

## Important limitations

- Limitation one.
```

Convert visible CTA content into short factual text and links; do not paste raw JSX.

## Validation checklist

Before finishing, verify:

- `public/llms.txt` exists when expected;
- it starts with exactly one H1;
- H2 sections contain file lists with Markdown links, not plain topic/limitation bullet lists;
- any `## Optional` section contains secondary links that can be skipped for shorter context;
- important links are absolute production URLs;
- Markdown page-version links use same-URL `.md` convention when the project supports it, or a documented fallback when it does not;
- no secrets, private routes, staging URLs, drafts, or personal data are included;
- no unrealistic legal, insurance, or commercial promises are included;
- listed important pages are not obviously `noindex`;
- robots does not block `/llms.txt`;
- deployment verification can use `curl -I https://example.com/llms.txt` and `curl https://example.com/llms.txt | head -40`.

## PR notes

When making a PR, summarize:

- whether `public/llms.txt` was added or updated;
- main product/page/article groups included;
- insurance/legal limitations included;
- checks run and assumptions about production domain/routes.
