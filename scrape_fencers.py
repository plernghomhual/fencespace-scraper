#!/usr/bin/env python3
"""Compatibility entry point for scraping fencer profiles."""
import scrape_athlete_profiles


def main(limit=0):
    if limit and limit > 0:
        scrape_athlete_profiles.MAX_FENCERS = limit
    scrape_athlete_profiles.scrape_athlete_profiles()


if __name__ == "__main__":
    main()
