# s2 - Semantic Scholar CLI

Query academic papers, authors, and citations from the command line.

## Installation

```bash
uv sync
```

## Usage

```bash
# Search papers
s2 search papers "transformer attention mechanism" --limit 10

# Get a specific paper
s2 paper get arXiv:1706.03762 --fields title,abstract,tldr

# Get paper citations
s2 paper citations 10.1038/nature12373 --limit 20

# Search authors
s2 search authors "Geoffrey Hinton"

# Get recommendations
s2 recommend for-paper arXiv:1706.03762 --limit 5
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
