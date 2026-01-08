---
name: querying-semantic-scholar
description: Search and retrieve academic papers, authors, citations, and references from Semantic Scholar. Use when the user asks about research papers, academic publications, finding papers on a topic, looking up authors, citation counts, or exploring the scientific literature. Triggers include questions about papers, publications, research, citations, authors, h-index, or academic search.
---

# Querying Semantic Scholar

This skill provides access to the Semantic Scholar academic database via the `s2cli` command-line tool.

- **Repository**: https://github.com/mhalle/s2cli
- **Latest skill**: https://github.com/mhalle/s2cli/releases/latest/download/s2cli.skill

## Installation

### Prerequisites

The agent environment must have `uv` installed. If not available, install it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Install the CLI

Run the install script from the skill directory:

```bash
sh scripts/install.sh
```

This installs `s2cli` globally so it's available in PATH.

### Install Script Details

The `scripts/install.sh` script handles installation with these features:

1. **Auto-detects package name** - Extracts from `pyproject.toml` or `SKILL.md`, falls back to directory name
2. **Uses `uv tool install`** (preferred) - Installs the CLI in an isolated environment with its own dependencies, available globally in PATH
3. **Falls back to pip** - If uv is not available, uses `pip install` instead
4. **Supports reinstall** - Use `--force` flag to upgrade or reinstall
5. **Dry-run mode** - Use `--dry-run` to see what would happen without making changes

```bash
# Reinstall/upgrade
sh scripts/install.sh --force

# Preview without installing
sh scripts/install.sh --dry-run
```

### Manual Installation

If you prefer manual installation:

```bash
# With uv (recommended)
uv tool install /path/to/this/skill

# With pip
pip install /path/to/this/skill
```

### Verify Installation

```bash
s2cli --version
s2cli --help
```

## Quick Reference

### Search for Papers

```bash
s2cli search papers "transformer attention mechanism" --limit 10
s2cli search papers "CRISPR gene editing" --year 2020-2024 --min-citations 50
s2cli search papers "climate change" --fields-of-study "Environmental Science"
s2cli search papers "neural networks" --open-access
```

### Get a Specific Paper

```bash
# By DOI
s2cli paper get 10.1038/nature12373

# By ArXiv ID
s2cli paper get arXiv:1706.03762

# With specific fields
s2cli paper get arXiv:1706.03762 --fields title,abstract,tldr,citationCount
```

### Get Citations and References

```bash
# Papers that cite this paper
s2cli paper citations arXiv:1706.03762 --limit 20

# Papers this paper references
s2cli paper references arXiv:1706.03762 --limit 20
```

### Search and Get Authors

```bash
# Search by name
s2cli search authors "Geoffrey Hinton" --limit 5

# Get author details
s2cli author get 1741101 --fields name,hIndex,citationCount,paperCount

# Get an author's papers
s2cli author papers 1741101 --limit 20
```

### Get Recommendations

```bash
# Based on one paper
s2cli recommend for-paper arXiv:1706.03762 --limit 5

# Based on multiple papers
s2cli recommend for-papers arXiv:1706.03762 arXiv:2103.14030 --limit 10
```

### Bulk Operations

```bash
# Get multiple papers
s2cli papers get 10.1038/nature12373 arXiv:1706.03762 arXiv:2103.14030

# From a file
s2cli papers get --file paper_ids.txt

# Piped from another command
s2cli paper references arXiv:1706.03762 | s2cli papers get --stdin --fields title,abstract
```

## Output Formats

Use `--format` or `-f` to control output:

| Format | Description |
|--------|-------------|
| `json` | JSON object/array (default) |
| `jsonl` | One JSON object per line |
| `csv` | Comma-separated values |
| `record` | Human-readable key-value format |

For LLM consumption, use `--format record`:

```bash
s2cli paper get arXiv:1706.03762 --fields title,abstract,tldr -f record
```

## Paper ID Formats

The tool accepts multiple ID formats:

| Format | Example |
|--------|---------|
| DOI | `10.1038/nature12373` |
| ArXiv | `arXiv:1706.03762` |
| PubMed | `PMID:12345678` |
| ACL | `ACL:P18-1234` |
| Corpus ID | `CorpusId:12345` |
| S2 Paper ID | `649def34f8be52c8b66281af98ae884c09aef38b` |

## Available Fields

### Paper Fields

Use `--fields all` for all fields, or select specific ones:

`paperId`, `externalIds`, `url`, `title`, `abstract`, `venue`, `year`, `referenceCount`, `citationCount`, `influentialCitationCount`, `isOpenAccess`, `openAccessPdf`, `fieldsOfStudy`, `publicationTypes`, `publicationDate`, `journal`, `authors`, `tldr`

### Author Fields

`authorId`, `externalIds`, `url`, `name`, `affiliations`, `homepage`, `paperCount`, `citationCount`, `hIndex`

## Common Workflows

### Find influential papers on a topic

```bash
s2cli search papers "large language models" --min-citations 100 --limit 20 -f record
```

### Explore a paper's impact

```bash
# Get the paper
s2cli paper get arXiv:1706.03762 --fields title,citationCount,influentialCitationCount -f record

# See who cited it
s2cli paper citations arXiv:1706.03762 --fields title,year,citationCount --limit 10 -f record
```

### Research an author's work

```bash
# Find the author
s2cli search authors "Yann LeCun" --limit 3 -f record

# Get their papers
s2cli author papers 1741101 --fields title,year,citationCount --limit 20 -f record
```

### Build a reading list

```bash
# Start with a seed paper, get recommendations
s2cli recommend for-paper arXiv:1706.03762 --fields title,abstract,tldr --limit 10 -f record
```

## Error Handling

- Exit code 0: Success
- Exit code 2: Invalid input (missing IDs, file not found)
- Exit code 3: API error (paper not found, rate limit)

Use `--quiet` to suppress error messages when scripting.

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `S2_API_KEY` | Semantic Scholar API key for higher rate limits |
| `S2_OUTPUT_FORMAT` | Default output format: `json`, `jsonl`, `csv`, or `record` |

### Using a .env File

Create a `.env` file in your working directory:

```bash
# Semantic Scholar API Key
# Get one at: https://www.semanticscholar.org/product/api
S2_API_KEY=your-api-key

# Default output format
S2_OUTPUT_FORMAT=json
```

The CLI automatically loads `.env` from the current directory.

### API Key

An API key is optional but recommended for:
- Higher rate limits
- Access to additional features

Get a free API key at: https://www.semanticscholar.org/product/api

You can also pass the key per-command:

```bash
s2cli paper get arXiv:1706.03762 --api-key your-api-key
```
