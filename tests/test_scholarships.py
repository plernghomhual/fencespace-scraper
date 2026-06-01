import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

NOW = "2026-06-01T12:00:00+00:00"


SCHOLARSHIPSTATS_HTML = """
<html><body>
<table>
  <tr><th></th><th></th><th colspan="2"># of teams</th><th></th><th colspan="2">Total Athletes</th><th></th><th colspan="2">Average team size</th><th></th><th colspan="2">Scholarship limit</th></tr>
  <tr><th>Division</th><th></th><th>Men's</th><th>Women's</th><th></th><th>Men</th><th>Women</th><th></th><th>Men's</th><th>Women's</th><th></th><th>Men</th><th>Women</th></tr>
  <tr><td>NCAA I</td><td></td><td>23</td><td>28</td><td></td><td>444</td><td>506</td><td></td><td>19</td><td>18</td><td></td><td>24</td><td>24</td></tr>
  <tr><td>NCAA II</td><td></td><td>1</td><td>1</td><td></td><td>13</td><td>12</td><td></td><td>13</td><td>12</td><td></td><td>4.5</td><td>4.5</td></tr>
  <tr><td>NCAA III</td><td></td><td>11</td><td>15</td><td></td><td>228</td><td>241</td><td></td><td>21</td><td>16</td><td></td><td>-</td><td>-</td></tr>
</table>
<table>
  <tr><th>US Colleges with varsity Fencing teams 2024-25</th><th>City / Campus</th><th>State</th><th></th><th>Division</th><th></th><th>Teams</th><th></th></tr>
  <tr><td><a href="http://www.gostanford.com/">Stanford University</a></td><td>Palo Alto</td><td>CA</td><td></td><td>NCAA I</td><td></td><td>M</td><td>W</td></tr>
  <tr><td><a href="http://bceagles.com/">Boston College</a></td><td>Chestnut Hill</td><td>MA</td><td></td><td>NCAA I</td><td></td><td>M</td><td>W</td></tr>
  <tr><td><a href="http://www.drewrangers.com/">Drew University</a></td><td>Madison</td><td>NJ</td><td></td><td>NCAA III</td><td></td><td></td><td>W</td></tr>
  <tr><td><a href="http://www.savannahartdesign.edu/">Savannah College of Art &amp; Design</a></td><td>Savannah</td><td>GA</td><td></td><td>NAIA</td><td></td><td>M</td><td>W</td></tr>
</table>
</body></html>
"""


ROSTER_HTML = """
<html><body>
<a href="/sports/fencing/roster/julia-babiac/26464"></a>
<a href="/sports/fencing/roster/julia-babiac/26464">Julia Babiac</a>
<a href="/sports/fencing/roster/julia-babiac/26464">Full Bio for Julia Babiac</a>
<div>Position Epee</div>
<a href="/sports/fencing/roster/chase-callahan/26466">Chase Callahan</a>
<div>Position Foil</div>
<a href="/sports/fencing/roster/coaches/brendan-doris-pierce/1302">Brendan Doris-Pierce</a>
</body></html>
"""


COACH_HTML = """
<html><body>
<div>Name</div><div>Title</div><div>Phone</div><div>Email Address</div>
<div>Brendan Doris-Pierce</div>
<div>Mayer Family Head Fencing Coach</div>
<div>552-1048</div>
<div>dorispib@bc.edu</div>
<div>Ralf Bissdorf</div>
<div>Assistant Coach</div>
</body></html>
"""

ROSTER_WITH_FALSE_COACH_HINT = """
<html><body>
<a href="/sports/fencing/roster/renee-zuhars/1">Hide/Show Additional Information For Renee Zuhars</a>
<div>Renee Zuhars</div>
<div>Head Coach</div>
<a href="/sports/fencing/roster/julia-babiac/26464">Julia Babiac</a>
</body></html>
"""


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, client, table_name):
        self.client = client
        self.table_name = table_name
        self.pending_rows = None
        self.pending_conflict = None

    def upsert(self, rows, on_conflict):
        self.pending_rows = rows
        self.pending_conflict = on_conflict
        return self

    def execute(self):
        self.client.upserts.append(
            (self.table_name, self.pending_rows, self.pending_conflict)
        )
        return FakeResponse(self.pending_rows)


class FakeSupabase:
    def __init__(self):
        self.upserts = []

    def table(self, table_name):
        return FakeQuery(self, table_name)


class FakeHTTPResponse:
    def __init__(self, url, text, status_code=200):
        self.url = url
        self.text = text
        self.status_code = status_code


class FakeSession:
    def get(self, url, headers=None, timeout=None):
        if url.endswith("/sports/fencing/roster"):
            return FakeHTTPResponse(url, ROSTER_WITH_FALSE_COACH_HINT)
        if url.endswith("/sports/fencing/coaches"):
            return FakeHTTPResponse(url, COACH_HTML)
        return FakeHTTPResponse(url, "<html><body>Fencing</body></html>")


class RedirectToOtherSportSession:
    def get(self, url, headers=None, timeout=None):
        return FakeHTTPResponse(
            "https://gostanford.com/sports/womens-tennis/roster/season/2012-13/staff/frankie-brennan",
            COACH_HTML,
        )


def test_parse_scholarshipstats_programs_extracts_ncaa_programs_and_limits():
    from scrape_college_scholarships import parse_scholarshipstats_programs

    programs = parse_scholarshipstats_programs(SCHOLARSHIPSTATS_HTML, limit=50)

    assert [program.college_name for program in programs] == [
        "Stanford University",
        "Boston College",
        "Drew University",
    ]
    assert programs[0].division == "NCAA I"
    assert programs[0].gender_teams == ["Men", "Women"]
    assert programs[0].website == "https://www.gostanford.com/"
    assert programs[0].scholarship_slots == 48
    assert programs[0].metadata["scholarship_slots_exact"] == 48.0
    assert programs[2].scholarship_slots == 0
    assert programs[2].metadata["source_rank"] == 3


def test_extract_roster_size_counts_unique_athlete_profile_links_only():
    from scrape_college_scholarships import extract_roster_size, extract_weapons

    assert extract_roster_size(ROSTER_HTML) == 2
    assert extract_weapons(ROSTER_HTML) == ["Epee", "Foil"]


def test_extract_head_coach_prefers_head_coach_over_assistants():
    from scrape_college_scholarships import extract_head_coach

    coach = extract_head_coach(COACH_HTML)

    assert coach == {
        "head_coach": "Brendan Doris-Pierce",
        "coach_email": "dorispib@bc.edu",
    }


def test_build_scholarship_row_combines_directory_roster_and_coach_data():
    from scrape_college_scholarships import (
        CollegeProgramSeed,
        build_scholarship_row,
    )

    seed = CollegeProgramSeed(
        college_name="Boston College",
        division="NCAA I",
        conference="ACC",
        gender_teams=["Men", "Women"],
        website="https://bceagles.com/",
        scholarship_slots=48,
        metadata={
            "directory_source": "https://scholarshipstats.com/fencing",
            "scholarship_slots_exact": 48.0,
        },
    )

    row = build_scholarship_row(
        seed,
        roster_html=ROSTER_HTML,
        coach_html=COACH_HTML,
        roster_url="https://bceagles.com/sports/fencing/roster",
        coach_url="https://bceagles.com/sports/fencing/coaches",
        scraped_at=NOW,
    )

    assert row["college_name"] == "Boston College"
    assert row["division"] == "NCAA I"
    assert row["conference"] == "ACC"
    assert row["weapons"] == ["Epee", "Foil"]
    assert row["gender_teams"] == ["Men", "Women"]
    assert row["roster_size"] == 2
    assert row["scholarship_slots"] == 48
    assert row["head_coach"] == "Brendan Doris-Pierce"
    assert row["coach_email"] == "dorispib@bc.edu"
    assert row["website"] == "https://bceagles.com/"
    assert row["scraped_at"] == NOW
    assert row["metadata"]["source_urls"] == {
        "roster": "https://bceagles.com/sports/fencing/roster",
        "coach": "https://bceagles.com/sports/fencing/coaches",
    }


def test_candidate_urls_include_common_sidearm_roster_and_coach_paths():
    from scrape_college_scholarships import candidate_urls

    urls = candidate_urls("http://bceagles.com/", ["Men", "Women"])

    assert "https://bceagles.com/sports/fencing/roster" in urls
    assert "https://bceagles.com/sports/mens-fencing/roster" in urls
    assert "https://bceagles.com/sports/womens-fencing/coaches" in urls
    assert len(urls) == len(set(urls))


def test_discover_program_pages_does_not_treat_roster_athlete_text_as_coach():
    from scrape_college_scholarships import CollegeProgramSeed, discover_program_pages

    seed = CollegeProgramSeed(
        college_name="Boston College",
        gender_teams=["Men", "Women"],
        website="https://bceagles.com/",
    )

    pages = discover_program_pages(FakeSession(), seed, delay=0)

    assert pages["roster_url"] == "https://bceagles.com/sports/fencing/roster"
    assert pages["coach_url"] == "https://bceagles.com/sports/fencing/coaches"


def test_discover_program_pages_ignores_redirects_to_other_sports():
    from scrape_college_scholarships import CollegeProgramSeed, discover_program_pages

    seed = CollegeProgramSeed(
        college_name="Stanford University",
        gender_teams=["Men", "Women"],
        website="https://gostanford.com/",
    )

    pages = discover_program_pages(RedirectToOtherSportSession(), seed, delay=0)

    assert pages["roster_html"] is None
    assert pages["coach_html"] is None


def test_upsert_scholarship_rows_uses_college_name_conflict_key():
    from scrape_college_scholarships import upsert_scholarship_rows

    fake = FakeSupabase()
    rows = [
        {
            "college_name": "Boston College",
            "division": "NCAA I",
            "conference": "ACC",
        }
    ]

    written = upsert_scholarship_rows(fake, rows)

    assert written == 1
    assert fake.upserts == [
        ("fs_college_scholarships", rows, "college_name"),
    ]


def test_scholarships_migration_defines_table_and_upsert_constraint():
    root = Path(__file__).resolve().parents[1]
    migration = root / "supabase" / "migrations" / "20260601_scholarships.sql"

    sql = migration.read_text()
    normalized = " ".join(sql.lower().split())

    assert "create table if not exists public.fs_college_scholarships" in normalized
    assert "college_name text not null" in normalized
    assert "weapons text[]" in normalized
    assert "gender_teams text[]" in normalized
    assert "unique (college_name)" in normalized
