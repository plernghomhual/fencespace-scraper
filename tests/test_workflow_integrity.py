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
    "askfred_scraper.py",
    "scrape_engarde.py",
    "scrape_bouts.py",
    "scrape_clubs.py",
]

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
)

WEEKLY_ANALYTICS_SCRIPTS = [
    "compute_national_rankings.py",
    *PROMPT_COMPUTE_SCRIPTS,
]

INTENDED_WORKFLOWS = {
    **{script: {SCRAPER_WORKFLOW} for script in SIX_HOUR_SCRIPTS},
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
    assert len(jobs) == 1
    return next(iter(jobs.values()))["steps"]


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
    scripts = workflow_scripts(load_workflow(SCRAPER_WORKFLOW))

    assert scripts.index("discover_competition_urls.py") < scripts.index("scrape_results.py")


def test_six_hour_scraper_workflow_contains_required_scripts_once_and_in_order():
    scripts = workflow_scripts(load_workflow(SCRAPER_WORKFLOW))

    for script in SIX_HOUR_SCRIPTS:
        assert scripts.count(script) == 1, f"{script} should appear once in scraper.yml"
    assert_subsequence(scripts, SIX_HOUR_SCRIPTS)


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


def test_each_python_script_step_has_continue_on_error_and_supabase_env():
    for filename, workflow in all_workflows().items():
        for step in workflow_steps(workflow):
            if not script_from_step(step):
                continue
            assert step.get("continue-on-error") is True, f"{filename}: {step['name']}"
            env = step.get("env", {})
            assert SUPABASE_ENV_KEYS <= set(env), f"{filename}: {step['name']}"
