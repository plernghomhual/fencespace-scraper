# Tournament Monte Carlo Re-Simulation

`simulate_tournament.py` re-simulates a historical tournament from entrants, Elo
ratings, and optional bracket data. It returns probabilities for winner, medal,
and top-8 outcomes without updating `fs_results`, `fs_bouts`, or historical
bracket rows.

## Inputs

- Entrants: `fencer_id`, `name`, and optional `seed`.
- Elo ratings: `fencer_id` to `rating`, or rows with `fencer_id` and `rating`.
- Format hint: examples are `direct_elimination`, `DE`, `standings`, `pool`, or
  `round robin`.
- Bracket rows: optional `fs_tournament_brackets` style rows with
  `round_name`, `bout_order`, `fencer_a_id`, and `fencer_b_id`.

Missing Elo ratings use a neutral `1500` rating and add a warning. Duplicate
entrant rows are deduplicated by `fencer_id`.

## Simulation Modes

### Direct Elimination

When usable bracket rows exist, the simulator uses only the earliest direct
elimination matchup slots. Historical `winner_id` fields are ignored so prior
results are not replayed as simulated outcomes.

If the format says direct elimination but bracket rows are missing, the
simulator builds a deterministic seeded bracket from entrant seeds, ratings,
names, and IDs. This is marked lower confidence than a bracket-backed run.

Medal probabilities in direct elimination count the winner, runner-up, and
semifinal losers when the bracket shape supports them. Top-8 probabilities count
the fencers that reach the round of 8, or all entrants when the event has eight
or fewer entrants.

### Simple Standings

For standings, pool, or round-robin formats, each iteration simulates a complete
pairwise set of Elo bouts and ranks entrants by simulated wins with a seeded
random tiebreaker. Medal probabilities count top 3. Top-8 probabilities count
top 8 or all entrants for smaller fields.

### Partial-Data Fallback

When no bracket and no recognized format are available, the simulator uses the
same standings model and returns `confidence: "low"`. This keeps the output
deterministic and useful while flagging that the true tournament format was not
known.

## CLI

Offline fixture run:

```bash
.venv/bin/python simulate_tournament.py \
  --tournament-id example-tournament \
  --input-json fixture.json \
  --seed 20260602 \
  --iterations 1000 \
  --output-json simulation.json
```

Supabase-backed run:

```bash
SUPABASE_URL=... SUPABASE_SERVICE_KEY=... \
.venv/bin/python simulate_tournament.py \
  --tournament-id <fs_tournaments.id> \
  --seed 20260602 \
  --iterations 5000 \
  --output-json simulation.json
```

The Supabase-backed path reads `fs_tournaments`, `fs_results`,
`fs_tournament_brackets`, and `fs_fencer_elo` when those tables are available.
It does not upsert or update tournament source tables.

## Output

The JSON result includes:

- `mode`: `direct_elimination`, `simple_standings`, or
  `partial_data_fallback`.
- `confidence`: `high`, `medium`, or `low`.
- `participants`: normalized entrants and ratings used.
- `probabilities.winner`: probabilities that sum to 1.
- `probabilities.medal`: probabilities that sum to the modeled medal slots.
- `probabilities.top8`: probabilities that sum to the available top-8 slots.
- `warnings`: missing Elo, fallback, bracket, or dedupe notes.

## Limitations

- Elo is assumed to be precomputed by Agent 76 or supplied in the input JSON.
- The simulator does not update Elo during a simulated tournament.
- Pool-to-DE qualification is approximated by simple standings unless detailed
  pool and bracket handoff data exists in future schema.
- Historical final or later-round bracket participants are not used as fixed
  advancement paths because that would leak actual results into the simulation.
- Team events, repechage, fence-offs for bronze, withdrawals, and injury
  defaults are not modeled.
