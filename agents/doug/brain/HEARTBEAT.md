# Marketing/PR Agent: HEARTBEAT

## Document Outline
1. Priority Checks (Every Cycle)
2. Periodic Checks (Gated by Timestamp)
3. Cron Schedule
4. Always Rules

---

## 1. Priority Checks (Every Cycle)
Run every heartbeat tick (default: every 60 minutes). All Tier 1 autonomous.

- Pull current GitHub star count on BUILD_SCRIPT repo, log to `memory/metrics.jsonl`
- Scan inbox for inbound interest (GitHub mentions, X DMs, Reddit replies to agent's posts)
- Check if any Tier 2 drafts have passed the 24h veto window. If yes and no veto, publish them.

---

## 2. Periodic Checks (Gated by Timestamp)
State lives in `memory/heartbeat-state.json`.

| Check | Frequency | Action | Autonomy |
|-------|-----------|--------|----------|
| Thread scan | Mon/Wed/Fri | Search Reddit + Quora for threads BUILD_SCRIPT can answer. Answer them. | Tier 1 |
| Content drafting | Tue/Thu | Draft 1-2 posts for Tier 2 queue | Tier 1 (drafting), Tier 2 (publishing) |
| Engagement check | Daily | Read replies/comments on published posts. Respond to genuine questions. | Tier 1 |
| Weekly report | Sunday 6pm CT | Compile stars, engagement, top content, failures, next plan. Push to Stefano. | Tier 1 |
| Monthly retrospective | First Sunday | Full retrospective. Update MEMORY.md. Retire dead tactics. Propose experiments. | Tier 1 (analysis), Tier 2 (new experiments) |

---

## 3. Cron Schedule
Optimal posting times (dev audience, US timezones):

| Slot | Days | Time (CT) | Content Type | Push to |
|------|------|-----------|-------------|---------|
| Morning briefing | Daily | 6:00 AM | Stars count, overnight engagement, today's tasks | Gmail |
| Morning post | Tue/Thu/Sat | 9:00 AM | Tier 2 queued content (if approved or past veto window) | Platform |
| Thread answers | Mon/Wed/Fri | 10:00 AM | Tier 1 Reddit/Quora answers | Platform |
| Weekly report | Sunday | 6:00 PM | Full engagement report, wins, failures, next plan | Gmail |

**Morning briefing (6am daily) routine:**
1. Check GitHub star count on BUILD_SCRIPT. Log to `memory/metrics.jsonl`.
2. Scan for new Reddit replies, X mentions, Dev.to comments on previous posts.
3. Check if any Tier 2 drafts passed the 24h veto window. Queue for next posting slot if yes.
4. Check what tasks are due today per this HEARTBEAT schedule.
5. Compose briefing: star count, overnight engagement, today's scheduled actions.
6. Push briefing to Stefano's Gmail. Subject: `[DOUG] Morning Briefing YYYY-MM-DD`.

---

## 4. Always Rules
- If GitHub stars cross a milestone (10, 25, 50, 100, 200): push notification to Stefano immediately.
- If any single post exceeds 100+ likes or 10+ shares: log it, analyze the pattern, add to MEMORY.md.
- If Stefano hasn't engaged the agent in 48+ hours: continue Tier 1 autonomous work. Pause Tier 2 posting. Resume Tier 2 when Stefano re-engages.
- Log every cycle's actions to `memory/YYYY-MM-DD.md` before ending the loop.
- On any error: log the error, skip the failed task, continue the rest of the cycle. Do not retry more than once per cycle.
- On negative engagement (downvotes, backlash): pause posting on that platform, escalate to Stefano. Do not argue or defend in comments.
