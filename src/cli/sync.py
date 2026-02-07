"""CLI commands for database sync between local and cloud."""

import click


@click.group()
def sync():
    """Sync database between local machine and cloud (GCS).

    Merges cloud-managed tables without overwriting local-only data
    (shooting zones, assist zones, play types, schedules, etc.).
    """
    pass


@sync.command()
@click.option("--dry-run", is_flag=True, help="Preview merge without making changes")
@click.option("--skip-models", is_flag=True, help="Skip syncing trained model files")
@click.pass_context
def pull(ctx, dry_run, skip_models):
    """Merge cloud DB into local (cloud-managed tables only)."""
    from src.db.sync import DatabaseSyncer

    db_path = ctx.obj["db"]
    syncer = DatabaseSyncer(db_path=db_path)

    if dry_run:
        click.echo("DRY RUN - previewing merge (no changes will be made)\n")

    try:
        report = syncer.pull(dry_run=dry_run, skip_models=skip_models)
    except FileNotFoundError as e:
        click.echo(click.style(f"Error: {e}", fg="red"))
        raise SystemExit(1)
    except Exception as e:
        click.echo(click.style(f"Download failed: {e}", fg="red"))
        raise SystemExit(1)

    _print_report(report)


@sync.command()
@click.pass_context
def push(ctx):
    """Upload local DB to cloud (GCS)."""
    from src.db.sync import DatabaseSyncer, GCS_BUCKET

    db_path = ctx.obj["db"]

    if not click.confirm(
        f"Upload {db_path} to gs://{GCS_BUCKET}/nba_stats.db?"
    ):
        click.echo("Aborted.")
        return

    syncer = DatabaseSyncer(db_path=db_path)
    try:
        syncer.push()
        click.echo(click.style("Push complete.", fg="green"))
    except Exception as e:
        click.echo(click.style(f"Push failed: {e}", fg="red"))
        raise SystemExit(1)


@sync.command()
@click.pass_context
def status(ctx):
    """Show row counts for cloud-managed tables."""
    from src.db.sync import DatabaseSyncer

    db_path = ctx.obj["db"]
    syncer = DatabaseSyncer(db_path=db_path)
    counts = syncer.status()

    if not counts:
        click.echo("No cloud-managed tables found in local DB.")
        return

    click.echo(f"{'Table':<25} {'Rows':>10}")
    click.echo("-" * 37)
    total = 0
    for table, count in counts.items():
        click.echo(f"{table:<25} {count:>10,}")
        total += count
    click.echo("-" * 37)
    click.echo(f"{'Total':<25} {total:>10,}")


def _print_report(report):
    """Pretty-print a SyncReport."""
    mode = "DRY RUN" if report.dry_run else "MERGE"

    click.echo(f"{'Table':<25} {'Strategy':<10} {'Cloud':>8} {'Before':>8} {'After':>8} {'New':>8} {'Status':<8}")
    click.echo("-" * 85)

    for r in report.results:
        if r.error:
            status_str = click.style(r.error, fg="yellow")
        elif r.new_rows > 0:
            status_str = click.style(f"+{r.new_rows}", fg="green")
        else:
            status_str = click.style("OK", fg="green")

        after = r.local_after if not report.dry_run else "-"

        click.echo(
            f"{r.table:<25} {r.strategy:<10} {r.cloud_rows:>8,} "
            f"{r.local_before:>8,} {str(after):>8} {r.new_rows:>8,} {status_str}"
        )

        if r.skipped_columns:
            click.echo(
                click.style(
                    f"  warning: cloud-only columns skipped: {', '.join(r.skipped_columns)}",
                    fg="yellow",
                )
            )

    click.echo()

    if report.backup_path:
        click.echo(f"Backup: {report.backup_path}")

    if report.errors:
        click.echo(
            click.style(f"\n{len(report.errors)} table(s) had errors.", fg="yellow")
        )

    if report.dry_run:
        click.echo("\nNo changes made (dry run).")
    else:
        click.echo(
            click.style(
                f"\n{mode} complete: {report.total_new_rows:,} new rows across "
                f"{report.tables_updated} table(s).",
                fg="green",
            )
        )
