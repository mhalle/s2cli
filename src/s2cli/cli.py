"""Main CLI entry point."""

from typing import Annotated

import typer

from . import __version__
from .commands import author, authors, citetree, paper, papers, recommend, search

EXIT_CODES_HELP = (
    "[dim]Exit codes:[/dim] "
    "[cyan]0[/cyan]=success, "
    "[cyan]1[/cyan]=not found, "
    "[cyan]2[/cyan]=input error, "
    "[cyan]3[/cyan]=API error, "
    "[cyan]4[/cyan]=rate limited (retriable)"
)

app = typer.Typer(
    name="s2cli",
    help="Semantic Scholar CLI - Query academic papers, authors, and citations.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
    epilog=EXIT_CODES_HELP,
    rich_markup_mode="rich",
)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit",
        ),
    ] = False,
):
    """Semantic Scholar CLI - Query academic papers, authors, and citations.

    All output is JSON by default. Use --format on any command to change.
    """
    if version:
        print(f"s2cli version {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()


# Register subcommands
app.add_typer(paper.app, name="paper", help="Query individual papers")
app.add_typer(papers.app, name="papers", help="Bulk paper operations")
app.add_typer(author.app, name="author", help="Query individual authors")
app.add_typer(authors.app, name="authors", help="Bulk author operations")
app.add_typer(search.app, name="search", help="Search papers or authors")
app.add_typer(recommend.app, name="recommend", help="Get paper recommendations")
app.add_typer(citetree.app, name="citetree", help="Build and manage citation trees")


if __name__ == "__main__":
    app()
