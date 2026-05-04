---
aliases:
  - SalientSignal Algorithms
  - Algorithm Specification
tags:
  - apex
  - business
  - app
  - engineering
  - algorithms
created: 2026-04-09
---

# SalientSignal — Algorithm Specification

> **Every algorithm needed to run the pipeline, detect patterns, classify sources, track trends, and produce intelligence. Pseudocode where it matters. Math where it counts.**

---

## Algorithm 1: Source Classification (Domestic vs. International)

### The Problem

The same country operates media that talks to its own citizens and media that talks to the world. These often tell different stories about the same events. Every article must be classified as DOMESTIC or INTERNATIONAL audience targeting.

### Classification Signals (Ranked by Reliability)

**Signal 1: Outlet Identity (Highest Confidence)**

Most state media outlets have an explicit audience identity. This is a hard-coded lookup, not inference.

```
OUTLET_CLASSIFICATION = {
    # Russia
    "rt.com":           {"country": "RU", "audience": "INTERNATIONAL", "languages": ["en","es","fr","ar","de"]},
    "sputniknews.com":  {"country": "RU", "audience": "INTERNATIONAL", "languages": ["en","es","fr","ar","pt","etc"]},
    "tass.com":         {"country": "RU", "audience": "INTERNATIONAL", "languages": ["en"]},
    "tass.ru":          {"country": "RU", "audience": "DOMESTIC",      "languages": ["ru"]},
    "ria.ru":           {"country": "RU", "audience": "DOMESTIC",      "languages": ["ru"]},
    "1tv.ru":           {"country": "RU", "audience": "DOMESTIC",      "languages": ["ru"]},
    "vesti.ru":         {"country": "RU", "audience": "DOMESTIC",      "languages": ["ru"]},

    # China
    "xinhua.net":       {"country": "CN", "audience": "INTERNATIONAL", "languages": ["en","fr","es","ar","ru","pt"]},
    "xinhuanet.com/zh": {"country": "CN", "audience": "DOMESTIC",      "languages": ["zh"]},
    "cgtn.com":         {"country": "CN", "audience": "INTERNATIONAL", "languages": ["en","fr","es","ar","ru"]},
    "cctv.com":         {"country": "CN", "audience": "DOMESTIC",      "languages": ["zh"]},
    "globaltimes.cn":   {"country": "CN", "audience": "INTERNATIONAL", "languages": ["en"]},
    "people.com.cn/zh": {"country": "CN", "audience": "DOMESTIC",      "languages": ["zh"]},
    "chinadaily.com.cn":{"country": "CN", "audience": "INTERNATIONAL", "languages": ["en"]},

    # Iran
    "presstv.ir":       {"country": "IR", "audience": "INTERNATIONAL", "languages": ["en"]},
    "irna.ir/en":       {"country": "IR", "audience": "INTERNATIONAL", "languages": ["en"]},
    "irna.ir":          {"country": "IR", "audience": "DOMESTIC",      "languages": ["fa"]},
    "farsnews.ir":      {"country": "IR", "audience": "DOMESTIC",      "languages": ["fa"]},
    "alalam.ir":        {"country": "IR", "audience": "INTERNATIONAL", "languages": ["ar"]},

    # Turkey
    "trtworld.com":     {"country": "TR", "audience": "INTERNATIONAL", "languages": ["en"]},
    "trthaber.com":     {"country": "TR", "audience": "DOMESTIC",      "languages": ["tr"]},
    "aa.com.tr/en":     {"country": "TR", "audience": "INTERNATIONAL", "languages": ["en","ar","fr","ru"]},
    "aa.com.tr/tr":     {"country": "TR", "audience": "DOMESTIC",      "languages": ["tr"]},

    # ... 606+ outlets total, each classified
}
```

**Confidence: HIGH.** The outlet's identity IS its audience. RT was created to talk to non-Russians. Rossiya 1 was created to talk to Russians. This isn't inference.

**Signal 2: Publication Language vs. Country's Official Language**

```python
def classify_by_language(article_language, country_official_languages):
    """
    If a Russian outlet publishes in Spanish, it's targeting international audiences.
    If it publishes in Russian, it's targeting domestic audiences.
    """
    if article_language in country_official_languages:
        return "DOMESTIC", confidence=0.75
    else:
        return "INTERNATIONAL", confidence=0.85

# Edge cases:
# - Russian in Ukraine (large Russian-speaking population) → DIASPORA
# - English in India (official language) → could be either
# - Arabic from Al Jazeera (Qatar) → targeting broader Arab world, not just Qataris
```

**Confidence: MEDIUM-HIGH.** Works for most cases. Fails for multilingual countries and diaspora targeting.

**Signal 3: Platform**

```python
PLATFORM_AUDIENCE = {
    "vk.com":       {"audience": "DOMESTIC", "country": "RU", "confidence": 0.90},
    "weibo.com":    {"audience": "DOMESTIC", "country": "CN", "confidence": 0.90},
    "douyin.com":   {"audience": "DOMESTIC", "country": "CN", "confidence": 0.95},
    "tiktok.com":   {"audience": "INTERNATIONAL", "country": "CN", "confidence": 0.80},
    "twitter.com":  {"audience": "INTERNATIONAL", "country": "*", "confidence": 0.70},
    "telegram.org": {"audience": "VARIES",  "country": "*", "confidence": 0.50},
    # Telegram: Russian domestic + international. Must check channel language.
}
```

**Signal 4: Domain TLD and Subdomain**

```python
def classify_by_domain(url):
    """
    .ru, .cn, .ir = likely domestic
    .com, .org, .net = likely international
    Subdomain language codes (en., fr., ar.) = international language desks
    """
    domain = extract_domain(url)
    tld = domain.split(".")[-1]

    if tld in ["ru", "cn", "ir", "tr", "sa", "qa", "ae"]:
        return "DOMESTIC", confidence=0.60
    elif has_language_subdomain(url, non_native=True):
        return "INTERNATIONAL", confidence=0.80
    else:
        return "UNKNOWN", confidence=0.40
```

**Confidence: LOW-MEDIUM.** Many international outlets use country TLDs (rt.com redirects to rt.com but content is international). Use only as tiebreaker.

### Final Classification Function

```python
def classify_audience(article):
    """
    Combine all signals with weighted confidence.
    Returns: "DOMESTIC", "INTERNATIONAL", or "DIASPORA"
    Plus confidence score 0.0-1.0
    """
    scores = {"DOMESTIC": 0, "INTERNATIONAL": 0, "DIASPORA": 0}

    # Signal 1: Outlet lookup (weight: 1.0 — this is the truth when available)
    outlet = OUTLET_CLASSIFICATION.get(article.domain)
    if outlet:
        return outlet["audience"], confidence=0.95

    # Signal 2: Language vs. country official languages (weight: 0.8)
    lang_class, lang_conf = classify_by_language(
        article.language, 
        COUNTRY_LANGUAGES[article.source_country]
    )
    scores[lang_class] += 0.8 * lang_conf

    # Signal 3: Platform (weight: 0.7)
    platform = PLATFORM_AUDIENCE.get(article.platform)
    if platform and platform["audience"] != "VARIES":
        scores[platform["audience"]] += 0.7 * platform["confidence"]

    # Signal 4: Domain TLD (weight: 0.3)
    domain_class, domain_conf = classify_by_domain(article.url)
    if domain_class != "UNKNOWN":
        scores[domain_class] += 0.3 * domain_conf

    # Return highest-scoring classification
    best = max(scores, key=scores.get)
    total = sum(scores.values())
    confidence = scores[best] / total if total > 0 else 0

    return best, confidence
```

### Edge Case: Diaspora Targeting

Some content targets diaspora communities — Russian media in German (targeting Russian-Germans), Chinese media in Malay (targeting Chinese-Malaysians). This is a third category:

```python
DIASPORA_PATTERNS = {
    "RU": {
        "languages_in_countries": {
            "de": ["DE"],  # RT DE → Russian diaspora in Germany
            "fr": ["FR"],  # RT FR → but also Francophone Africa
        }
    },
    "CN": {
        "languages_in_countries": {
            "ms": ["MY"],  # Xinhua Malay → Chinese-Malaysians
            "id": ["ID"],  # Xinhua Indonesian → Chinese-Indonesians
        }
    }
}
```

---

## Algorithm 2: Baseline Deviation (Globe Color Coding)

### The Problem

Each country needs a "normal" level of state media output so that spikes and silences are detectable. The baseline must account for: weekday vs. weekend patterns, holidays, different output volumes by country, and ramping periods for new outlets.

### Baseline Calculation

```python
def calculate_baseline(country_code, audience_type, date):
    """
    30-day rolling average of daily article count for this country.
    Separate baselines for DOMESTIC and INTERNATIONAL audiences.
    Uses same-day-of-week comparison to handle weekend effects.
    """
    # Get last 30 days of daily counts
    daily_counts = db.query("""
        SELECT date, COUNT(*) as count 
        FROM articles 
        WHERE source_country = :country 
          AND audience_type = :audience_type
          AND date BETWEEN :date - 30 AND :date - 1
        GROUP BY date
    """, country=country_code, audience_type=audience_type, date=date)

    if len(daily_counts) < 7:
        # Not enough data for reliable baseline (new country or new monitoring)
        return None  # No color coding — show as neutral gray

    # Simple 30-day mean
    mean_30d = sum(d.count for d in daily_counts) / len(daily_counts)

    # Standard deviation for anomaly detection
    std_30d = sqrt(
        sum((d.count - mean_30d) ** 2 for d in daily_counts) / len(daily_counts)
    )

    return {
        "mean": mean_30d,
        "std": std_30d,
        "min_30d": min(d.count for d in daily_counts),
        "max_30d": max(d.count for d in daily_counts),
        "days_sampled": len(daily_counts)
    }
```

### Deviation Ratio

```python
def calculate_deviation(country_code, audience_type, date):
    """
    How far is today's output from normal?
    Returns a ratio AND a z-score.
    """
    baseline = calculate_baseline(country_code, audience_type, date)
    if baseline is None:
        return {"ratio": 1.0, "z_score": 0, "confidence": "LOW"}

    today_count = db.query("""
        SELECT COUNT(*) FROM articles 
        WHERE source_country = :country 
          AND audience_type = :audience_type
          AND date = :date
    """, country=country_code, audience_type=audience_type, date=date)

    # Ratio: today vs. average
    ratio = today_count / baseline["mean"] if baseline["mean"] > 0 else 0

    # Z-score: how many standard deviations from mean
    z_score = (today_count - baseline["mean"]) / baseline["std"] if baseline["std"] > 0 else 0

    return {
        "ratio": round(ratio, 2),
        "z_score": round(z_score, 2),
        "today_count": today_count,
        "baseline_mean": round(baseline["mean"], 1),
        "baseline_std": round(baseline["std"], 1),
        "confidence": "HIGH" if baseline["days_sampled"] >= 21 else "MEDIUM"
    }
```

### Color Mapping Function

```python
def deviation_to_color(deviation, audience_type):
    """
    Maps deviation ratio to a color on the globe.
    Separate color channels for DOMESTIC and INTERNATIONAL.
    
    DOMESTIC: uses left half of legend (blues to reds)
    INTERNATIONAL: uses right half of legend (teals to oranges)
    Or: user toggles between domestic/international view.
    """
    ratio = deviation["ratio"]
    z = deviation["z_score"]

    # Color thresholds based on BOTH ratio and z-score
    # Z-score prevents false alarms from noisy small countries
    if ratio < 0.3 and z < -2.0:
        return "DEEP_BLUE"      # #1A3A5C — Significant silence
    elif ratio < 0.5 and z < -1.5:
        return "STEEL_BLUE"     # #4A7FB5 — Unusually quiet
    elif ratio < 0.75:
        return "COOL_GRAY"      # #2A3040 — Slightly below normal
    elif ratio <= 1.5:
        return "NEUTRAL"        # #1A1D24 — Normal range
    elif ratio <= 2.5 and z >= 1.5:
        return "AMBER"          # #F5A623 — Elevated
    elif ratio <= 4.0 and z >= 2.0:
        return "ORANGE"         # #E8601C — Significant spike
    elif z >= 2.5:
        return "RED"            # #D93025 — Anomalous surge
    else:
        return "NEUTRAL"        # Ratio high but z-score low = noisy country

# Why both ratio AND z-score?
# 
# A country that publishes 2 articles/day (mean=2, std=1) 
# might publish 6 articles today.
# Ratio = 3.0 (looks alarming)
# Z-score = 4.0 (genuinely anomalous)
# → Color: ORANGE or RED ✓
#
# A country that publishes 500 articles/day (mean=500, std=100) 
# might publish 750 today.
# Ratio = 1.5 (mild elevation)
# Z-score = 2.5 (statistically significant)
# → Color: AMBER ✓
#
# A country that publishes 3 articles/day (mean=3, std=3)
# might publish 9 today.
# Ratio = 3.0 (looks alarming)
# Z-score = 2.0 (moderate — high variance country)
# → Color: AMBER (not RED) — the z-score tempers the ratio ✓
```

### Domestic vs. International Globe Toggle

The globe has a toggle: **DOMESTIC | INTERNATIONAL | BOTH**

```python
def get_globe_data(date, view_mode):
    """
    Returns country color data for the globe based on selected view.
    """
    countries = get_all_monitored_countries()
    globe_data = []

    for country in countries:
        if view_mode == "DOMESTIC":
            dev = calculate_deviation(country, "DOMESTIC", date)
            color = deviation_to_color(dev, "DOMESTIC")
        elif view_mode == "INTERNATIONAL":
            dev = calculate_deviation(country, "INTERNATIONAL", date)
            color = deviation_to_color(dev, "INTERNATIONAL")
        elif view_mode == "BOTH":
            dom = calculate_deviation(country, "DOMESTIC", date)
            intl = calculate_deviation(country, "INTERNATIONAL", date)
            # Use the MORE anomalous of the two
            if abs(dom["z_score"]) > abs(intl["z_score"]):
                color = deviation_to_color(dom, "DOMESTIC")
                dev = dom
            else:
                color = deviation_to_color(intl, "INTERNATIONAL")
                dev = intl

        globe_data.append({
            "country_code": country,
            "color": color,
            "domestic_ratio": dom["ratio"] if view_mode != "INTERNATIONAL" else None,
            "international_ratio": intl["ratio"] if view_mode != "DOMESTIC" else None,
            "domestic_count": dom["today_count"] if view_mode != "INTERNATIONAL" else None,
            "international_count": intl["today_count"] if view_mode != "DOMESTIC" else None,
        })

    return globe_data
```

### Country Page Split View

When user taps a country, the page shows **two columns** (or tabs on mobile):

```
┌─────────────────────────────────────────────┐
│  🇷🇺 RUSSIA                                 │
├──────────────────┬──────────────────────────┤
│  DOMESTIC        │  INTERNATIONAL           │
│  Today: 847      │  Today: 312              │
│  Baseline: 790   │  Baseline: 285           │
│  Ratio: 1.07x    │  Ratio: 1.09x            │
│                  │                          │
│  TOP THEMES:     │  TOP THEMES:             │
│  1. Economy (23%) │  1. NATO (31%)           │
│  2. Military (18%)│  2. Ukraine (24%)        │
│  3. Social (15%)  │  3. Sanctions (18%)      │
│                  │                          │
│  OUTLETS:        │  OUTLETS:                │
│  Rossiya 1 (341) │  RT English (89)         │
│  TASS.ru (189)   │  RT Spanish (67)         │
│  RIA.ru (156)    │  RT Arabic (54)          │
│  1TV.ru (98)     │  Sputnik EN (42)         │
│  Vesti.ru (63)   │  RT French (31)          │
│                  │  TASS.com (29)           │
├──────────────────┴──────────────────────────┤
│  CONTRADICTIONS DETECTED: 3                  │
│  ► Domestic says X. International says Y.    │
│  ► Domestic emphasis: Z. Intl emphasis: W.   │
└─────────────────────────────────────────────┘
```

---

## Algorithm 3: Event Clustering

### The Problem

Multiple outlets across multiple countries publish about the same real-world event. Need to group them into clusters so we can compare how different countries covered the same event.

### Approach: Title Similarity + Temporal Proximity + Entity Overlap

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_similarity

def cluster_events(articles, time_window_hours=24, similarity_threshold=0.35):
    """
    Group articles about the same event.
    Uses TF-IDF on translated titles + entity overlap + temporal proximity.
    
    Low similarity threshold (0.35) because:
    - Different countries frame the same event very differently
    - Translations introduce noise
    - We WANT to catch articles about the same event with different framing
    """
    # Step 1: Normalize — all titles translated to English by this point
    titles = [a.title_english for a in articles]

    # Step 2: TF-IDF vectorization
    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=10000,
        ngram_range=(1, 2)  # Unigrams + bigrams for phrase matching
    )
    tfidf_matrix = vectorizer.fit_transform(titles)

    # Step 3: Cosine similarity matrix
    sim_matrix = cosine_similarity(tfidf_matrix)

    # Step 4: Apply temporal constraint
    # Articles more than time_window_hours apart cannot be in same cluster
    for i in range(len(articles)):
        for j in range(len(articles)):
            time_diff = abs(articles[i].pub_date - articles[j].pub_date)
            if time_diff.total_seconds() > time_window_hours * 3600:
                sim_matrix[i][j] = 0

    # Step 5: Entity overlap boost
    # If two articles mention the same people/places/orgs, boost similarity
    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            entities_i = set(articles[i].entities)
            entities_j = set(articles[j].entities)
            if entities_i and entities_j:
                entity_overlap = len(entities_i & entities_j) / len(entities_i | entities_j)
                sim_matrix[i][j] += entity_overlap * 0.3  # 30% boost for entity overlap
                sim_matrix[j][i] = sim_matrix[i][j]

    # Step 6: DBSCAN clustering
    # Convert similarity to distance
    distance_matrix = 1 - sim_matrix
    clustering = DBSCAN(
        eps=1 - similarity_threshold,  # Distance threshold
        min_samples=2,                  # Need at least 2 articles to form a cluster
        metric="precomputed"
    ).fit(distance_matrix)

    # Step 7: Build cluster objects
    clusters = {}
    for idx, label in enumerate(clustering.labels_):
        if label == -1:
            continue  # Unclustered articles (singletons)
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(articles[idx])

    return clusters
```

### Why This Is Hard

The same event can have wildly different titles in different state media:
- RT English: "NATO Expansion Summit Concludes in Discord"
- Xinhua: "European Leaders Discuss Regional Security Framework"
- Press TV: "Western Military Alliance Tightens Grip on Eastern Europe"

These are all about the same summit. TF-IDF alone might not catch it. Entity overlap (same leaders, same location, same date) is the tiebreaker.

### Fallback: GDELT Event IDs

GDELT already clusters events using the CAMEO taxonomy. When GDELT assigns the same event ID to articles from different sources, we can use that as a pre-clustered grouping. Our algorithm above runs on articles GDELT didn't cluster (different framing, different entities extracted).

---

## Algorithm 4: Cross-Audience Contradiction Detection

### The Problem

Detect when a country tells its domestic audience one thing and its international audience another about the same event.

### Approach

```python
def detect_contradictions(event_cluster, country_code):
    """
    For a given event cluster, compare domestic vs. international coverage
    from the same country. Score the divergence.
    """
    # Split articles by audience
    domestic = [a for a in event_cluster 
                if a.source_country == country_code and a.audience_type == "DOMESTIC"]
    international = [a for a in event_cluster 
                     if a.source_country == country_code and a.audience_type == "INTERNATIONAL"]

    if not domestic or not international:
        return None  # Need both to compare

    # Extract framing features
    dom_framing = extract_framing(domestic)
    intl_framing = extract_framing(international)

    # Compare across 5 dimensions
    contradiction_score = 0
    contradiction_details = []

    # 1. TOPIC EMPHASIS — are they covering the same aspects?
    dom_keywords = set(dom_framing["top_keywords"])
    intl_keywords = set(intl_framing["top_keywords"])
    keyword_overlap = len(dom_keywords & intl_keywords) / len(dom_keywords | intl_keywords)
    if keyword_overlap < 0.3:
        contradiction_score += 0.25
        contradiction_details.append({
            "dimension": "topic_emphasis",
            "domestic_focus": list(dom_keywords - intl_keywords)[:5],
            "international_focus": list(intl_keywords - dom_keywords)[:5],
            "overlap": keyword_overlap
        })

    # 2. TONE DIVERGENCE — is the sentiment different?
    tone_diff = abs(dom_framing["avg_tone"] - intl_framing["avg_tone"])
    if tone_diff > 3.0:  # GDELT tone is -10 to +10
        contradiction_score += 0.25
        contradiction_details.append({
            "dimension": "tone",
            "domestic_tone": dom_framing["avg_tone"],
            "international_tone": intl_framing["avg_tone"],
            "difference": tone_diff
        })

    # 3. VOLUME ASYMMETRY — is one audience getting much more coverage?
    dom_count = len(domestic)
    intl_count = len(international)
    volume_ratio = max(dom_count, intl_count) / max(min(dom_count, intl_count), 1)
    if volume_ratio > 3.0:
        contradiction_score += 0.20
        contradiction_details.append({
            "dimension": "volume_asymmetry",
            "domestic_articles": dom_count,
            "international_articles": intl_count,
            "ratio": volume_ratio
        })

    # 4. HEADLINE FRAMING — do the headlines suggest different narratives?
    dom_headlines = [a.title_english for a in domestic]
    intl_headlines = [a.title_english for a in international]
    headline_sim = compute_average_similarity(dom_headlines, intl_headlines)
    if headline_sim < 0.25:
        contradiction_score += 0.20
        contradiction_details.append({
            "dimension": "headline_framing",
            "domestic_sample": dom_headlines[0],
            "international_sample": intl_headlines[0],
            "similarity": headline_sim
        })

    # 5. OMISSION — did one audience get coverage the other didn't?
    # (Only applies when one side has 0 articles for this event)
    if dom_count == 0 or intl_count == 0:
        contradiction_score += 0.10
        contradiction_details.append({
            "dimension": "omission",
            "covered_for": "international" if dom_count == 0 else "domestic",
            "omitted_for": "domestic" if dom_count == 0 else "international"
        })

    return {
        "country": country_code,
        "contradiction_score": min(contradiction_score, 1.0),  # Cap at 1.0
        "is_significant": contradiction_score >= 0.40,
        "details": contradiction_details,
        "domestic_articles": dom_count,
        "international_articles": intl_count
    }


def extract_framing(articles):
    """
    Extract framing features from a set of articles about the same event.
    """
    all_text = " ".join([a.title_english for a in articles])

    # TF-IDF keywords (top distinctive words)
    vectorizer = TfidfVectorizer(stop_words="english", max_features=20)
    matrix = vectorizer.fit_transform([all_text])
    top_keywords = sorted(
        zip(vectorizer.get_feature_names_out(), matrix.toarray()[0]),
        key=lambda x: x[1], reverse=True
    )[:10]

    # Average tone from GDELT
    avg_tone = sum(a.tone for a in articles) / len(articles)

    return {
        "top_keywords": [kw[0] for kw in top_keywords],
        "avg_tone": avg_tone,
        "article_count": len(articles)
    }
```

### Contradiction Severity Levels

| Score | Level | Globe Indicator |
|-------|-------|-----------------|
| 0.0 - 0.19 | No contradiction | No indicator |
| 0.20 - 0.39 | Minor divergence | — |
| 0.40 - 0.59 | Significant divergence | Small badge on country |
| 0.60 - 0.79 | Major contradiction | Pulsing badge |
| 0.80 - 1.00 | Direct contradiction | Pulsing badge + appears in alerts |

---

## Algorithm 5: Theme Extraction & Tracking

### Theme Taxonomy

Two layers: GDELT's built-in themes (broad) + custom state media narrative themes (specific).

```python
NARRATIVE_THEMES = {
    # Geopolitical narratives (commonly pushed by adversary state media)
    "NATO_AGGRESSION":       {"keywords": ["nato", "expansion", "provocation", "encirclement", "threat"]},
    "WESTERN_HYPOCRISY":     {"keywords": ["double standard", "hypocrisy", "selective", "rules-based"]},
    "SOVEREIGNTY":           {"keywords": ["sovereignty", "internal affairs", "interference", "self-determination"]},
    "ECONOMIC_COERCION":     {"keywords": ["sanctions", "economic warfare", "coercion", "weaponize"]},
    "MULTIPOLARITY":         {"keywords": ["multipolar", "new world order", "BRICS", "dedollarization"]},
    "WESTERN_DECLINE":       {"keywords": ["decline", "collapse", "crisis", "failing", "divided"]},
    "DEVELOPMENT_MODEL":     {"keywords": ["belt and road", "development", "infrastructure", "partnership"]},
    "MILITARY_STRENGTH":     {"keywords": ["military", "defense", "capability", "modernization", "exercise"]},
    "SOCIAL_DECAY":          {"keywords": ["crime", "drugs", "homelessness", "immigration crisis"]},
    "TECHNOLOGY_LEADERSHIP": {"keywords": ["innovation", "technology", "AI", "space", "5G"]},
    
    # Regional narratives
    "TAIWAN_SOVEREIGNTY":    {"keywords": ["taiwan", "one china", "reunification", "separatist"]},
    "UKRAINE_SPECIAL_OP":    {"keywords": ["special operation", "denazification", "kiev regime"]},
    "PALESTINE_SOLIDARITY":  {"keywords": ["palestine", "occupation", "resistance", "zionist"]},
    "GULF_RIVALRY":          {"keywords": ["qatar", "saudi", "blockade", "normalization"]},
    
    # Positive self-image
    "REGIME_LEGITIMACY":     {"keywords": ["election", "support", "prosperity", "stability", "unity"]},
    "HUMANITARIAN_AID":      {"keywords": ["aid", "humanitarian", "assistance", "cooperation"]},
    
    # Custom — expanded as patterns emerge
}
```

### Theme Scoring Per Article

```python
def score_themes(article):
    """
    Score each article against all narrative themes.
    Uses keyword matching + GDELT theme codes.
    Returns list of (theme, confidence) tuples.
    """
    text = (article.title_english + " " + article.description_english).lower()
    matched_themes = []

    for theme_name, theme_def in NARRATIVE_THEMES.items():
        # Keyword count
        keyword_hits = sum(1 for kw in theme_def["keywords"] if kw in text)
        keyword_ratio = keyword_hits / len(theme_def["keywords"])

        if keyword_ratio >= 0.2:  # At least 20% of keywords present
            confidence = min(keyword_ratio * 1.5, 1.0)  # Scale up, cap at 1.0
            matched_themes.append((theme_name, round(confidence, 2)))

    # Also map GDELT theme codes to our taxonomy
    for gdelt_theme in article.gdelt_themes:
        mapped = GDELT_THEME_MAP.get(gdelt_theme)
        if mapped and mapped not in [t[0] for t in matched_themes]:
            matched_themes.append((mapped, 0.60))  # Lower confidence for GDELT mapping

    return matched_themes
```

### Theme Frequency Over Time

```python
def get_theme_trend(theme_name, country_code, audience_type, days=90):
    """
    Daily frequency of a theme for a country/audience over time.
    Returns time series data for charting.
    """
    data = db.query("""
        SELECT date, COUNT(*) as count
        FROM article_themes at
        JOIN articles a ON at.article_id = a.id
        WHERE at.theme = :theme
          AND a.source_country = :country
          AND a.audience_type = :audience_type
          AND a.date >= CURRENT_DATE - :days
        GROUP BY date
        ORDER BY date
    """, theme=theme_name, country=country_code, 
       audience_type=audience_type, days=days)

    # Fill in zero days (no articles matching theme)
    all_dates = generate_date_range(days)
    counts = {d.date: d.count for d in data}
    return [{"date": d, "count": counts.get(d, 0)} for d in all_dates]
```

---

## Algorithm 6: Narrative Coordination Detection

### The Problem

Detect when multiple countries' state media push the same narrative within a short time window. Russia, China, and Iran coordinating on "Western hypocrisy" simultaneously is a meaningful signal.

### Approach: Cross-Country Temporal Correlation

```python
def detect_coordination(theme_name, date, time_window_hours=48):
    """
    For a given theme, check which countries surged it within a time window.
    Returns coordination clusters.
    """
    # Get all countries where this theme spiked above 2x baseline today
    surging_countries = db.query("""
        SELECT source_country, COUNT(*) as count, 
               baseline_avg, (COUNT(*) / baseline_avg) as ratio
        FROM articles a
        JOIN article_themes at ON a.id = at.article_id
        JOIN country_baselines cb ON a.source_country = cb.country 
          AND at.theme = cb.theme
        WHERE at.theme = :theme
          AND a.date BETWEEN :date - INTERVAL ':hours hours' AND :date
        GROUP BY source_country, baseline_avg
        HAVING (COUNT(*) / baseline_avg) > 2.0
    """, theme=theme_name, date=date, hours=time_window_hours)

    if len(surging_countries) < 2:
        return None  # Need 2+ countries surging the same theme

    # Calculate coordination score
    # Based on: number of countries, timing proximity, theme specificity
    coordination_score = calculate_coordination_score(surging_countries, theme_name)

    return {
        "theme": theme_name,
        "countries": [c.source_country for c in surging_countries],
        "time_window": time_window_hours,
        "coordination_score": coordination_score,
        "details": [{
            "country": c.source_country,
            "article_count": c.count,
            "baseline_ratio": round(c.ratio, 2)
        } for c in surging_countries]
    }


def calculate_coordination_score(surging_countries, theme_name):
    """
    Score how likely this is coordinated vs. coincidental.
    
    Higher score when:
    - More countries involved (3 > 2)
    - Countries are known to coordinate (Russia + China > Brazil + Japan)
    - Theme is specific (TAIWAN_SOVEREIGNTY > general foreign policy)
    - Timing is tight (all within 6 hours > spread over 48 hours)
    """
    n_countries = len(surging_countries)

    # Known coordination pairs (empirically observed)
    KNOWN_PAIRS = {
        frozenset(["RU", "CN"]): 0.3,   # Russia-China coordination documented
        frozenset(["RU", "IR"]): 0.3,   # Russia-Iran coordination documented
        frozenset(["CN", "IR"]): 0.2,   # China-Iran less documented
        frozenset(["RU", "VE"]): 0.2,   # Russia-Venezuela
        frozenset(["CU", "VE"]): 0.2,   # Cuba-Venezuela
        frozenset(["RU", "CN", "IR"]): 0.5,  # Triple coordination is very significant
    }

    country_set = frozenset(c.source_country for c in surging_countries)
    pair_bonus = KNOWN_PAIRS.get(country_set, 0)

    # More countries = more significant
    country_bonus = min((n_countries - 1) * 0.15, 0.45)

    # Theme specificity (narrow themes are more significant)
    specificity = NARRATIVE_THEMES[theme_name].get("specificity", 0.5)

    score = pair_bonus + country_bonus + (specificity * 0.2)
    return min(score, 1.0)
```

### Arc Line Generation for Globe

```python
def generate_coordination_arcs(date):
    """
    Generate arc line data for the globe visualization.
    Each arc connects two countries that are pushing the same theme.
    """
    arcs = []

    for theme in NARRATIVE_THEMES:
        coord = detect_coordination(theme, date)
        if coord and coord["coordination_score"] >= 0.30:
            countries = coord["countries"]
            # Generate arcs between all pairs
            for i in range(len(countries)):
                for j in range(i + 1, len(countries)):
                    arcs.append({
                        "start_country": countries[i],
                        "end_country": countries[j],
                        "theme": theme,
                        "score": coord["coordination_score"],
                        "color": arc_color(coord["coordination_score"]),
                        "stroke_width": 1 + coord["coordination_score"] * 3,
                        "altitude": 0.3 + coord["coordination_score"] * 0.2
                    })

    return arcs


def arc_color(score):
    """Stronger coordination = brighter arc."""
    if score >= 0.70:
        return "#00E5CC"  # Bright teal
    elif score >= 0.50:
        return "#00BFA5"  # Medium teal
    else:
        return "#00897B"  # Muted teal
```

---

## Algorithm 7: Trend Analysis Over Time

### The Problem

This is the tricky one. Need to detect:
1. Emerging themes (new narrative appearing)
2. Surging themes (existing narrative accelerating)
3. Peaked themes (narrative at maximum intensity)
4. Declining themes (narrative fading)
5. Resurgent themes (narrative that faded but came back)
6. Cyclic themes (anniversary-driven narratives that repeat annually)
7. Gradual shifts (slow audience targeting changes over months)

### Theme Lifecycle Detection

```python
from scipy.signal import argrelextrema
import numpy as np

def detect_lifecycle_stage(theme_series, min_history_days=14):
    """
    Given a daily time series of theme frequency, determine its lifecycle stage.
    
    Input: [{"date": "2026-04-01", "count": 5}, {"date": "2026-04-02", "count": 8}, ...]
    Output: lifecycle stage + confidence
    """
    counts = np.array([d["count"] for d in theme_series])
    
    if len(counts) < min_history_days:
        return {"stage": "INSUFFICIENT_DATA", "confidence": 0}

    # Smoothing: 3-day moving average to reduce noise
    smoothed = np.convolve(counts, np.ones(3)/3, mode="valid")

    if len(smoothed) < 7:
        return {"stage": "INSUFFICIENT_DATA", "confidence": 0}

    # Recent trend (last 7 days)
    recent = smoothed[-7:]
    recent_slope = np.polyfit(range(len(recent)), recent, 1)[0]

    # Overall mean and recent mean
    overall_mean = np.mean(smoothed)
    recent_mean = np.mean(recent)

    # Find peaks and troughs
    peaks = argrelextrema(smoothed, np.greater, order=3)[0]
    troughs = argrelextrema(smoothed, np.less, order=3)[0]

    # Lifecycle classification
    if overall_mean < 1.0 and recent_mean > 3.0:
        # Was near zero, now appearing
        return {"stage": "EMERGING", "confidence": 0.80,
                "detail": "Theme appeared recently with no prior history"}

    elif recent_slope > 0.5 and recent_mean > overall_mean * 1.5:
        # Accelerating upward, above historical average
        return {"stage": "SURGING", "confidence": 0.75,
                "slope": round(recent_slope, 2),
                "detail": f"Increasing at {recent_slope:.1f} articles/day"}

    elif len(peaks) > 0 and peaks[-1] >= len(smoothed) - 4:
        # Most recent peak is within last 4 days
        return {"stage": "PEAKED", "confidence": 0.70,
                "peak_date": theme_series[peaks[-1] + 1]["date"],
                "detail": "At or near maximum intensity"}

    elif recent_slope < -0.5 and recent_mean < overall_mean * 0.7:
        # Declining, below historical average
        return {"stage": "DECLINING", "confidence": 0.70,
                "slope": round(recent_slope, 2),
                "detail": f"Decreasing at {abs(recent_slope):.1f} articles/day"}

    elif (len(peaks) >= 2 and 
          smoothed[peaks[-1]] > overall_mean * 2 and
          any(smoothed[t] < overall_mean * 0.3 for t in troughs if t > peaks[-2])):
        # Had a peak, dropped to near zero, then peaked again
        return {"stage": "RESURGENT", "confidence": 0.65,
                "detail": "Narrative returned after a period of dormancy"}

    elif recent_mean < overall_mean * 0.3 and max(counts[-14:]) < overall_mean * 0.5:
        # Near zero for 2 weeks, below historical average
        return {"stage": "FADED", "confidence": 0.70,
                "detail": "Narrative has gone dormant"}

    else:
        return {"stage": "STABLE", "confidence": 0.60,
                "detail": "Within normal variation"}
```

### Cyclic Pattern Detection (Anniversary Narratives)

```python
def detect_cyclic_pattern(theme_name, country_code):
    """
    Detect annually recurring narrative patterns.
    Requires 12+ months of data.
    
    Examples:
    - Russian media: Victory Day (May 9) narratives spike every year
    - Chinese media: Tiananmen anniversary (June 4) coverage changes every year
    - Iranian media: Revolution Day (Feb 11) narratives surge annually
    """
    # Get monthly theme counts for all available history
    monthly = db.query("""
        SELECT EXTRACT(MONTH FROM date) as month, 
               AVG(daily_count) as avg_daily
        FROM theme_daily_counts
        WHERE theme = :theme AND country = :country
        GROUP BY EXTRACT(MONTH FROM date)
        HAVING COUNT(DISTINCT EXTRACT(YEAR FROM date)) >= 1
        ORDER BY month
    """, theme=theme_name, country=country_code)

    if len(monthly) < 12:
        return None  # Need at least 12 months

    counts = [m.avg_daily for m in monthly]
    overall_mean = sum(counts) / len(counts)

    # Find months that are significantly above average
    spike_months = []
    for m in monthly:
        if m.avg_daily > overall_mean * 2.0:
            spike_months.append({
                "month": int(m.month),
                "avg_daily": round(m.avg_daily, 1),
                "ratio_to_mean": round(m.avg_daily / overall_mean, 2)
            })

    if spike_months:
        return {
            "is_cyclic": True,
            "spike_months": spike_months,
            "overall_mean": round(overall_mean, 1),
            "pattern": f"Peaks in month(s): {[s['month'] for s in spike_months]}"
        }

    return {"is_cyclic": False}
```

### Gradual Audience Targeting Shift Detection

```python
def detect_audience_shift(country_code, theme_name, window_months=6):
    """
    Detect when a country is gradually shifting its messaging from one
    audience to another on a specific theme.
    
    Example: Iran increases Arabic-language coverage of Gulf security by 
    5% per month over 6 months while English coverage stays flat.
    """
    # Monthly domestic vs international ratio for this theme
    monthly = db.query("""
        SELECT DATE_TRUNC('month', date) as month,
               SUM(CASE WHEN audience_type = 'DOMESTIC' THEN 1 ELSE 0 END) as domestic,
               SUM(CASE WHEN audience_type = 'INTERNATIONAL' THEN 1 ELSE 0 END) as intl
        FROM articles a
        JOIN article_themes at ON a.id = at.article_id
        WHERE a.source_country = :country
          AND at.theme = :theme
          AND date >= CURRENT_DATE - INTERVAL ':months months'
        GROUP BY DATE_TRUNC('month', date)
        ORDER BY month
    """, country=country_code, theme=theme_name, months=window_months)

    if len(monthly) < 3:
        return None

    # Calculate domestic:international ratio trend
    ratios = []
    for m in monthly:
        total = m.domestic + m.intl
        if total > 0:
            intl_share = m.intl / total
            ratios.append(intl_share)

    if len(ratios) < 3:
        return None

    # Linear regression on international share over time
    slope = np.polyfit(range(len(ratios)), ratios, 1)[0]

    if abs(slope) > 0.03:  # >3% shift per month
        direction = "toward INTERNATIONAL" if slope > 0 else "toward DOMESTIC"
        return {
            "shift_detected": True,
            "direction": direction,
            "slope_per_month": round(slope * 100, 1),  # As percentage
            "current_intl_share": round(ratios[-1] * 100, 1),
            "initial_intl_share": round(ratios[0] * 100, 1),
            "detail": f"International share shifted from {ratios[0]*100:.0f}% to {ratios[-1]*100:.0f}% over {len(ratios)} months"
        }

    return {"shift_detected": False}
```

---

## Algorithm 8: Silence Detection

### The Problem

A country or outlet going unusually quiet is as significant as a surge. Detect meaningful silence, not just weekends.

```python
def detect_silence(country_code, audience_type, date):
    """
    Detect unusual silence from a country's state media.
    Accounts for weekday/weekend patterns and known holidays.
    """
    dev = calculate_deviation(country_code, audience_type, date)

    if dev["ratio"] > 0.5:
        return None  # Not quiet enough to flag

    # Check if this is a known pattern (weekend, holiday)
    day_of_week = date.weekday()
    is_weekend = day_of_week >= 5

    if is_weekend:
        # Compare against weekend baseline specifically
        weekend_baseline = calculate_weekend_baseline(country_code, audience_type, date)
        if dev["today_count"] >= weekend_baseline["mean"] * 0.5:
            return None  # Normal weekend reduction

    # Check against known holidays for this country
    if is_national_holiday(country_code, date):
        return None  # Holiday — expected reduction

    # Genuine silence detected
    severity = "NOTABLE" if dev["ratio"] < 0.5 else "MINOR"
    if dev["ratio"] < 0.2:
        severity = "SIGNIFICANT"
    if dev["ratio"] == 0:
        severity = "TOTAL"  # Zero articles — extremely unusual

    return {
        "country": country_code,
        "audience_type": audience_type,
        "severity": severity,
        "ratio": dev["ratio"],
        "z_score": dev["z_score"],
        "today_count": dev["today_count"],
        "baseline_mean": dev["baseline_mean"],
        "detail": f"{country_code} {audience_type} output at {dev['ratio']:.0%} of baseline"
    }


def detect_topic_silence(country_code, theme_name, days=7):
    """
    Detect when a country STOPS covering a theme it normally covers.
    More subtle than overall silence — the country is still active,
    but a specific narrative disappeared.
    """
    # Theme frequency in last 7 days
    recent = db.query("""
        SELECT COUNT(*) as count
        FROM articles a
        JOIN article_themes at ON a.id = at.article_id
        WHERE a.source_country = :country
          AND at.theme = :theme
          AND a.date >= CURRENT_DATE - :days
    """, country=country_code, theme=theme_name, days=days)

    # Theme frequency in 30 days before that
    historical = db.query("""
        SELECT COUNT(*) / 30.0 as daily_avg
        FROM articles a
        JOIN article_themes at ON a.id = at.article_id
        WHERE a.source_country = :country
          AND at.theme = :theme
          AND a.date BETWEEN CURRENT_DATE - 37 AND CURRENT_DATE - 8
    """, country=country_code, theme=theme_name)

    recent_daily = recent.count / days
    historical_daily = historical.daily_avg

    if historical_daily > 2.0 and recent_daily < historical_daily * 0.2:
        return {
            "topic_silence": True,
            "theme": theme_name,
            "country": country_code,
            "recent_daily_avg": round(recent_daily, 1),
            "historical_daily_avg": round(historical_daily, 1),
            "drop_ratio": round(recent_daily / historical_daily, 2) if historical_daily > 0 else 0,
            "detail": f"{country_code} dropped '{theme_name}' from {historical_daily:.0f}/day to {recent_daily:.0f}/day"
        }

    return None
```

---

## Algorithm 9: Gray Source Confidence Scoring (Phase 2, Grok)

```python
def score_gray_source(account, known_state_accounts, time_window_days=30):
    """
    Score how likely an X/Twitter account is affiliated with state media.
    Uses behavioral signals, not content analysis.
    
    Range: 0.0 (probably independent) to 1.0 (almost certainly state-affiliated)
    """
    score = 0.0
    signals = []

    # Signal 1: Amplification timing
    # How quickly does this account share state media content after publication?
    avg_delay = calculate_avg_amplification_delay(account, known_state_accounts, time_window_days)
    if avg_delay and avg_delay < timedelta(hours=2):
        score += 0.25
        signals.append(f"Avg amplification delay: {avg_delay}")

    # Signal 2: Source concentration
    # What % of this account's shares/retweets come from state media?
    state_share_pct = calculate_state_media_share_percentage(account, known_state_accounts)
    if state_share_pct > 0.50:
        score += 0.25
        signals.append(f"{state_share_pct:.0%} of shares are state media")
    elif state_share_pct > 0.30:
        score += 0.15

    # Signal 3: Account creation timing
    # Was the account created around the same time as other gray accounts?
    cluster_match = check_creation_date_clustering(account)
    if cluster_match:
        score += 0.15
        signals.append(f"Created in cluster with {cluster_match['cluster_size']} other accounts")

    # Signal 4: Posting cadence
    # Does the account post on a schedule consistent with a work shift?
    cadence = analyze_posting_cadence(account)
    if cadence["is_business_hours"] and cadence["timezone_matches_country"]:
        score += 0.10
        signals.append(f"Posts during business hours in {cadence['likely_timezone']}")

    # Signal 5: Network overlap
    # Does this account follow/interact with known state accounts disproportionately?
    network_overlap = calculate_network_overlap(account, known_state_accounts)
    if network_overlap > 0.40:
        score += 0.15
        signals.append(f"Network overlap: {network_overlap:.0%} with known state accounts")

    # Signal 6: Content language patterns
    # Does the account use phrasing typical of translated/institutional content?
    # (This is the weakest signal — flagged but low weight)
    if detect_institutional_language(account):
        score += 0.05
        signals.append("Institutional language patterns detected")

    confidence_label = "LOW"
    if score >= 0.60:
        confidence_label = "HIGH"
    elif score >= 0.35:
        confidence_label = "MEDIUM"

    return {
        "account": account.handle,
        "score": round(min(score, 1.0), 2),
        "confidence": confidence_label,
        "signals": signals,
        "likely_country": infer_country_affiliation(account, known_state_accounts)
    }
```

---

## Algorithm 10: Weekly/Monthly Rollup Generation

```python
def generate_weekly_digest(week_end_date):
    """
    Aggregate 7 daily snapshots into a weekly intelligence digest.
    """
    week_start = week_end_date - timedelta(days=6)

    # Top themes of the week
    theme_counts = db.query("""
        SELECT theme, SUM(count) as total,
               (SELECT SUM(count) FROM theme_daily WHERE theme = t.theme 
                AND date BETWEEN :prev_start AND :prev_end) as prev_week
        FROM theme_daily t
        WHERE date BETWEEN :start AND :end
        GROUP BY theme
        ORDER BY total DESC
        LIMIT 20
    """, start=week_start, end=week_end_date,
       prev_start=week_start - timedelta(days=7),
       prev_end=week_start - timedelta(days=1))

    themes = []
    for t in theme_counts:
        delta = ((t.total - t.prev_week) / t.prev_week * 100) if t.prev_week > 0 else None
        themes.append({
            "theme": t.theme,
            "count": t.total,
            "prev_week": t.prev_week,
            "change_pct": round(delta, 1) if delta else "NEW",
            "direction": "UP" if delta and delta > 10 else "DOWN" if delta and delta < -10 else "STABLE"
        })

    # Biggest country spikes
    spikes = db.query("""
        SELECT country, MAX(deviation_ratio) as peak_ratio, 
               date as peak_date, audience_type
        FROM daily_deviations
        WHERE date BETWEEN :start AND :end
          AND deviation_ratio > 2.0
        GROUP BY country, audience_type
        ORDER BY peak_ratio DESC
        LIMIT 10
    """, start=week_start, end=week_end_date)

    # Significant contradictions
    contradictions = db.query("""
        SELECT * FROM contradictions
        WHERE date BETWEEN :start AND :end
          AND contradiction_score >= 0.40
        ORDER BY contradiction_score DESC
        LIMIT 10
    """, start=week_start, end=week_end_date)

    # Silence signals
    silences = db.query("""
        SELECT * FROM silence_events
        WHERE date BETWEEN :start AND :end
          AND severity IN ('SIGNIFICANT', 'TOTAL')
        ORDER BY date
    """, start=week_start, end=week_end_date)

    # Coordination events
    coordinations = db.query("""
        SELECT * FROM coordination_events
        WHERE date BETWEEN :start AND :end
          AND coordination_score >= 0.30
        ORDER BY coordination_score DESC
        LIMIT 5
    """, start=week_start, end=week_end_date)

    return {
        "week": f"{week_start} to {week_end_date}",
        "top_themes": themes,
        "biggest_spikes": spikes,
        "contradictions": contradictions,
        "silences": silences,
        "coordinations": coordinations,
        "total_articles_ingested": get_weekly_article_count(week_start, week_end_date),
        "countries_active": get_active_country_count(week_start, week_end_date)
    }
```

---

## Database Schema (Core Tables)

```sql
-- Articles (main table)
CREATE TABLE articles (
    id              BIGSERIAL PRIMARY KEY,
    url             TEXT NOT NULL UNIQUE,
    title_original  TEXT,
    title_english   TEXT,
    source_domain   TEXT NOT NULL,
    source_country  CHAR(2) NOT NULL,      -- FIPS code
    source_language CHAR(3),                -- ISO 639-3
    audience_type   TEXT NOT NULL,           -- DOMESTIC, INTERNATIONAL, DIASPORA
    audience_confidence FLOAT,
    tone            FLOAT,                  -- GDELT tone score
    pub_date        TIMESTAMPTZ NOT NULL,
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),
    full_text       TEXT,                   -- NULL for metadata-only records
    entities        JSONB,                  -- [{name, type, salience}]
    gdelt_themes    TEXT[]                  -- GDELT CAMEO theme codes
);

-- Article themes (our custom taxonomy)
CREATE TABLE article_themes (
    article_id  BIGINT REFERENCES articles(id),
    theme       TEXT NOT NULL,
    confidence  FLOAT NOT NULL,
    PRIMARY KEY (article_id, theme)
);

-- Daily snapshots (tiny, kept forever)
CREATE TABLE daily_snapshots (
    date                DATE PRIMARY KEY,
    total_articles      INT,
    countries_active    INT,
    country_activity    JSONB,   -- {country: {domestic: N, international: N, ratio: N}}
    theme_counts        JSONB,   -- {theme: {count: N, top_countries: [...]}}
    contradictions      JSONB,   -- [{country, score, details}]
    coordinations       JSONB,   -- [{theme, countries, score}]
    silences            JSONB    -- [{country, audience_type, severity}]
);

-- Country baselines (recalculated weekly)
CREATE TABLE country_baselines (
    country         CHAR(2),
    audience_type   TEXT,
    theme           TEXT DEFAULT '__ALL__',  -- '__ALL__' for overall, or specific theme
    mean_30d        FLOAT,
    std_30d         FLOAT,
    updated_at      TIMESTAMPTZ,
    PRIMARY KEY (country, audience_type, theme)
);

-- Source classification (lookup table, maintained manually + algorithmically)
CREATE TABLE source_classification (
    domain          TEXT PRIMARY KEY,
    country         CHAR(2),
    audience_type   TEXT,          -- DOMESTIC, INTERNATIONAL
    outlet_name     TEXT,
    outlet_type     TEXT,          -- NEWS_AGENCY, TV, RADIO, NEWSPAPER, DIGITAL
    languages       TEXT[],
    confidence      FLOAT,
    is_state_owned  BOOLEAN,
    is_state_aligned BOOLEAN,
    notes           TEXT
);

-- Coordination events
CREATE TABLE coordination_events (
    id              SERIAL PRIMARY KEY,
    date            DATE,
    theme           TEXT,
    countries       TEXT[],
    score           FLOAT,
    details         JSONB
);

-- Contradiction events
CREATE TABLE contradiction_events (
    id              SERIAL PRIMARY KEY,
    date            DATE,
    country         CHAR(2),
    event_cluster_id TEXT,
    score           FLOAT,
    domestic_count  INT,
    intl_count      INT,
    details         JSONB
);

-- User accounts
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    is_mil          BOOLEAN DEFAULT FALSE,
    is_paid         BOOLEAN DEFAULT FALSE,
    stripe_customer_id TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_articles_country_date ON articles(source_country, pub_date);
CREATE INDEX idx_articles_audience_date ON articles(audience_type, pub_date);
CREATE INDEX idx_articles_domain ON articles(source_domain);
CREATE INDEX idx_themes_theme ON article_themes(theme);
```

---

## Related Files

- [[SalientSignal-Project]] — Product vision, features, design direction
- [[SalientSignal-Source-Database]] — 151+ countries, 606+ outlets, all APIs
- [[SalientSignal-Technical-Spec]] — Verified numbers, daily pipeline, cost breakdown
- [[SalientSignal-User-Stories]] — Six user archetypes, conversion triggers, feature gaps
