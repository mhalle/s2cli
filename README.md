# s2cli - Semantic Scholar CLI

Unofficial command-line interface for querying academic papers, authors, and citations.

## Installation

```bash
uv sync
```

## Usage

```bash
# Search papers
s2cli search papers "transformer attention mechanism" --limit 10

# Get a specific paper
s2cli paper get arXiv:1706.03762 --fields title,abstract,tldr

# Get paper citations
s2cli paper citations 10.1038/nature12373 --limit 20

# Search authors
s2cli search authors "Geoffrey Hinton"

# Get recommendations
s2cli recommend for-paper arXiv:1706.03762 --limit 5
```

## Configuration

Set your API key via environment variable or `.env` file:

```bash
export S2_API_KEY=your-api-key
```

## Citation Trees

Build and maintain local SQLite databases of citation networks:

```bash
# Add papers and crawl their citations
s2cli citetree add PMID:12345678 --db papers.db --depth 2

# Use a YAML config file
s2cli citetree add --config citetree.yaml --db papers.db

# CLI flags override config settings
s2cli citetree add --config citetree.yaml --db papers.db --depth 1

# Check database status
s2cli citetree status --db papers.db
```

### YAML Config Format

```yaml
# citetree.yaml
depth: 2
direction: citations  # or "references"
limit: 1000
influential_only: false

papers:
  - id: "PMID:12345678"
    title: "Paper title (for documentation)"
  - id: "arXiv:1706.03762"
  - "DOI:10.1234/example"  # plain string also valid
```

## Output Formats

- `json` - JSON object/array (default)
- `jsonl` - One JSON object per line
- `csv` - Comma-separated values
- `record` - Human/LLM readable format
