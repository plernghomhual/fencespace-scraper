import re
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"

SCRAPER_WORKFLOW = "scraper.yml"
LIVE_RESULTS_WORKFLOW = "live_results.yml"
WEEKLY_ANALYTICS_WORKFLOW = "weekly_analytics.yml"

SUPABASE_ENV_KEYS = {"SUPABASE_URL", "SUPABASE_SERVICE_KEY"}

CORE_SCRAPERS = [
    "discover_competition_urls.py",
    "scraper.py",
    "scrape_fie_events.py",
    "scrape_rankings_history.py",
    "scrape_results.py",
    "scrape_engarde.py",
    "scrape_bouts.py",
    "scrape_clubs.py",
]

DEPRECATED_WORKFLOW_SCRIPTS = {
    "askfred_scraper.py",
}

EXISTING_FEDERATION_SCRAPERS = [
    "scrape_fed_british.py",
    "scrape_fed_france.py",
    "scrape_fed_germany.py",
    "scrape_fed_italy.py",
    "scrape_fed_canada.py",
]

FEDERATION_BATCH_B = [
    "scrape_fed_hun.py",
    "scrape_fed_kor.py",
    "scrape_fed_chn.py",
    "scrape_fed_jpn.py",
    "scrape_fed_rus.py",
    "scrape_fed_pol.py",
    "scrape_fed_ukr.py",
    "scrape_fed_rou.py",
    "scrape_fed_esp.py",
    "scrape_fed_egy.py",
]

FEDERATION_TIER_2 = [
    "scrape_fed_ned.py",
    "scrape_fed_bel.py",
    "scrape_fed_sui.py",
    "scrape_fed_aut.py",
    "scrape_fed_swe.py",
    "scrape_fed_den.py",
    "scrape_fed_nor.py",
    "scrape_fed_fin.py",
    "scrape_fed_aus.py",
    "scrape_fed_nzl.py",
    "scrape_fed_bra.py",
    "scrape_fed_arg.py",
    "scrape_fed_hkg.py",
    "scrape_fed_sgp.py",
    "scrape_fed_isr.py",
]

COMPETITION_SOURCES = [
    "scrape_fred.py",
    "scrape_youth_olympics.py",
    "scrape_universiade.py",
    "scrape_continental_games.py",
    "scrape_ncaa_regular.py",
    "scrape_youth_majors.py",
    "scrape_paralympics.py",
    "scrape_news.py",
]

COMPETITION_TIER_3 = [
    "scrape_commonwealth.py",
    "scrape_cism.py",
    "scrape_mediterranean_games.py",
    "scrape_maccabiah.py",
    "scrape_masters_games.py",
    "scrape_south_american_games.py",
    "scrape_cac_games.py",
    "scrape_island_games.py",
]

ENRICHMENT_SCRIPTS = [
    "scrape_wikipedia_bios.py",
    "scrape_social_media.py",
    "scripts/download_headshots.py",
    "scrape_equipment.py",
    "scrape_physical_stats.py",
    "enrich_nationality_history.py",
    "scrape_competition_details.py",
    "scrape_club_reviews.py",
    "scrape_equipment_reviews.py",
    "scrape_training_camps.py",
    "scrape_college_scholarships.py",
]

PROMPT_COMPUTE_SCRIPTS = [
    "compute_head_to_head.py",
    "compute_career_stats.py",
    "compute_rankings_trends.py",
    "compute_country_analytics.py",
    "compute_transfers.py",
    "compute_name_variants.py",
    "enrich_locations.py",
    "compute_strength_of_field.py",
    "compute_performance_analysis.py",
    "compute_medal_tables.py",
    "compute_longevity.py",
    "compute_specialization.py",
]

FINAL_SCRIPTS = [
    "scripts/data_quality_check.py",
]

EXISTING_FINAL_SCRIPTS = [
    "compute_national_rankings.py",
    "scrape_athlete_profiles.py",
    "scrape_fie_history.py",
    "scrape_wikidata.py",
    "scrape_olympics.py",
    "scrape_ncaa.py",
    "scrape_iwas.py",
    "scrape_fie_career.py",
]

# ── New agents 31-60: tier-3 federation scrapers ──────────────────────────────
FEDERATION_TIER_3 = [
    "scrape_fed_aze.py",
    "scrape_fed_bul.py",
    "scrape_fed_chi.py",
    "scrape_fed_col.py",
    "scrape_fed_cro.py",
    "scrape_fed_cyp.py",
    "scrape_fed_dom.py",
    "scrape_fed_est.py",
    "scrape_fed_gre.py",
    "scrape_fed_iri.py",
    "scrape_fed_irl.py",
    "scrape_fed_isl.py",
    "scrape_fed_jam.py",
    "scrape_fed_kaz.py",
    "scrape_fed_ltu.py",
    "scrape_fed_lva.py",
    "scrape_fed_mar.py",
    "scrape_fed_mex.py",
    "scrape_fed_mlt.py",
    "scrape_fed_por.py",
    "scrape_fed_pur.py",
    "scrape_fed_rsa.py",
    "scrape_fed_slo.py",
    "scrape_fed_srb.py",
    "scrape_fed_svk.py",
    "scrape_fed_tha.py",
    "scrape_fed_tpe.py",
    "scrape_fed_tun.py",
    "scrape_fed_tur.py",
    "scrape_fed_ven.py",
    "scrape_ffsu.py",
]

# ── New agents 61-75: more tournament scrapers ────────────────────────────────
TOURNAMENT_SCRAPERS = [
    "scrape_fie_pools.py",
    "scrape_fie_satellite.py",
    "scrape_national_champs.py",
    "scrape_veterans.py",
    "scrape_british_youth.py",
    "scrape_bucs.py",
    "scrape_efc_youth.py",
    "scrape_japanese_univ.py",
    "scrape_usa_youth.py",
    "scrape_iwas_games.py",
    "scrape_afc.py",
    "scrape_african_conf.py",
    "scrape_panam_conf.py",
    "scrape_fencers.py",
]

# ── New agents 91-105: more enrichment ───────────────────────────────────────
ENRICHMENT_EXTENDED = [
    "enrich_clubs.py",
    "enrich_coach_history.py",
    "enrich_education.py",
    "enrich_family.py",
    "enrich_handedness.py",
    "enrich_weather.py",
    "scrape_injuries.py",
    "scrape_historical_olympedia.py",
    "scrape_referee_assignments.py",
    "scrape_doping.py",
    "scrape_fencing_history.py",
    "scrape_training_facilities.py",
    "scrape_camp_reviews.py",
    "dedupe_headshots.py",
    "estimate_travel_costs.py",
    "scripts/backfill_national_rank.py",
    "scripts/backfill_result_losses.py",
    "scripts/geocode_countries.py",
    "scripts/match_orphan_results.py",
    "scripts/reconcile_data.py",
]

# ── New agents 131-145: marketplace and social scrapers ───────────────────────
MARKETPLACE_SOCIAL = [
    "scrape_fencing_stores.py",
    "scrape_absolutefencing.py",
    "scrape_allstar_uhlmann.py",
    "scrape_blue_gauntlet_products.py",
    "scrape_leonpaul.py",
    "scrape_pbt_products.py",
    "scrape_fencingnet_products.py",
    "scrape_secondhand_equipment.py",
    "scrape_equipment_trends.py",
    "scrape_sponsorships.py",
    "scrape_instagram_fencing.py",
    "scrape_tiktok_fencing.py",
    "scrape_youtube_videos.py",
    "scrape_fencing_forums.py",
    "scrape_social_followers.py",
    "scrape_photographer_directory.py",
    "scrape_google_club_reviews.py",
    "scrape_quotes.py",
    "aggregate_social_feed.py",
    "aggregate_videos.py",
]

# ── New agents 76-90: deeper analytics (scraper.yml + weekly_analytics.yml) ──
DEEPER_ANALYTICS = [
    "compute_elo.py",
    "compute_anomalies.py",
    "compute_brackets.py",
    "compute_clutch.py",
    "compute_upsets.py",
    "compute_predictions.py",
    "compute_form_tracker.py",
    "compute_career_milestones.py",
    "compute_difficulty_trend.py",
    "compute_youth_talent.py",
    "compute_junior_conversion.py",
    "compute_peak_age.py",
    "compute_home_advantage.py",
    "compute_country_specialization.py",
    "compute_fencer_stats.py",
]

# ── New agents 146-159: advanced / experimental ───────────────────────────────
# Compute scripts appear in both scraper.yml and weekly_analytics.yml.
# Scraper-only scripts appear in scraper.yml only.
ADVANCED_COMPUTE = [
    "compute_ai_insights.py",
    "compute_fencer_similarity.py",
    "compute_fencer_season_stats.py",
    "compute_h2h_graph.py",
    "compute_legacy_score.py",
    "compute_medal_efficiency.py",
    "compute_social_leaderboard.py",
    "compute_sponsorship_matches.py",
    "compute_technique_analysis.py",
    "compute_transfer_value.py",
    "compute_trending_fencers.py",
    "compute_equipment_durability.py",
]

ADVANCED_SCRAPER_ONLY = [
    "ocr_results.py",
    "scrape_betting_odds.py",
    "scrape_rule_changes.py",
]

ADVANCED_EXPERIMENTAL = ADVANCED_COMPUTE + ADVANCED_SCRAPER_ONLY

# ── Agents 106-130: product / frontend layer — NOT scheduled in CI ────────────
# These scripts serve the frontend/API layer and must not appear in any workflow.
FRONTEND_PRODUCT_ONLY = {
    "api.py",
    "api_syndication.py",
    "calendar_feed.py",
    "cli.py",
    "cli_export.py",
    "compute_fantasy_points.py",
    "compute_featured_athletes.py",
    "compute_trivia.py",
    "export_bigquery.py",
    "fantasy_league.py",
    "frontend_api_contract.py",
    "generate_tournament_pdf.py",
    "marketplace_api.py",
    "obs_overlay_server.py",
    "post_result_tweets.py",
    "push_notifications.py",
    "ranking_alerts.py",
    "simulate_tournament.py",
    "video_trimmer.py",
    "ws_server.py",
}

SIX_HOUR_SCRIPTS = (
    CORE_SCRAPERS
    + EXISTING_FEDERATION_SCRAPERS
    + FEDERATION_BATCH_B
    + FEDERATION_TIER_2
    + COMPETITION_SOURCES
    + COMPETITION_TIER_3
    + ENRICHMENT_SCRIPTS
    + PROMPT_COMPUTE_SCRIPTS
    + FINAL_SCRIPTS
    + EXISTING_FINAL_SCRIPTS
    + FEDERATION_TIER_3
    + TOURNAMENT_SCRAPERS
    + ENRICHMENT_EXTENDED
    + MARKETPLACE_SOCIAL
    + DEEPER_ANALYTICS
    + ADVANCED_EXPERIMENTAL
)

WEEKLY_ANALYTICS_SCRIPTS = [
    "compute_national_rankings.py",
    *PROMPT_COMPUTE_SCRIPTS,
    # Deeper analytics — agents 76-90
    *DEEPER_ANALYTICS,
    # Advanced / experimental compute — agents 146-159
    *ADVANCED_COMPUTE,
]

INTENDED_WORKFLOWS = {
    **{script: {SCRAPER_WORKFLOW} for script in SIX_HOUR_SCRIPTS},
    # Compute scripts in WEEKLY_ANALYTICS_SCRIPTS override to appear in both workflows.
    **{script: {SCRAPER_WORKFLOW, WEEKLY_ANALYTICS_WORKFLOW} for script in WEEKLY_ANALYTICS_SCRIPTS},
    "watch_live_results.py": {LIVE_RESULTS_WORKFLOW},
}


def load_workflow(filename):
    with (WORKFLOW_DIR / filename).open() as handle:
        return yaml.safe_load(handle)


def all_workflows():
    return {
        filename: load_workflow(filename)
        for filename in [SCRAPER_WORKFLOW, LIVE_RESULTS_WORKFLOW, WEEKLY_ANALYTICS_WORKFLOW]
    }


def script_from_step(step):
    run = step.get("run", "")
    match = re.search(r"\bpython\s+([^\s]+\.py)\b", run)
    return match.group(1) if match else None


def workflow_steps(workflow):
    jobs = workflow["jobs"]
    all_steps = []
    for job in jobs.values():
        all_steps.extend(job.get("steps", []))
    return all_steps


def workflow_triggers(workflow):
    return workflow.get("on") or workflow.get(True)


def workflow_scripts(workflow):
    return [script for step in workflow_steps(workflow) if (script := script_from_step(step))]


def assert_subsequence(actual, expected):
    cursor = 0
    for script in actual:
        if cursor < len(expected) and script == expected[cursor]:
            cursor += 1
    assert cursor == len(expected), f"missing ordered scripts: {expected[cursor:]}"


def test_workflow_yaml_parses_all_files():
    for filename, workflow in all_workflows().items():
        assert workflow, f"{filename} did not parse to a workflow"


def test_workflow_schedules_are_expected():
    workflows = all_workflows()

    expected_crons = {
        SCRAPER_WORKFLOW: ["0 */6 * * *"],
        LIVE_RESULTS_WORKFLOW: ["*/15 * * * *"],
        WEEKLY_ANALYTICS_WORKFLOW: ["0 3 * * 0"],
    }
    for filename, expected in expected_crons.items():
        triggers = workflow_triggers(workflows[filename])
        actual = [schedule["cron"] for schedule in triggers["schedule"]]
        assert actual == expected
        assert "workflow_dispatch" in triggers


def test_discover_competition_urls_runs_before_results_scraper():
    workflow = load_workflow(SCRAPER_WORKFLOW)
    jobs = workflow["jobs"]

    def find_job(script):
        for job_name, job in jobs.items():
            for step in job.get("steps", []):
                if script == script_from_step(step):
                    return job_name
        return None

    discover_job = find_job("discover_competition_urls.py")
    results_job = find_job("scrape_results.py")
    assert discover_job is not None
    assert results_job is not None
    # results_job must directly or transitively depend on discover_job
    needs = set(jobs[results_job].get("needs", []))
    assert discover_job in needs or any(
        discover_job in set(jobs[n].get("needs", [])) for n in needs
    )


def test_six_hour_scraper_workflow_contains_required_scripts_once_and_in_order():
    scripts = workflow_scripts(load_workflow(SCRAPER_WORKFLOW))

    for script in SIX_HOUR_SCRIPTS:
        assert scripts.count(script) == 1, f"{script} should appear once in scraper.yml"
    # Global step ordering is not enforced with parallel jobs; job `needs:` dependencies
    # ensure correct execution order between phases. Only check containment here.


def test_deprecated_scrapers_are_not_scheduled():
    scripts = workflow_scripts(load_workflow(SCRAPER_WORKFLOW))

    for script in DEPRECATED_WORKFLOW_SCRIPTS:
        assert script not in scripts, f"{script} is deprecated and should not run in scraper.yml"


def test_analytics_job_waits_for_all_phase2_scraper_jobs():
    workflow = load_workflow(SCRAPER_WORKFLOW)
    jobs = workflow["jobs"]
    assert "analytics" in jobs, "analytics job must exist"
    analytics_needs = set(jobs["analytics"].get("needs", []))
    expected_needs = {
        "fie-scrapers",
        "federation-scrapers",
        "competition-scrapers",
        "enrichment",
        "federation-tier3",
        "tournament-scrapers",
        "enrichment-extended",
        "marketplace-social",
    }
    assert analytics_needs == expected_needs, (
        f"analytics job must depend on all phase-2 scraper jobs; got {analytics_needs}"
    )


def test_deeper_analytics_waits_for_analytics():
    workflow = load_workflow(SCRAPER_WORKFLOW)
    jobs = workflow["jobs"]
    assert "deeper-analytics" in jobs, "deeper-analytics job must exist"
    needs = set(jobs["deeper-analytics"].get("needs", []))
    assert "analytics" in needs, f"deeper-analytics must depend on analytics; got {needs}"


def test_advanced_experimental_waits_for_deeper_analytics():
    workflow = load_workflow(SCRAPER_WORKFLOW)
    jobs = workflow["jobs"]
    assert "advanced-experimental" in jobs, "advanced-experimental job must exist"
    needs = set(jobs["advanced-experimental"].get("needs", []))
    assert "deeper-analytics" in needs, (
        f"advanced-experimental must depend on deeper-analytics; got {needs}"
    )


def test_live_results_workflow_only_runs_live_watcher():
    scripts = workflow_scripts(load_workflow(LIVE_RESULTS_WORKFLOW))

    assert scripts == ["watch_live_results.py"]


def test_weekly_analytics_workflow_contains_compute_scripts_once():
    scripts = workflow_scripts(load_workflow(WEEKLY_ANALYTICS_WORKFLOW))

    assert scripts == WEEKLY_ANALYTICS_SCRIPTS


def test_prompt_scripts_only_appear_in_intended_workflows():
    workflows = all_workflows()

    for script, intended in INTENDED_WORKFLOWS.items():
        actual = {
            filename
            for filename, workflow in workflows.items()
            if script in workflow_scripts(workflow)
        }
        assert actual == intended, f"{script} workflows should be {intended}, got {actual}"


def test_frontend_product_scripts_not_in_any_workflow():
    workflows = all_workflows()
    all_ci_scripts: set[str] = set()
    for workflow in workflows.values():
        all_ci_scripts.update(workflow_scripts(workflow))

    for script in FRONTEND_PRODUCT_ONLY:
        assert script not in all_ci_scripts, (
            f"{script} is product/frontend-only (agents 106-130) and must not appear in any workflow"
        )


def test_new_agent_script_groups_all_appear_in_scraper():
    scripts = set(workflow_scripts(load_workflow(SCRAPER_WORKFLOW)))
    for group_name, group in [
        ("FEDERATION_TIER_3", FEDERATION_TIER_3),
        ("TOURNAMENT_SCRAPERS", TOURNAMENT_SCRAPERS),
        ("ENRICHMENT_EXTENDED", ENRICHMENT_EXTENDED),
        ("MARKETPLACE_SOCIAL", MARKETPLACE_SOCIAL),
        ("DEEPER_ANALYTICS", DEEPER_ANALYTICS),
        ("ADVANCED_EXPERIMENTAL", ADVANCED_EXPERIMENTAL),
    ]:
        missing = [s for s in group if s not in scripts]
        assert not missing, f"{group_name} scripts missing from scraper.yml: {missing}"


def test_deeper_and_advanced_compute_appear_in_weekly_analytics():
    scripts = set(workflow_scripts(load_workflow(WEEKLY_ANALYTICS_WORKFLOW)))
    for group_name, group in [
        ("DEEPER_ANALYTICS", DEEPER_ANALYTICS),
        ("ADVANCED_COMPUTE", ADVANCED_COMPUTE),
    ]:
        missing = [s for s in group if s not in scripts]
        assert not missing, f"{group_name} scripts missing from weekly_analytics.yml: {missing}"


def test_advanced_scraper_only_not_in_weekly_analytics():
    scripts = set(workflow_scripts(load_workflow(WEEKLY_ANALYTICS_WORKFLOW)))
    for script in ADVANCED_SCRAPER_ONLY:
        assert script not in scripts, (
            f"{script} is scraper-only and must not appear in weekly_analytics.yml"
        )


INFRASTRUCTURE_SCRIPTS = {
    "scripts/migrate.py",
}


def test_each_python_script_step_has_continue_on_error_and_supabase_env():
    for filename, workflow in all_workflows().items():
        for step in workflow_steps(workflow):
            script = script_from_step(step)
            if not script or script in INFRASTRUCTURE_SCRIPTS:
                continue
            assert step.get("continue-on-error") is True, f"{filename}: {step['name']}"
            env = step.get("env", {})
            assert SUPABASE_ENV_KEYS <= set(env), f"{filename}: {step['name']}"
