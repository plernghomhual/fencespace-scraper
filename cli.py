#!/usr/bin/env python3
"""
Usage:
  python cli.py results [--season YEAR] [--weapon WEAPON] [--limit N]
  python cli.py discover-urls [--season YEAR]
  python cli.py fencers [--limit N]
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="FenceSpace scraper CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    # results sub-command
    r = sub.add_parser("results", help="Scrape competition results")
    r.add_argument("--season", type=int, help="Season year (e.g. 2026)")
    r.add_argument("--weapon", choices=["foil", "epee", "sabre"], help="Filter by weapon")
    r.add_argument("--limit", type=int, default=0, help="Max tournaments to scrape (0 = all)")

    # discover-urls sub-command
    d = sub.add_parser("discover-urls", help="Discover competition URL IDs")
    d.add_argument("--season", type=int, help="Season year to search")

    # fencers sub-command
    f = sub.add_parser("fencers", help="Scrape fencer profiles")
    f.add_argument("--limit", type=int, default=0)

    args = parser.parse_args()

    if args.command == "results":
        from scrape_results import main as scrape_results_main
        scrape_results_main(season=args.season, weapon=args.weapon, limit=args.limit)
    elif args.command == "discover-urls":
        from scrape_results import discover_urls_main
        discover_urls_main(season=args.season)
    elif args.command == "fencers":
        from scrape_fencers import main as scrape_fencers_main
        scrape_fencers_main(limit=args.limit)


if __name__ == "__main__":
    main()
