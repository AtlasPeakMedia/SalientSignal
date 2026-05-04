---
aliases:
  - SalientSignal Users
  - User Stories
tags:
  - apex
  - business
  - app
  - user-research
created: 2026-04-09
---

# SalientSignal — User Stories

> **Six user archetypes. How they find us, how they use us, what makes them stay, what leaves them wanting more.**

---

## User 1: Captain Torres — PSYOP Planner, CENTCOM J39

### Background
Active duty Army captain, PSYOP qualified, assigned to CENTCOM's information operations directorate. Monitors Iranian and Russian state media narratives targeting Middle Eastern audiences. Uses Google Alerts and manually checks 15 bookmarked state media sites every morning. Writes weekly hostile propaganda assessments for the J2.

### How She Finds Us
A colleague in the unit sends a link: "This thing is free with your .mil email." She signs up during lunch, verifies with her .mil address in 2 minutes.

### Daily Use (Free → Full Access via .mil)
- **0600:** Opens the site on her government laptop (no install needed — critical for .gov networks). Globe loads. She immediately sees Iran is at 2.8x baseline today — glowing orange. Saudi Arabia is at 0.4x — unusually quiet. She taps Iran.
- **0610:** Reads the morning brief on Iran. The debrief paragraph tells her Press TV's English desk focused on "Western hypocrisy" around sanctions while IRNA's Arabic desk pushed a completely different angle about Gulf economic partnerships. She screenshots this for her morning standup.
- **0620:** Opens the trend explorer. Searches "sanctions" across Iranian media for the last 60 days. Sees a clear spike starting 2 weeks ago, concentrated in Arabic-language outlets. This matches the timeline of the sanctions vote at the UN.
- **0630:** Checks the contradiction log. Finds 3 instances this week where Iranian state media told Arabic audiences one thing and English audiences another. She pulls these into her weekly assessment.

### What She Values Most
- **Free.** Her unit doesn't have budget for tools like Meltwater ($15K/yr) or Recorded Future ($50K/yr). This is free with .mil.
- **No install.** IT won't approve app installations on government machines. A website works.
- **Cross-audience contradictions.** This is exactly what her hostile propaganda analysis requires — SCAME without having to do it manually across 6 outlets.
- **Historical archive.** She can look back 90 days to show her commander how a narrative evolved. Her Google Alerts don't do that.

### What Leaves Her Wanting More
- **Classified overlay.** She can't feed classified reporting into the tool, so her analysis is always bifurcated — open source here, classified sources in JWICS. Not solvable by us, but she feels the gap.
- **Custom watchlists.** She wants to track specific Iranian officials' social media alongside state media. The app tracks outlets, not individuals yet.
- **Team sharing.** She wants to flag a brief and share it to her team's channel. No collaboration features in v1.
- **Telegram depth.** She knows IRGC-affiliated Telegram channels are critical but the free tier doesn't have Grok/Telegram integration. She'd pay for it — but it's free for .mil anyway, so this is a feature gap, not a price gap.

---

## User 2: Marcus — Freelance Disinformation Reporter

### Background
Freelance journalist covering disinformation for Wired and The Atlantic. Used CrowdTangle daily until Meta killed it in August 2024. Now cobbles together Junkipedia (free, limited), NewsWhip (expensive, his editor won't approve), and manual checks of RT/Xinhua/Press TV websites. Lost his best investigative tool and hasn't found a replacement.

### How He Finds Us
Sees a tweet from a fellow disinfo reporter: "This new tool shows you what RT's Spanish desk said about the election vs. what RT English said. Side by side. For free." He clicks the link.

### Daily Use (Free Tier)
- **Morning:** Opens the globe. Scans for anomalies. Notices Russia is at 3.2x baseline and there are arc lines connecting Russia, Venezuela, and Cuba. Taps Russia. Sees today's headlines organized by language desk. RT English, RT Spanish, RT Arabic, Sputnik — all visible.
- **Midday:** He's writing a story about Russian influence in Latin America. He sees that RT Spanish published 12 articles on the Latin American trade summit while RT English published 2. The headlines are framed completely differently. He can see this on the free tier — it's just raw GDELT data, headlines side by side. No AI analysis needed. He screenshots it for his article.
- **The conversion moment:** He wants to see if this pattern has been happening for months. He clicks "Trend Explorer" — paywall. He wants to search "Latin America" across all Russian media for the last 6 months — paywall. He pulls out his credit card. $10/month is nothing compared to the $15K NewsWhip wanted.

### What He Values Most
- **CrowdTangle replacement.** Not a perfect replacement (this tracks state media, not all of Facebook), but for his beat — disinformation and state propaganda — it's better.
- **Cross-language comparison.** This is the story. "Russia told Latin Americans X while telling Europeans Y." That's a front-page investigation. No other tool makes this comparison easy.
- **Affordable.** $10/month vs. $15K/year for Meltwater. His editor approves it in 5 minutes.
- **The globe.** It's visual. He can screenshot the arc lines for his article. "Here's what coordinated state messaging looks like."

### What Leaves Him Wanting More
- **Social media amplification tracking.** He wants to see the narrative travel: "State media publishes → which Twitter accounts amplify → which TikTok creators pick it up → which Reddit threads emerge." The app stops at state media + gray X accounts. The downstream virality isn't tracked.
- **Embeddable widgets.** He wants to embed the globe or a trend chart in his Wired article. No embed code in v1.
- **More granular source attribution.** He wants to know: "This specific journalist at RT Spanish has published 15 articles on this theme in 30 days." Per-journalist tracking, not just per-outlet.
- **Alerting.** He wants a push notification when a new coordinated campaign launches. "Russia + China + Iran all started pushing the same narrative within 24 hours." The free tier doesn't have alerts.

---

## User 3: Dr. Okafor — Political Science Professor, Georgetown

### Background
Tenured professor studying Chinese influence operations in Africa. Published 3 papers using GDELT data and was frustrated every time — Western bias, 55% accuracy on key fields, duplicate events inflating counts. Co-PI on an NSF grant studying state media framing of Belt and Road Initiative across 20 African countries.

### How She Finds Us
Hears about it at an ISA (International Studies Association) panel. A colleague mentions "this tool that tracks state media from every country, and it specifically labels which outlets are state-run vs. state-aligned." She's been manually coding that distinction for years.

### Daily Use (Paid $10/month, should be institutional)
- **Weekly research session:** Opens the tool, goes to trend explorer. Searches "Belt and Road" across all Chinese state media's English and French language desks targeting African audiences. Gets a frequency chart over 6 months. Downloads the data as CSV.
- **Comparative analysis:** Searches the same theme in Xinhua French (targeting Francophone Africa) vs. Xinhua English (targeting Anglophone Africa). Sees framing differences. This is a publishable finding.
- **Monthly data pull:** Exports 30 days of Chinese state media coverage of all 54 African countries. Cross-references with GDELT event data for the same period. Uses both datasets in her paper.

### What She Values Most
- **State media explicitly labeled.** Every outlet is tagged as state-owned, state-aligned, or independent. She doesn't have to code this herself.
- **Non-Western coverage.** The tool monitors Xinhua's Swahili desk, CGTN Africa, China Daily Africa Edition. GDELT doesn't distinguish these from general news.
- **Historical data.** After 1 year of operation, she has a custom dataset of Chinese state media coverage of Africa that didn't exist before. That's a paper.
- **Affordable for individuals.** $10/month on her research budget. Her NSF grant would cover the institutional API access when that launches.

### What Leaves Her Wanting More
- **API access.** She wants to run custom queries programmatically, not through a web interface. Pull 10,000 articles matching specific criteria into her Python pipeline. API is roadmapped for v2 but not available yet.
- **Full article text.** The tool shows headlines, metadata, and debrief paragraphs — but she wants the raw full text for her own content analysis. Copyright and storage constraints limit this.
- **Citation format.** She wants to cite the tool in her papers. Needs a proper methodology page explaining exactly how articles are collected, classified, and analyzed. Published methodology builds academic credibility.
- **Longer history.** Her research requires 3-5 years of data. The tool only has data from launch date forward. GDELT's 3-month rolling window for the DOC API means she can't even backfill.
- **Accuracy metrics.** GDELT's 55% accuracy burned her before. She wants to know this tool's false positive/negative rates.

---

## User 4: Jake — College Senior, International Relations Major

### Background
IR major at American University. Wrote his senior thesis on Russian disinformation in the 2024 election. Uses Ground News occasionally but finds the left-right spectrum useless for foreign state media. Follows Bellingcat on Twitter. Wants to understand how propaganda works without being told what to think.

### How He Finds Us
Professor mentions it in lecture. "There's a free tool that shows you what every country's state media is saying right now. Go look at what North Korea's news agency said about the summit." He pulls it up on his phone during class.

### Daily Use (Free Tier)
- **First visit:** Opens the globe on his phone. Rotates it. Sees North Korea is a neutral gray (low output, normal for DPRK). Taps it anyway. Sees KCNA's 3 articles for the day. Reads the headlines. Laughs at the language. Gets it immediately — this is what state-controlled media looks like.
- **Comparison moment:** His professor asked the class to compare how Russia and China covered the same event. He taps Russia, reads the RT headlines. Taps China, reads the Xinhua headlines. Same event, different framing. He writes this up for his assignment.
- **The hook:** He shows his roommate. "Look at this — Venezuela, Cuba, and Nicaragua are all glowing orange today and they're connected by these lines." His roommate says "What does that mean?" Jake: "Their state media is all pushing the same story." He just explained coordinated state messaging to a non-IR student using the globe visualization.

### What He Values Most
- **Free.** He's a college student. $10/month is a barrier. The free tier gives him enough for coursework.
- **Visual.** The globe is immediately understandable. He doesn't need to read documentation. Countries glow, lines connect them, he gets it.
- **Not preachy.** The tool doesn't tell him "THIS IS PROPAGANDA." It shows him the data and lets him figure it out. That's more persuasive than any lecture.
- **Shareable.** He can send a link to a friend: "Look at what Iranian state media said about this." That drives organic growth.

### What Leaves Him Wanting More
- **He wants the debrief paragraphs.** The free tier shows headlines but not the AI analysis. He reads the headlines and can sort of see the framing differences, but the paid tier's debrief paragraph would spell it out more clearly. He's tempted but won't pay.
- **He wants to go back in time.** He's writing a paper on how Russian media covered the Ukraine war over 12 months. The free tier only shows today. He'd need paid — or he'll use GDELT directly (but that's harder).
- **Mobile experience.** The globe works on his phone but it's better on a laptop. Pinch-zoom on small countries is hard. The list view fallback helps but isn't as cool.
- **Social sharing.** He wants to share a specific country's page or a specific day's brief on Instagram/X. No social sharing cards or embeddable images in v1.

---

## User 5: Sarah — Geopolitical Risk Analyst, Consulting Firm

### Background
Works at a mid-tier consulting firm that advises Fortune 500 companies on geopolitical risk. Her clients have supply chain exposure to China, Turkey, and the Gulf states. She monitors state media manually — reads Global Times, Daily Sabah, and Arab News every morning. Her firm can't afford Recorded Future ($50K+/year) or Dataminr.

### How She Finds Us
LinkedIn post from an OSINT account she follows. "New state media monitoring tool with a global view. $10/month." She trials it immediately.

### Daily Use (Paid $10/month)
- **0700:** Opens the globe. Scans for anomalies in her client-relevant countries: China, Turkey, Saudi Arabia, UAE, India. China is at 1.8x baseline — elevated. She taps it.
- **0710:** Reads the morning brief on China. Global Times and Xinhua are running a coordinated theme about "supply chain sovereignty" — a narrative that historically precedes trade policy changes. She flags this for her team.
- **0720:** Opens the trend explorer. Searches "rare earth" across Chinese state media for the last 90 days. Sees a clear upward trend starting 6 weeks ago. She includes this chart in her client memo.
- **Weekly:** Generates a PDF of the weekly digest for China, Turkey, and Saudi Arabia. Attaches it to her weekly client risk briefing.

### What She Values Most
- **State media as a leading indicator.** When Chinese state media starts pushing a narrative, policy often follows. She's using state media as an early warning system for her clients.
- **Affordable.** $10/month vs. $50K+ for Recorded Future. Her firm buys 3 seats without blinking.
- **PDF export.** She can drop the weekly digest directly into client deliverables. Professional formatting matters.
- **Trend explorer.** The 90-day view on specific themes is exactly what her risk assessments need. "Here's how Chinese state media messaging on X topic has evolved over 3 months."

### What Leaves Her Wanting More
- **Custom reports.** She wants to generate a branded PDF with her firm's logo, not the SalientSignal branding. White-label is a Phase 2 feature at best.
- **Sector-specific filtering.** She wants to track state media mentions of specific industries (semiconductors, rare earth, oil, banking). The theme taxonomy may not be granular enough for industry-specific monitoring.
- **More countries.** Her clients are increasingly worried about India (Modi's media apparatus) and Indonesia. These are covered, but the analysis depth isn't as good as Russia/China/Iran because less research attention goes to their state media.
- **Integration.** She wants the data to flow into her firm's existing dashboards (Notion, Slack, email). API access or Zapier integration would help. Neither exists in v1.
- **Forecasting.** She doesn't just want to know what state media said — she wants to know what it means for policy. That's a human analysis layer the tool can't provide, but she wishes it did.

---

## User 6: Specialist Reeves — Army Intel Analyst, 18 Months from ETS

### Background
E-4 intelligence analyst at a BCT (Brigade Combat Team). Does OSINT collection as part of his MOS but his unit has zero tools beyond OSINT Framework and Google. He's interested in IO/PSYOP and wants to transition to a contractor role or government civilian position after ETS. Uses the tool both for his job and for self-development.

### How He Finds Us
Reddit. Sees a post in r/OSINT: "Free tool that maps global state media activity on a 3D globe. Pretty legit for monitoring foreign narratives." Clicks the link.

### Daily Use (Free → Full Access via .mil)
- **At work:** Checks the tool during his OSINT research. His unit is monitoring a country in Africa where Chinese influence is growing. He opens the country page, sees Xinhua articles about infrastructure deals and Chinese state TV coverage of the president's visit. Includes this in his RFI (Request for Information) response.
- **Self-development:** At home, he explores the globe for learning. Taps random countries. Reads what Turkmenistan's state media said today. Reads what Uruguay's state media published. Starts to understand that EVERY country has a state media apparatus, not just the "big bad guys." This reframes his understanding of information operations.
- **Interview prep:** He's preparing for a contractor interview at a defense firm. He uses the trend explorer to pull 6 months of Russian media coverage of NATO. Screenshots the trend chart and includes it in his interview presentation as an example of his analytical capability. The tool becomes a portfolio piece.

### What He Values Most
- **Free with .mil.** He's an E-4. He has no money. The .mil verification is the difference between using this tool and not.
- **Learning tool.** It's teaching him IO/PSYOP analytical tradecraft without formal training. He's learning to spot cross-audience contradictions, narrative surges, and coordinated messaging just by using the tool daily.
- **Career development.** He can demonstrate OSINT analytical skills in interviews using data from the tool. "Here's an analysis I produced using open-source state media monitoring." That's a differentiator.
- **Reddit credibility.** He posts about the tool in r/OSINT and r/intel communities. Other analysts ask questions. He becomes a subject matter resource.

### What Leaves Him Wanting More
- **Training content.** He wishes the tool had an educational layer: "Here's what to look for in state media. Here's why this contradiction matters." The tool assumes the user already knows IO/PSYOP concepts. A "Learn" section would help non-expert users.
- **Saved analyses.** He wants to save a specific day's brief or a trend chart to his account for later reference. No "favorites" or "saved items" in v1.
- **Community.** He wants to discuss findings with other analysts. A forum or comments section. This is deliberately not included (scope creep, moderation burden), but the desire exists.

---

## Cross-User Summary

### What Every User Values

| Feature | Torres | Marcus | Okafor | Jake | Sarah | Reeves |
|---------|--------|--------|--------|------|-------|--------|
| Free or cheap | .mil free | $10 | $10 | Free tier | $10 | .mil free |
| Globe visualization | Uses | Screenshots | — | Core hook | Uses | Core hook |
| Cross-language comparison | Core workflow | Story material | Research data | Assignment tool | Leading indicator | Learning tool |
| Historical archive | Weekly assessments | Investigation | Paper data | Paper data | Client memos | Interview prep |
| No preachiness | Trusts it more | Trusts it more | Academic rigor | Respects it | Professional tone | Learns better |
| Baseline deviation | Quick scan | Anomaly detection | Research signal | Visual learning | Risk flagging | OSINT research |

### Conversion Triggers (Free → Paid)

| User | Conversion Moment |
|------|-------------------|
| Torres | N/A — .mil gets full access free |
| Marcus | Wants to search historical archive for an investigation |
| Okafor | Wants to export 30 days of data for a paper |
| Jake | Doesn't convert — stays free. But tells 20 classmates. |
| Sarah | Converts immediately — $10/month is a rounding error vs. Recorded Future |
| Reeves | N/A — .mil gets full access free |

### Top Feature Gaps Across All Users

1. **API access** (Okafor, Sarah) — researchers and business users want programmatic queries
2. **Embeddable content** (Marcus, Jake) — journalists and students want to share/embed visualizations
3. **Per-journalist tracking** (Marcus) — not just per-outlet, but per-person narrative tracking
4. **Custom watchlists** (Torres, Sarah) — track specific countries/themes with push alerts
5. **Saved analyses** (Reeves, Torres) — bookmark specific findings for later
6. **Social sharing cards** (Jake, Marcus) — shareable images/links with rich previews
7. **Educational content** (Reeves, Jake) — "what to look for" guidance for non-experts
8. **Team collaboration** (Torres, Sarah) — share findings within a team, comment on briefs
9. **Downstream amplification tracking** (Marcus) — how state narratives spread to mainstream social media
10. **White-label/custom branding** (Sarah) — enterprise feature for consulting firms

---

## Related Files

- [[SalientSignal-Project]] — Product vision, features, monetization, design direction
- [[SalientSignal-Source-Database]] — 151+ countries, 606+ outlets, all APIs
- [[SalientSignal-Technical-Spec]] — Verified numbers, daily pipeline, cost breakdown
