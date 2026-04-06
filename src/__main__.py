import sys

subcommands = ["scrape", "apply", "stats"]

if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
    print("Usage: python -m src <command> [options]")
    print("Commands:")
    print("  scrape  - Aggregate job listings from all platforms")
    print("  apply   - Send applications to queued jobs")
    print("  stats   - Show job queue statistics")
    print("")
    print("Examples:")
    print("  python -m src scrape --platforms linkedin dice")
    print("  python -m src apply --limit 10 --dry-run")
    print("  python -m src stats")
    sys.exit(1)

command = sys.argv[1]
sys.argv = [sys.argv[0]] + sys.argv[2:]

if command == "scrape":
    from .scraper_cli import run_scraper_cli

    run_scraper_cli()
elif command == "apply":
    from .applier_cli import run_applier_cli

    run_applier_cli()
elif command == "stats":
    from .queue.job_queue import JobQueue

    queue = JobQueue()
    stats = queue.get_stats()
    print("\n=== Job Queue Stats ===")
    print(f"Total: {stats['total']}")
    print(f"Pending: {stats['pending']}")
    print(f"Applied: {stats['applied']}")
    print(f"Failed: {stats['failed']}")
    print("\nBy Platform:")
    for platform, count in stats["by_platform"].items():
        print(f"  {platform}: {count}")
else:
    print(f"Unknown command: {command}")
    print(f"Available commands: {subcommands}")
    sys.exit(1)
