# XHS Digest Agent Notes

This folder stores the first draft of the Xiaohongshu AI digest agent rules.

Files:

- `xhs-digest-agent.rules.yaml`: structured rules for sources, ranking, summary, and output.
- `xhs_auth_refresh.py`: local auth health-check and refresh entrypoint for Spider_XHS.

Current defaults:

- Digest tone: `AI产品情报`
- Delivery window: `evening`
- Output: local Markdown report
- Future notifier: Feishu card
- Data collection base: `Spider_XHS`

Current open items for later:

- Add the rest of the followed accounts if needed
- Refine "快速略过" criteria from real usage
- Confirm the exact evening schedule time
- Decide whether watch authors should be included by default or only when high-signal
- Replace manual cookie refresh with Spider_XHS built-in login flow
- Add a cookie health check that triggers re-login when selfinfo/search endpoints expire

Optimization backlog for later:

- Improve one-line summary quality so outputs feel more like conclusions than compressed titles
- Refine the "其余值得看" section to reduce weakly related posts
- Improve summary truncation so lines end naturally instead of cutting mid-thought
- Add better topic-tag inference so tags feel controlled and readable
- Add clearer distinction between "最推荐" summary tone and "其余值得看" summary tone
- Revisit watch-author inclusion rules based on real daily usage
- Add stronger same-topic clustering and dedupe before final ranking
- Later upgrade the ranking pipeline toward embedding recall + rerank + LLM judge

Final target architecture:

1. Data collection
   - Spider_XHS pulls keyword results
   - Spider_XHS pulls recent posts from priority authors
2. Coarse filtering
   - Remove recruiting, resume, lead-gen, deployment-only, and broad tutorial noise
3. Embedding recall enhancement
   - Recover semantically relevant posts that do not explicitly match user keywords
4. Rerank
   - Sort by digest goal rather than raw popularity
5. LLM judge
   - Score novelty, clarity, methodization, usefulness, and click-worthiness
6. Cluster and dedupe
   - Keep the best post per topic cluster
7. Summarize
   - Generate one-line takeaways plus concise topic tags
