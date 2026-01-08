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

## Output Formats

- `json` - JSON object/array (default)
- `jsonl` - One JSON object per line
- `csv` - Comma-separated values
- `record` - Human/LLM readable format
