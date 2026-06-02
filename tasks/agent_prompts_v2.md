# Agent Prompts v2 — 160 Agents

## FRONTEND DATA GAPS (30 agents)

Agent 1 — Add `bio`, `birth_date`, `birth_place` columns to `fs_fencers` migration
Agent 2 — Expand Wikipedia bio scraper to fill `bio`, `birth_date`, `birth_place` for all fencers
Agent 3 — Create `fs_fencer_stats` table: total_bouts, wins, losses, win_pct, current_streak
Agent 4 — Compute fencer bout stats from `fs_bouts` into `fs_fencer_stats`
Agent 5 — Add `national_rank` column to `fs_fencers` and backfill from federation rankings
Agent 6 — Add `organizer`, `entry_deadline`, `format`, `quota` columns to `fs_tournaments`
Agent 7 — Scrape FIE competition detail pages for organizer, format, quota, deadline
Agent 8 — Create `fs_tournament_brackets` table: tournament_id, round, bout_order, fencer_a, fencer_b, score_a, score_b, winner_id
Agent 9 — Build bracket data pipeline from `fs_bouts` into `fs_tournament_brackets`
Agent 10 — Create `fs_fencer_season_stats` table: fencer_id, season, weapon, bouts, wins, losses, win_pct, avg_rank, medals
Agent 11 — Compute per-season fencer stats from results + bouts
Agent 12 — Create `fs_career_milestones` table: fencer_id, type, description, date, tournament_id, rank
Agent 13 — Career milestone detection engine (first podium, first gold, first senior, category transition)
Agent 14 — Create `fs_country_medal_geo` materialized view: country, lat, lon, gold, silver, bronze, total
Agent 15 — Geocode all countries for medal heatmap
Agent 16 — Create `fs_ranking_history_trajectory` table with per-fencer/weapon/category/season rank snapshots
Agent 17 — Ranking sparkline data endpoint materialized view
Agent 18 — Unify country code data: single source of truth API removing 5 hardcoded copies
Agent 19 — Add `losses`/`defeats` column to `fs_results` and backfill from bout data
Agent 20 — Featured athletes algorithm: top-N fencers by world_rank, trending, recent medalists
Agent 21 — Fencer social follower count tracker (Instagram, Twitter, YouTube subscriber counts)
Agent 22 — Social media feed real-time aggregator for #fencing content
Agent 23 — AI insights pipeline: fencer comparison, performance summary generation
Agent 24 — Wire H2H data into athlete page (currently says "coming soon")
Agent 25 — Wire ranking history into athlete page trajectory chart
Agent 26 — Wire win/loss stats into athlete page
Agent 27 — Wire career milestones into athlete page timeline
Agent 28 — Wire bracket data into tournament page interactive bracket
Agent 29 — Wire organizer/format/deadline into tournament info table
Agent 30 — Create `v_fencer_public` view that exposes all needed athlete fields

## TIER-3 FEDERATIONS (30 agents)

Agent 31 — Mexico (FME)
Agent 32 — Colombia (FEC)
Agent 33 — Venezuela (FVA)
Agent 34 — Chile (FChE)
Agent 35 — Turkey (TF)
Agent 36 — Iran (IRI)
Agent 37 — Kazakhstan (KAZ)
Agent 38 — Thailand (THA)
Agent 39 — Chinese Taipei (TPE)
Agent 40 — Morocco (MAR)
Agent 41 — Tunisia (TUN)
Agent 42 — South Africa (RSA)
Agent 43 — Ireland (IRL)
Agent 44 — Portugal (POR)
Agent 45 — Greece (GRE)
Agent 46 — Croatia (CRO)
Agent 47 — Serbia (SRB)
Agent 48 — Bulgaria (BUL)
Agent 49 — Slovakia (SVK)
Agent 50 — Slovenia (SLO)
Agent 51 — Lithuania (LTU)
Agent 52 — Latvia (LVA)
Agent 53 — Estonia (EST)
Agent 54 — Azerbaijan (AZE)
Agent 55 — Puerto Rico (PUR)
Agent 56 — Dominican Republic (DOM)
Agent 57 — Jamaica (JAM)
Agent 58 — Cyprus (CYP)
Agent 59 — Iceland (ISL)
Agent 60 — Malta (MLT)

## MORE TOURNAMENTS (15 agents)

Agent 61 — National championships scraper for top-20 countries (from federation sites)
Agent 62 — BUCS UK university fencing results
Agent 63 — French university fencing league (FFSU)
Agent 64 — Japanese university fencing league results
Agent 65 — USA Y12/Y14 youth national circuit results
Agent 66 — British Youth Fencing results (BYC)
Agent 67 — IWAS World Games and IWAS satellite wheelchair events
Agent 68 — Historical pre-2000 results from sport-reference / olympedia deep crawl
Agent 69 — FIE World Cup individual pool bout-by-bout data (all pools, not just DE)
Agent 70 — FIE Satellite and FIE Challenge series results
Agent 71 — Veterans World Cup circuit (Veteran World Championships + VWC events)
Agent 72 — European Fencing Confederation (EFC) youth circuit events
Agent 73 — Asian Fencing Confederation (AFC) championships and circuit
Agent 74 — African Fencing Confederation (AFC) championships
Agent 75 — Pan American Fencing Confederation (PAFC) circuit events

## DEEPER ANALYTICS (15 agents)

Agent 76 — Elo rating system for fencers (dynamic, bout-weighted, cross-era comparable)
Agent 77 — Legacy score: weighted medal index (Olympic gold × 10, Worlds × 5, GP × 3, WC × 2)
Agent 78 — Peak performance age analysis by weapon × gender
Agent 79 — Upset tracker: lowest seed to medal per tournament, biggest rank gap upsets
Agent 80 — Home advantage analysis: fencer performance at home vs abroad
Agent 81 — Prediction model for next Olympic/World medalists
Agent 82 — Fantasy fencing scoring engine (points per fencer per tournament)
Agent 83 — Match-fixing / betting anomaly detection (score pattern analysis)
Agent 84 — Fencer head-to-head network graph computation
Agent 85 — Competition difficulty trending over time
Agent 86 — Fencer "clutch" metric: performance delta in elimination vs pool rounds
Agent 87 — Country specialization index (which weapons/categories each country dominates)
Agent 88 — Junior-to-Senior conversion rate by country and weapon
Agent 89 — Medal efficiency: medals per capita, per fencer, per competition entered
Agent 90 — Fencer similarity recommendation engine ("fencer you might also follow")

## MORE ENRICHMENT (15 agents)

Agent 91 — Fencer education and occupation from Wikipedia + Wikidata
Agent 92 — Fencer family relationships from Wikidata (siblings, parents who also fence)
Agent 93 — Anti-doping test history per fencer (from ITA / WADA databases)
Agent 94 — Referee match assignments per tournament (which referees officiated which bouts)
Agent 95 — Club founding dates, history text, notable alumni
Agent 96 — Coach career history (which fencers each coach has trained)
Agent 97 — Fencer video highlight reels auto-curated from YouTube
Agent 98 — Interview quotes database from press conferences and media
Agent 99 — Fencer sponsorship deals and endorsement history
Agent 100 — Fencer nationality history from Wikidata (multiple citizenships with dates)
Agent 101 — Competition weather data (indoor vs outdoor events, temperature, humidity)
Agent 102 — Equipment usage trends (what brands are winning, by weapon)
Agent 103 — Fencer handedness data (left-handed vs right-handed stats)
Agent 104 — Fencer injury history from news scraping
Agent 105 — Historical rule changes database and their impact on results

## PRODUCT / FRONTEND LAYER (25 agents)

Agent 106 — Next.js frontend with search + browse for all entities
Agent 107 — GraphQL API wrapping existing REST + Supabase
Agent 108 — WebSocket server for live results push
Agent 109 — Competition bracket visualizer React component
Agent 110 — Fencer career timeline visualizer React component
Agent 111 — Country medal heatmap interactive map component
Agent 112 — Ranking history sparkline chart component
Agent 113 — Head-to-head comparison page with side-by-side stats
Agent 114 — Tournament results PDF generator
Agent 115 — Calendar sync (ICS feed per federation/weapon/category)
Agent 116 — Ranking alerts service (email/SMS when fencer rank changes)
Agent 117 — Automated result tweets bot (Twitter/X integration)
Agent 118 — Data syndication API for media partners
Agent 119 — BigQuery export pipeline for data science users
Agent 120 — Data marketplace / API monetization portal with Stripe integration
Agent 121 — Fencer photo dedup via facial recognition
Agent 122 — Competition PDF results → structured data OCR pipeline
Agent 123 — Mobile push notification service for live results
Agent 124 — Fencer comparison tool (side-by-side career stats)
Agent 125 — "Who's hot" trending fencers weekly leaderboard
Agent 126 — Fencer social leaderboard (most followed, most mentioned)
Agent 127 — Competition countdown and calendar view
Agent 128 — Federation overview pages with depth charts
Agent 129 — News aggregator frontend with filtering by fencer
Agent 130 — Athlete quiz / trivia feature from career data

## MARKETPLACE / SOCIAL / MEDIA (15 agents)

Agent 131 — Absolute Fencing product catalog scraper
Agent 132 — Leon Paul product catalog scraper
Agent 133 — Allstar/Uhlmann product catalog scraper
Agent 134 — Fencing.net product scraper + reviews
Agent 135 — PBT Fencing product scraper
Agent 136 — Blue Gauntlet product scraper
Agent 137 — Fencing store directory (physical stores worldwide)
Agent 138 — Fencing club review scraper from Google Maps
Agent 139 — YouTube fencing video indexer (channels, playlists, by fencer)
Agent 140 — Instagram fencing content aggregator
Agent 141 — TikTok fencing content aggregator
Agent 142 — Forum scraper (fencing.net, reddit r/fencing) for discussions
Agent 143 — Fencing event photographer directory
Agent 144 — Fencing equipment second-hand marketplace scraper
Agent 145 — Fencing camp review aggregator

## ADVANCED / EXPERIMENTAL (15 agents)

Agent 146 — Match video auto-trimmer (find fencer from YouTube video length)
Agent 147 — Live scoring overlay for streamers (OBS plugin data)
Agent 148 — Fencing fantasy league with draft and weekly scoring
Agent 149 — Historical tournament re-simulator (Monte Carlo based on Elo)
Agent 150 — Fencer form tracker (last 5 competitions trend)
Agent 151 — Betting odds aggregator for upcoming competitions
Agent 152 — Youth talent identification (early-career outlier detection)
Agent 153 — Fencer transfer market value estimator
Agent 154 — Equipment durability tracker (how often top fencers replace gear)
Agent 155 — Fencing gym / training facility directory worldwide
Agent 156 — Fencer sponsorship matchmaking (brand to athlete)
Agent 157 — Competition travel cost estimator (flights + hotels for each event)
Agent 158 — Fencing history timeline (major rule changes, equipment evolution)
Agent 159 — AI coach: technique analysis from bout data patterns
Agent 160 — CI merge for all 160 agents into workflow files
