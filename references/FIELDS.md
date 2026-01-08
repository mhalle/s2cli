# Semantic Scholar Field Reference

## Paper Fields

| Field | Type | Description |
|-------|------|-------------|
| `paperId` | string | Semantic Scholar unique identifier |
| `externalIds` | object | External IDs: DOI, ArXiv, PubMed, ACL, etc. |
| `url` | string | Semantic Scholar URL |
| `title` | string | Paper title |
| `abstract` | string | Paper abstract |
| `venue` | string | Publication venue (journal/conference name) |
| `year` | integer | Publication year |
| `referenceCount` | integer | Number of papers this paper cites |
| `citationCount` | integer | Number of papers citing this paper |
| `influentialCitationCount` | integer | Citations that significantly influenced citing paper |
| `isOpenAccess` | boolean | Whether open access PDF is available |
| `openAccessPdf` | object | Open access PDF URL and status |
| `fieldsOfStudy` | array | Academic fields (Computer Science, Medicine, etc.) |
| `publicationTypes` | array | Types: JournalArticle, Conference, Review, etc. |
| `publicationDate` | string | Full publication date (YYYY-MM-DD) |
| `journal` | object | Journal name and volume info |
| `authors` | array | List of authors with IDs and names |
| `tldr` | object | AI-generated one-sentence summary |

### Default Paper Fields

When no `--fields` specified: `paperId`, `externalIds`, `title`, `year`, `authors`, `citationCount`

### Publication Types

- `JournalArticle` - Peer-reviewed journal paper
- `Conference` - Conference paper
- `Review` - Review/survey paper
- `Book` - Book or book chapter
- `Dataset` - Dataset publication
- `Patent` - Patent document

### Fields of Study

Common values: `Computer Science`, `Medicine`, `Biology`, `Physics`, `Chemistry`, `Mathematics`, `Engineering`, `Environmental Science`, `Psychology`, `Economics`

## Author Fields

| Field | Type | Description |
|-------|------|-------------|
| `authorId` | string | Semantic Scholar author ID |
| `externalIds` | object | External IDs (ORCID, DBLP, etc.) |
| `url` | string | Semantic Scholar profile URL |
| `name` | string | Author name |
| `affiliations` | array | Current institutional affiliations |
| `homepage` | string | Author's homepage URL |
| `paperCount` | integer | Total number of papers |
| `citationCount` | integer | Total citation count |
| `hIndex` | integer | h-index metric |

### Default Author Fields

When no `--fields` specified: `authorId`, `name`, `affiliations`, `paperCount`, `citationCount`, `hIndex`

## Search Filters

### Paper Search

| Filter | Example | Description |
|--------|---------|-------------|
| `--year` | `2020`, `2018-2022`, `2020-` | Publication year or range |
| `--venue` | `Nature`, `NeurIPS` | Filter by venue/journal |
| `--open-access` | flag | Only open access papers |
| `--fields-of-study` | `Computer Science` | Filter by field |
| `--min-citations` | `100` | Minimum citation count |
| `--publication-types` | `Review` | Filter by type |

### Recommendation Pools

| Pool | Description |
|------|-------------|
| `recent` | Recent papers (default) |
| `all-cs` | All computer science papers |
