---
aliases:
  - SalientSignal Sources
  - Source Database
tags:
  - apex
  - business
  - app
  - io
  - media-analysis
  - osint
created: 2026-04-09
---

# SalientSignal — Source Database

> **Master reference for every API, data platform, state media outlet, and social media discovery method identified through research. No country discounted by size.**

---

## Part 1: APIs & Data Platforms

### Tier 1 — Core Pipeline APIs (Start Here)

| API | What It Does | Coverage | Pricing | Priority |
|-----|-------------|----------|---------|----------|
| **Grok API (xAI)** | X/Twitter search + LLM analysis. Native X data access no other model has. Gray source discovery. 2M token context window. | All public X accounts globally | Grok 4.1 Fast: $0.20/M input, $0.50/M output. X Search: $5/1,000 calls (~$0.025/query) | CRITICAL |
| **Claude API (Anthropic)** | SCAME analysis engine. Debrief paragraph generation. Translation + analysis in single call. | N/A (analysis layer) | Sonnet 4.6: $3/$15 per M tokens. Haiku 4.5 for high-volume. | CRITICAL |
| **GDELT Project** | Monitors print/broadcast/web news in 100+ languages from every country. Updates every 15 min. 2B+ events since 1979. Translates 65 languages in real-time. Highest-resolution inventory of non-Western media systems. | Global — every country | **FREE** | CRITICAL |
| **GDELT DOC 2.0 API** | Full-text search across all monitored articles. Theme extraction, tone analysis, entity detection. | Global | **FREE** | CRITICAL |
| **GDELT GEO 2.0 API** | Geographic article search. RSS, JSONFeed, CSV output. Rolling 15-min window. | Global | **FREE** | CRITICAL |
| **Media Cloud** | Open-source media analysis. 2B stories indexed. Harvard/UMass/Northeastern consortium. API + web interface. | Global | **FREE** (open source) | HIGH |
| **GDELT Cloud** | Hourly-updated global news event data + AI tools. API access since Jan 2025. | Global | TBD (newer service) | HIGH |

### Tier 2 — News Aggregation APIs

| API | Coverage | Pricing | Notes |
|-----|----------|---------|-------|
| **NewsAPI.ai (Event Registry)** | 150,000+ global sources, 60+ languages. Entity recognition, event clustering, sentiment, publisher metadata. | $500+/mo | Best enriched metadata. Good for event-level cross-source comparison. |
| **GNews** | 60,000+ sources, 22 languages via Google News | Free: 100 req/day. Paid: from $84/mo | Quick global coverage. Good for validation. |
| **Webz.io** | 170+ languages, every geographic territory. 30-day historical. | $500+/mo | Strongest language coverage of any news API. |
| **NewsAPI.org** | 80,000+ sources | Free: 100 req/day. Paid: $200-500/mo | Limited to 30 days historical. Good for testing. |
| **NewsData.io** | Global news, multiple languages | Free tier available | Budget alternative for prototyping. |
| **Twingly** | 170,000 news outlets, 100+ countries. 3M articles/day. Blogs (3M active), forums (9K), dark web (Telegram, Tor, Discord). | Enterprise pricing | Dark web API is unique — covers Telegram + Tor natively. |

### Tier 3 — Social Media Platform APIs

| Platform | API/Tool | Coverage | Pricing | Notes |
|----------|----------|----------|---------|-------|
| **X/Twitter** | Official API v2 + Grok API | Global. Gray badge = government accounts | X Basic: $200/mo (10K tweets/mo). Pro: $5K/mo. Grok: see Tier 1 | Gray badge programmatically identifies government accounts |
| **Telegram** | Telethon (Python, MTProto) | Global. Massive for Russia, Iran, Central Asia | **FREE** (open source) | Real-time channel monitoring, message scraping, media download |
| **Telegram** | Pyrogram (Python) | Same coverage | **FREE** (open source) | Modern alternative to Telethon |
| **YouTube** | YouTube Data API v3 | Global | Free: 10,000 units/day (~100 lookups) | State media YouTube channels. TranscriptAPI for captions. |
| **VK (VKontakte)** | VK API | Russia (95M users) | **FREE** with auth | Russian domestic vs. export narrative comparison |
| **Weibo** | Weibo API + Piloterr Search | China domestic | Piloterr: paid. Direct: free (Chinese registration) | PRC domestic vs. international narrative comparison |
| **TikTok** | TikTok Research API | Global | Academic access required | State media TikTok growing rapidly |
| **Meta (FB/IG)** | Meta Content Library | Global | Academic only. SOMAR: $371/mo + $1K setup (Jan 2026+) | Replaces CrowdTangle. Very restricted access. |
| **Reddit** | Reddit API | Global | Free tier available | State media amplification monitoring |

### Tier 4 — Translation APIs

| API | Languages | Pricing | Best For |
|-----|-----------|---------|----------|
| **Google Cloud Translation** | 130+ languages | $20/M chars. First 500K/mo free. LLM mode: $10+$10/M | Best coverage. Use for volume translation. |
| **DeepL** | 33 languages | Free: 500K chars/mo. Pro: $5.49/mo + $25/M chars | Highest quality for European + major Asian languages |
| **Claude API** | ~100+ languages | Already in pipeline | Translate + analyze in single call = cost efficient |

### Tier 5 — Specialized Analysis & OSINT

| Tool | What It Does | Pricing | URL |
|------|-------------|---------|-----|
| **State Media Monitor** | World's most complete state media database. 606 outlets, 151+ countries. Funding/ownership/autonomy classification. | **FREE** | statemediamonitor.com |
| **EUvsDisinfo** | 7,000+ pro-Kremlin disinfo cases. API available (euvsdisinfoR). | **FREE** | euvsdisinfo.eu |
| **Hamilton 2.0** (ASD/ISD) | Russian/Chinese/Iranian state media narrative tracking. X, Telegram, YouTube, FB, IG, TikTok, MFA transcripts. 30-day rolling. | **FREE** | securingdemocracy.isd.ngo |
| **Botometer** (Indiana U) | Bot detection scoring for X accounts. API access. | **FREE** | botometer.osome.iu.edu |
| **Bot Sentinel** | Coordinated inauthentic behavior detection. AI-powered. | Relaunching May 2026 | botsentinel.com |
| **Perspective API** (Jigsaw) | Toxicity/manipulation scoring. 18 languages. 500M+ req/day. | **FREE** | perspectiveapi.com |
| **Wayback Machine API** | Historical web snapshots. 1T+ pages. CDX search. | **FREE** | archive.org |

### Tier 6 — Web Scraping Infrastructure

| Tool | Use Case | Pricing |
|------|----------|---------|
| **Trafilatura** | Article text extraction. F1=0.945. Best across German/Greek/English/Chinese. | **FREE** (Python) |
| **Newspaper4k** | Article extraction. 80+ languages. Auto-detection. Successor to newspaper3k. | **FREE** (Python) |
| **Playwright** | Headless browser for JS-heavy sites. Chromium/Firefox/WebKit. | **FREE** (Python/Node) |
| **Scrapy + Playwright** | Production-grade crawling + JS rendering. | **FREE** (Python) |
| **Apify** | Cloud scraping. 23,000+ actors. Twitter/YouTube/Telegram actors. | Free $5 credit. Starter $29/mo |
| **Bright Data** | 72M+ IPs. Anti-bot bypass. Social platform scraping API. | Enterprise pricing |

### Tier 7 — Enterprise Social Listening (Scale Phase)

| Platform | Coverage | Pricing | Differentiator |
|----------|----------|---------|----------------|
| **Talkwalker** | X Firehose. 150M websites. 30 social channels. 187 languages. | From $9,600/yr | Most languages |
| **Meltwater** | 270,000+ news sources. 15+ social. 500M+ pieces/day. | From $6,000-15,000/yr | Most news sources |
| **Brandwatch** | 1.7T historical conversations (2010+). X/Tumblr/Reddit firehoses. | From $1,000/mo | Best historical depth |
| **Sprinklr** | Douyin + Sina Weibo firehose. Strong APAC. | Enterprise | Only platform with native Chinese social firehose |

---

## Part 2: Country-by-Country State Media Database

> **Sources:** Wikipedia "List of news agencies" + "List of state media by country" + State Media Monitor (606 outlets, 151 countries) + OANA membership roster + regional agency associations.
>
> **(S)** = state-owned/controlled. Every country listed regardless of size. No source discounted.

---

### EAST ASIA & PACIFIC

| Country | State News Agency | State TV/Radio | State-Aligned / Notable | English Service |
|---------|-------------------|----------------|------------------------|-----------------|
| **China (PRC)** | Xinhua **(S)**, China News Service **(S)** | CCTV (17+ ch) **(S)**, CGTN (EN/FR/ES/RU/AR/Doc) **(S)**, CRI **(S)**, CNR (17 ch) **(S)**, CETV **(S)** | Global Times, China Daily, People's Daily, Caixin, SCMP, Guancha | CGTN, China Daily, Global Times, Xinhua |
| **Japan** | Kyodo News, Jiji Press | NHK **(S)** — NHK World-Japan | | NHK World-Japan |
| **South Korea** | Yonhap News | KBS **(S)** — KBS1, KBS2, KBS World + 6 radio | Newsis | KBS World |
| **North Korea** | KCNA **(S)** | KCTV **(S)**, KCBS **(S)**, Voice of Korea **(S)** | Rodong Sinmun, Naenara, Uriminzokkiri | KCNA English, VOK |
| **Taiwan** | Central News Agency **(S)** | PTS (public) | Focus Taiwan | Focus Taiwan, Taiwan Today |
| **Mongolia** | Montsame **(S)** | MNB **(S)** | | Montsame English |
| **Vietnam** | VNA **(S)** | VTV **(S)** (9+ ch), VOV **(S)** (6+ ch) | | VTV World, VOV English |
| **Laos** | Lao News Agency **(S)** | LNTV **(S)**, LNR **(S)** | Vientiane Times | |
| **Cambodia** | Agence Kampuchea Press **(S)** | TVK **(S)**, TVK2 | Fresh News (aligned) | |
| **Myanmar** | Myanmar News Agency **(S)** | MRTV **(S)** | Global New Light of Myanmar | |
| **Thailand** | Thai News Agency **(S)** | Thai PBS **(S)**, NBT **(S)**, MCOT **(S)**, Royal Thai Army Radio/TV **(S)** | | NBT World |
| **Philippines** | Philippine News Agency **(S)** | PTV **(S)**, PBS **(S)**, RPN, IBC | | PNA English |
| **Malaysia** | Bernama **(S)** | RTM **(S)** — TV1, TV2, TV6, Okey + 20+ radio | | Bernama English |
| **Singapore** | — | Mediacorp **(S)** — Ch 5, 8, U, CNA, Suria, Vasantham + 10+ radio | | CNA |
| **Indonesia** | Antara **(S)** | TVRI **(S)**, RRI **(S)** | | Antara English |
| **Brunei** | — | RTB **(S)** — 3 TV + 5 radio | | |
| **East Timor** | Tatoli | RTTL **(S)** | | |
| **Papua New Guinea** | — | NBC PNG **(S)** | | |
| **Fiji** | Pacnews (regional) | Fiji Broadcasting Corp **(S)** | | |
| **Tonga** | — | Tonga Broadcasting Commission **(S)** | | |
| **Samoa** | — | 2AP Radio **(S)** | | |
| **Solomon Islands** | — | SIBC **(S)** | | |
| **Vanuatu** | — | VBTC **(S)** | | |
| **Palau** | — | Palau National Radio **(S)** | | |
| **Marshall Islands** | — | V7AB Radio **(S)** | | |
| **Micronesia** | — | FSM Radio **(S)** | | |
| **Kiribati** | — | Radio Kiribati **(S)** | | |
| **Nauru** | — | Nauru TV **(S)** | | |
| **Tuvalu** | — | Radio Tuvalu **(S)** | | |

### SOUTH ASIA

| Country | State News Agency | State TV/Radio | State-Aligned / Notable | English Service |
|---------|-------------------|----------------|------------------------|-----------------|
| **India** | PTI, UNI, ANI, IANS | Doordarshan **(S)** (30+ ch), All India Radio **(S)**, Sansad TV **(S)** | WION (aligned) | DD India, AIR English, WION |
| **Pakistan** | APP **(S)**, PPI | PTV **(S)** (10+ ch), Radio Pakistan **(S)** | Dawn, Geo News | PTV World, PTV Global |
| **Bangladesh** | BSS **(S)**, UNB | BTV **(S)** (4 ch), Bangladesh Betar **(S)**, Sangsad TV **(S)** | | |
| **Sri Lanka** | Lankapuvath **(S)** | Rupavahini **(S)**, SLBC **(S)** (15+ stations), ITN **(S)** | | Channel Eye |
| **Nepal** | RSS **(S)** | NTV **(S)** (5 ch), Radio Nepal **(S)** | | |
| **Bhutan** | Bhutan News Service | BBS **(S)** (3 TV + radio) | Kuensel **(S)** | |
| **Maldives** | — | PSM **(S)** | | |
| **Afghanistan** | Bakhtar **(S)** | RTA **(S)** | Khaama Press, Pajhwok | |

### CENTRAL ASIA

| Country | State News Agency | State TV/Radio | State-Aligned / Notable | English Service |
|---------|-------------------|----------------|------------------------|-----------------|
| **Kazakhstan** | Kazinform **(S)** | Qazaqstan TV **(S)**, Khabar **(S)** | Astana Times | Kazinform, Astana Times |
| **Uzbekistan** | UzA **(S)** | NTRK **(S)** | | UzA English |
| **Turkmenistan** | TDH **(S)** | Turkmenistan TV **(S)** | Chronicles of Turkmenistan (exile) | |
| **Tajikistan** | Khovar **(S)** | Televizioni Tojikiston **(S)** | Asia-Plus | Khovar English |
| **Kyrgyzstan** | Kabar **(S)** | KTRK **(S)** | AKIpress | |

### MIDDLE EAST & NORTH AFRICA

| Country | State News Agency | State TV/Radio | State-Aligned / Notable | English Service |
|---------|-------------------|----------------|------------------------|-----------------|
| **Iran** | IRNA **(S)**, Fars **(S)**, Tasnim **(S)**, ISNA **(S)**, Mehr **(S)**, ILNA **(S)** | IRIB **(S)** — Press TV, Al Alam, Sahar TV, iFilm | Al Mayadeen (aligned) | Press TV |
| **Iraq** | NINA **(S)** | Al Iraqiya **(S)**, Alahad TV | Kurdistan 24 (KRG) | |
| **Syria** | SANA **(S)** | Syrian TV **(S)** | Hawar News (SDF) | SANA English |
| **Lebanon** | — | Tele Liban **(S)**, Radio Lebanon **(S)** | Al Manar (Hezbollah), Al Mayadeen | |
| **Jordan** | Petra/JNA **(S)** | JRTV **(S)**, Al-Mamlaka TV | | |
| **Saudi Arabia** | SPA **(S)** | SBA **(S)** — Al Ekhbariya, AlRiyadiya, Quran TV, Sunnah TV | Al Arabiya (Saudi-aligned), Arab News | Al Arabiya, Arab News |
| **UAE** | WAM **(S)** | Abu Dhabi Media **(S)** (10+ ch), Dubai Media **(S)** (10+ ch) | The National, Sky News Arabia | The National, WAM English |
| **Qatar** | QNA **(S)** | QGBTC **(S)**, Al Jazeera Media Network **(S)** — AJ Arabic, AJ English, AJ Balkans, AJ Mubasher | AJ+, Doha News | Al Jazeera English, AJ+ |
| **Bahrain** | BNA **(S)** | BRTC **(S)** | | BNA English |
| **Kuwait** | KUNA **(S)** | Kuwait TV **(S)** (8+ ch) | | KUNA English |
| **Oman** | ONA **(S)** | Oman TV **(S)** | Times of Oman | ONA English |
| **Yemen** | Saba **(S)** | Yemen TV **(S)** | Al-Masira (Houthi) | |
| **Egypt** | MENA **(S)** | ERTU **(S)** — Nile TV, Nile News | Al-Ahram **(S)**, CBC Egypt | Nile TV Intl, Ahram Online |
| **Libya** | — | LJBC (defunct) | Libya Observer, Libya Herald | |
| **Tunisia** | TAP **(S)** | TVT **(S)** (2 ch), Radio Tunisienne **(S)** (5+ stations) | | |
| **Algeria** | APS **(S)** | EPTV **(S)**, Radio Algeria **(S)** | El Moudjahid **(S)** | APS English |
| **Morocco** | MAP **(S)** | SNRT **(S)** (10+ TV + radio), Medi 1 TV | | MAP English |
| **Israel** | — | Kan **(S)** | | i24NEWS |
| **Palestine** | WAFA **(S)** | PBC **(S)** | Ma'an News | WAFA English |

### SUB-SAHARAN AFRICA

| Country | State News Agency | State TV/Radio | Notable |
|---------|-------------------|----------------|---------|
| **Nigeria** | NAN **(S)** | NTA **(S)**, FRCN **(S)** | |
| **South Africa** | — | SABC **(S)** (8 TV + 18 radio) | Independent Media |
| **Kenya** | KNA **(S)** | KBC **(S)** | |
| **Ethiopia** | ENA **(S)** | EBC **(S)** | Fana Broadcasting (ruling party) |
| **Eritrea** | — | Eri-TV **(S)** | Shabait **(S)** |
| **Somalia** | — | SNTV **(S)**, Radio Mogadishu **(S)** | |
| **Sudan** | SUNA **(S)** | Sudan TV **(S)** | |
| **South Sudan** | SSNA **(S)** | SSBC **(S)** | |
| **DRC** | — | RTNC **(S)** (2 ch) | |
| **Congo (Republic)** | — | Tele Congo **(S)** | |
| **Rwanda** | — | RBA **(S)** | KT Press, New Times (aligned) |
| **Burundi** | — | RTNB **(S)** | |
| **Uganda** | — | UBC **(S)** | |
| **Tanzania** | — | TBC **(S)** | |
| **Mozambique** | — | TVM **(S)**, Radio Mocambique **(S)** | |
| **Angola** | ANGOP **(S)** | TPA **(S)**, RNA **(S)** | |
| **Zimbabwe** | — | ZBC **(S)** | The Herald **(S)** |
| **Zambia** | — | ZNBC **(S)** | |
| **Malawi** | MANA **(S)** | MBC **(S)** | |
| **Madagascar** | — | TVM **(S)** | |
| **Cameroon** | — | CRTV **(S)** | |
| **Ghana** | GNA **(S)** | GBC **(S)** | |
| **Senegal** | — | RTS **(S)** (2 TV) | |
| **Mali** | — | ORTM **(S)** | |
| **Burkina Faso** | — | RTB **(S)** | |
| **Niger** | — | ORTN **(S)** | |
| **Chad** | — | Tele Tchad **(S)**, RNT **(S)** | |
| **CAR** | — | TVCA **(S)** | |
| **Gabon** | — | RTG **(S)** | |
| **Equatorial Guinea** | — | TVGE **(S)** | |
| **Ivory Coast** | — | RTI **(S)** | |
| **Guinea** | — | RTG **(S)** | |
| **Sierra Leone** | — | SLBC **(S)** | |
| **Liberia** | — | LBS **(S)** | |
| **Togo** | — | Television Togolaise **(S)** | |
| **Benin** | ABP **(S)** | ORTB **(S)** | |
| **Mauritania** | — | TV de Mauritanie **(S)** | |
| **Djibouti** | — | RTD **(S)** | |
| **Comoros** | — | National Radio **(S)** | |
| **Seychelles** | SNA **(S)** | SBC **(S)** | |
| **Mauritius** | — | MBC **(S)** | |
| **Cabo Verde** | Inforpress **(S)** | RTC **(S)** | |
| **Sao Tome** | STP-Press | TVS **(S)** | |
| **Gambia** | — | GRTS **(S)** | |
| **Guinea-Bissau** | — | GBTV **(S)** | |
| **Lesotho** | — | Lesotho TV **(S)** | |
| **Eswatini** | — | EBIS **(S)** | |
| **Botswana** | — | BTV **(S)**, Radio Botswana **(S)** | |
| **Namibia** | NamPA **(S)** | NBC **(S)** | |

### EUROPE (non-FVEY)

| Country | State News Agency | State TV/Radio | State-Aligned / Notable | English Service |
|---------|-------------------|----------------|------------------------|-----------------|
| **Russia** | TASS **(S)**, Rossiya Segodnya/RIA Novosti **(S)**, Interfax | VGTRK **(S)** — Rossiya 1/24/K/Culture, Radio Rossii, Vesti FM. RT **(S)** — EN/ES/FR/AR/DE. Sputnik **(S)** multi-language | Tsargrad, Regnum, NewsFront, SouthFront. Telegram: Rybar, WarGonzo, Readovka | RT, Sputnik, TASS English |
| **Belarus** | BelTA **(S)** | Belteleradio **(S)** — Belarus 1, ONT, STV | BelaPAN | BelTA English |
| **Ukraine** | Ukrinform **(S)** | UA:PBC **(S)** | UNIAN, Ukrainian News | Ukrinform English |
| **Moldova** | Moldpres **(S)** | TRM **(S)** | | |
| **Georgia** | — | GPB **(S)** | | |
| **Armenia** | Armenpress **(S)** | AMPTV **(S)** | PanARMENIAN.Net | Armenpress English |
| **Azerbaijan** | AZERTAC **(S)**, Trend | ITV **(S)** | | AZERTAC English |
| **Turkey** | Anadolu Agency **(S)** | TRT **(S)** — TRT 1, TRT World, Haber, Arabi | Daily Sabah (aligned) | TRT World |
| **Serbia** | — | RTS **(S)** | Beta | |
| **Bosnia** | FENA **(S)** | BHRT **(S)** | | |
| **Montenegro** | MINA **(S)** | RTCG **(S)** | | |
| **North Macedonia** | MIA | MRT **(S)** | | |
| **Kosovo** | — | RTK **(S)** | Kosova Press | |
| **Albania** | ATA **(S)** | RTSH **(S)** | | |
| **Croatia** | HINA **(S)** | HRT **(S)** | | |
| **Slovenia** | STA **(S)** | RTVSLO **(S)** | | |
| **Hungary** | MTI **(S)** | MTVA **(S)** — M1, M2, M4, M5, Duna TV + 3 radio | | |
| **Poland** | PAP **(S)** | TVP **(S)**, Polskie Radio **(S)** | | TVP World |
| **Czech Republic** | CTK **(S)** | CT (public), CRo (public) | | |
| **Slovakia** | TASR **(S)** | RTVS **(S)** | | |
| **Romania** | AGERPRES **(S)** | TVR **(S)**, SRR **(S)** | Mediafax, Rador | |
| **Bulgaria** | BTA **(S)** | BNT **(S)**, BNR **(S)** | | |
| **Greece** | ANA-MPA **(S)** | ERT **(S)** | | |
| **Cyprus** | CNA **(S)** | CyBC **(S)** | | |
| **Italy** | — | RAI **(S)** | ANSA | |
| **Spain** | EFE **(S)** | RTVE **(S)** | | |
| **Portugal** | Lusa **(S)** | RTP **(S)** | | |
| **France** | AFP **(S)** | France Televisions **(S)**, Radio France **(S)**, France 24 **(S)**, RFI **(S)**, Monte Carlo Doualiya **(S)** | | France 24, RFI English |
| **Germany** | — | ARD/ZDF (public), Deutsche Welle **(S)** — DW EN/AR/ES | DPA | DW English |
| **Netherlands** | — | NPO (public) | ANP | |
| **Belgium** | — | VRT (Flemish), RTBF (French) | Belga | |
| **Switzerland** | — | SRG SSR — SRF, RTS, RSI, RTR | SDA/ATS | SWI swissinfo.ch |
| **Austria** | — | ORF (public) | APA | |
| **Ireland** | — | RTE **(S)** | | |
| **Denmark** | — | DR (public) | Ritzau | |
| **Norway** | — | NRK (public) | NTB | |
| **Sweden** | — | SVT (public), SR (public) | TT **(S)** | |
| **Finland** | — | Yle (public) | STT **(S)** | |
| **Iceland** | — | RUV **(S)** | | |
| **Estonia** | — | ERR (public) | BNS | |
| **Latvia** | LETA **(S)** | LSM (public) | | |
| **Lithuania** | ELTA **(S)** | LRT (public) | | |
| **Malta** | — | PBS Malta **(S)** | | |
| **San Marino** | — | RTV San Marino **(S)** | | |
| **Andorra** | — | RTVA **(S)** | | |
| **Vatican** | — | Vatican Radio **(S)**, Vatican News **(S)** | Agenzia Fides | Vatican News English |

### LATIN AMERICA & CARIBBEAN

| Country | State News Agency | State TV/Radio | State-Aligned / Notable | English Service |
|---------|-------------------|----------------|------------------------|-----------------|
| **Mexico** | Notimex **(S)** | SPR **(S)** — Canal Once, Canal Catorce, Canal 22 | | |
| **Guatemala** | — | Guatevision (partial) | | |
| **Honduras** | — | CONATEL **(S)** | | |
| **El Salvador** | — | TVES/Canal 10 **(S)** | | |
| **Nicaragua** | — | Canal 4, 6, TN8, Viva Nicaragua **(S-aligned)**, Radio Nicaragua **(S)** | | |
| **Costa Rica** | — | SINART/Canal 13 **(S)** | | |
| **Panama** | — | SERTV **(S)** | | |
| **Colombia** | — | RTVC **(S)** — Senal Colombia, Canal Institucional + Radio Nacional + 10+ regional | | |
| **Venezuela** | AVN **(S)** | VTV **(S)**, TVes **(S)**, ViVe **(S)**, TeleSUR **(S, multi-country)**, Radio Nacional **(S)** | Correo del Orinoco | TeleSUR English |
| **Ecuador** | — | Ecuador TV **(S)** | | |
| **Peru** | Andina **(S)** | IRTP **(S)** — TV Peru, Radio Nacional | | Andina English |
| **Bolivia** | ABI **(S)** | Bolivia TV **(S)** (2 ch) + 5 radio stations | | |
| **Brazil** | Agencia Brasil **(S)** | EBC **(S)** — TV Brasil, TV Brasil Internacional + radio. Padre Anchieta **(S)** — TV Cultura + 6 ch | | TV Brasil Internacional |
| **Paraguay** | — | Paraguay TV **(S)** (6 ch) + Radio Nacional **(S)** (5 stations) | | |
| **Uruguay** | — | TNU **(S)** (6 ch) + Radio Nacional **(S)** (5 stations) | | |
| **Argentina** | Telam **(S)** | RTA **(S)** — Television Publica, Canal 7, Encuentro, Pakapaka + Radio Nacional (5 stations) | | |
| **Chile** | — | TVN **(S)** — TVN, TV Chile, NTV, 24 Horas | | |
| **Cuba** | Prensa Latina **(S)** | ICRT **(S)** — Cubavision + radio | Granma **(S)** | Prensa Latina English |
| **Dominican Republic** | — | DBC **(S)** | | |
| **Haiti** | — | RTNH **(S)** | | |
| **Jamaica** | — | JIS **(S)** | | |
| **Trinidad & Tobago** | — | CNMG **(S)** | | |
| **Guyana** | — | NCN **(S)** | | |
| **Suriname** | — | STVS **(S)** | | |
| **Belize** | — | Love FM (government-aligned) | | |
| **Bahamas** | — | ZNS **(S)** | | |
| **Barbados** | — | CBC **(S)** | | |

---

## Part 3: Social Media Account Discovery Methods

### Systematic Approaches

**1. X/Twitter Gray Badge Identification**
Gray verified badges = government accounts. X API v2 can filter by verification type. This programmatically identifies every government account on the platform.

**2. Embassy Naming Patterns**
| Country | Pattern | Example |
|---------|---------|---------|
| China | `@ChinaEmb_[Country]` | @ChinaEmb_US, @ChinaEmb_UK |
| Russia | `@Russia_[Country]` or `@RussianEmbassy` | @RussianEmbassy, @Russia_UK |
| Iran | `@Iran_[Country]` | @Iran_UN |
| General | `@[Country]Embassy[Location]` | @IsraelEmbassyUS |

**3. UN Mission Accounts**
- Pattern: `@[Country]UN` or `@[Country]_UN` or `@[Country]MissionUN`
- Complete list: UN Member States directory (193 countries)
- Geneva missions also have separate accounts

**4. Ministry of Foreign Affairs (MFA)**
- Every country's MFA has an official X/Twitter account
- MFA spokesperson accounts (China's wolf warrior diplomats: Zhao Lijian, Hua Chunying, Wang Wenbin, etc.)

**5. Head of State / Government Leader**
- Presidents, PMs, Supreme Leaders with official X accounts
- These set narratives that state media amplifies
- Notable: Modi (most-followed leader), Erdogan, Maduro, Ortega, Lukashenko

**6. Military & Defense Ministry**
- Defense ministry accounts (Russia MoD Telegram is critical)
- IRGC-affiliated accounts (Iran)
- PLA Daily (China)

**7. Grok-Powered Gray Source Discovery**
```
Prompt: "Find X accounts that consistently amplify [RT/Xinhua/Press TV] 
content within 4 hours of publication but are not officially affiliated 
with any government. List account handles, posting patterns, and 
estimated amplification delay."
```

**8. Graph Analysis Method**
1. Start with known state media accounts
2. Map follower/following overlap
3. Identify accounts that retweet >50% from state sources
4. Flag accounts created in clusters (same date ranges)
5. Cross-reference posting times with state media publication times

**9. Bio Keyword Search**
Search X API for accounts with bio terms: "Embassy", "Consulate", "Ministry", "Official", "Government", "Diplomat", "Ambassador", "Mission", "Permanent Representative"

### Key Diplomatic Social Media Ecosystems

| Country | Est. Embassy Accounts | Primary Platform | Notable Pattern |
|---------|----------------------|------------------|-----------------|
| China | 170+ | X, WeChat (domestic) | Wolf warrior diplomats. Most aggressive X expansion since 2019. |
| Russia | 140+ | X, Telegram | Provocative trolling (UK embassy famous). Heavy Telegram. |
| Iran | 80+ | X, Telegram | Supreme Leader's X. IRGC accounts. Massive Telegram ecosystem. |
| Turkey | 100+ | X, Instagram | Erdogan personal account drives narrative. |
| Saudi Arabia | 90+ | X | MBS-era digital diplomacy expansion. |
| India | 150+ | X, Facebook | Modi most-followed world leader. |
| Israel | 90+ | X | Very active during conflicts. IDF Spokesperson key account. |

---

## Part 4: Recommended Architecture

### MVP Collection Stack (Under $200/mo)

```
Layer 1: GDELT (FREE)
├── 100+ languages, every country, 15-min updates
├── DOC 2.0 API for full-text search
└── GEO 2.0 API for geographic filtering

Layer 2: Direct RSS (FREE)
├── State news agency RSS feeds
├── State broadcaster RSS feeds
└── feedparser (Python) for ingestion

Layer 3: Grok API (~$50-100/mo)
├── X/Twitter state media account monitoring
├── Gray source discovery
└── Narrative velocity tracking

Layer 4: Telethon (FREE)
├── Telegram channel monitoring
├── Russian MoD, Iranian channels, Central Asian gov channels
└── Real-time message + media scraping

Layer 5: YouTube Data API (FREE tier)
├── State media channel monitoring
├── Transcript extraction
└── Comment sentiment (optional)

Layer 6: Scrapy + Trafilatura (FREE)
├── Fallback for sites without RSS/API
├── JS-heavy sites via Playwright
└── Article text extraction (F1=0.945)
```

### Analysis Stack

```
Claude API (Sonnet/Haiku)
├── SCAME analysis → debrief paragraph generation
├── Translation + analysis in single call
├── Theme extraction and classification
└── Cross-audience contradiction detection

Google Cloud Translation ($20/M chars, 500K free)
├── Batch translation for volume
└── 130+ language coverage

Perspective API (FREE)
└── Toxicity/manipulation scoring layer
```

### Scale Phase Additions (When Revenue Supports)
- NewsAPI.ai ($500+/mo) — enriched metadata, event clustering
- Webz.io ($500+/mo) — 170+ language coverage
- Talkwalker ($9,600/yr) — X Firehose, 187 languages
- Sprinklr (enterprise) — Douyin + Weibo firehose

---

## Part 5: Key Findings

1. **GDELT is the foundation** — free, global, 100+ languages, 15-min updates. Highest-resolution non-Western media inventory in the world. Start here.
2. **State Media Monitor is the source bible** — 606 outlets across 151 countries, already classified by funding/ownership/autonomy. Use to seed the database.
3. **Grok is the X/Twitter differentiator** — native access to social data no other model has. Essential for gray source discovery and narrative velocity tracking.
4. **Telegram is non-negotiable for Russia/Iran** — Telethon (free) provides full channel monitoring. Russian MoD, Rybar, WarGonzo, IRGC channels are critical sources.
5. **Hamilton 2.0 is still alive** — merged ASD/ISD. 30-day rolling data for Russia/China/Iran. Use as validation layer.
6. **Media Cloud for academic depth** — 2B stories, open source. Good for historical analysis and methodology credibility.
7. **Translation is solved** — Claude can translate + analyze in a single call. Google Cloud for volume (130+ languages). DeepL for quality on European languages.
8. **Every country has identifiable state media** — from Tuvalu to Turkmenistan. Even the smallest Pacific islands have a state radio station.
9. **MVP cost is under $200/mo** — GDELT (free) + RSS (free) + Telethon (free) + Claude Haiku (~$50) + Grok (~$100) = viable minimum.
10. **VK + Weibo are critical for domestic narrative comparison** — the app's killer feature (cross-audience contradiction) requires comparing what Russia/China tell domestic vs. international audiences. VK API and Weibo API make this possible.

---

## Related Files

- [[SalientSignal-Project]] — Product vision, features, monetization, development gameplan
- [[AURORA-Feed-Database]] — AURORA's 263 RSS sources (separate system, different purpose)
- [[Media-and-AI-Tools]] — Personal language learning media sources
- [[Digital-Language-Immersion-Overview]] — Foreign media sources for language practice
