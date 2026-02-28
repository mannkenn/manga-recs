# API Documentation

## Base URL

- Development: `http://localhost:8000`
- Production: TBD

## Interactive Documentation

Once the server is running:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Endpoints

### Health Check

Check if the API is running.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy"
}
```

**Status Codes:**
- `200 OK`: API is running

---

### Get Recommendations

Get manga recommendations based on a given manga title.

**Endpoint:** `POST /api/recommendations`

**Request Body:**
```json
{
  "manga_title": "string",
  "top_n": 10
}
```

**Parameters:**
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| manga_title | string | Yes | - | Title of manga to base recommendations on |
| top_n | integer | No | 10 | Number of recommendations to return (1-50) |

**Example Request:**
```bash
curl -X POST "http://localhost:8000/api/recommendations" \
  -H "Content-Type: application/json" \
  -d '{
    "manga_title": "One Piece",
    "top_n": 5
  }'
```

**Success Response (200 OK):**
```json
{
  "query": "One Piece",
  "matched_title": "One Piece",
  "match_score": 100,
  "recommendations": [
    {
      "id": 13,
      "title": "Naruto",
      "genres": ["Action", "Adventure", "Comedy"],
      "similarity_score": 0.85,
      "average_score": 82,
      "popularity": 150000
    },
    {
      "id": 30013,
      "title": "Fairy Tail",
      "genres": ["Action", "Adventure", "Fantasy"],
      "similarity_score": 0.78,
      "average_score": 75,
      "popularity": 80000
    }
  ]
}
```

**Response Fields:**
| Field | Type | Description |
|-------|------|-------------|
| query | string | Original search query |
| matched_title | string | Best matching manga title found |
| match_score | float | Fuzzy match score (0-100) |
| recommendations | array | List of recommended manga |
| recommendations[].id | integer | Manga ID |
| recommendations[].title | string | Manga title |
| recommendations[].genres | array | List of genres |
| recommendations[].similarity_score | float | Similarity score (0-1) |
| recommendations[].average_score | integer | Average user score (0-100) |
| recommendations[].popularity | integer | Number of users who added this manga |

**Error Responses:**

**404 Not Found** - Manga title not found
```json
{
  "detail": "Manga 'NonexistentManga' not found. Did you mean 'SimilarManga'?"
}
```

**422 Unprocessable Entity** - Validation error
```json
{
  "detail": [
    {
      "loc": ["body", "top_n"],
      "msg": "ensure this value is less than or equal to 50",
      "type": "value_error.number.not_le"
    }
  ]
}
```

**500 Internal Server Error** - Server error
```json
{
  "detail": "An error occurred while processing your request"
}
```

**Status Codes:**
- `200 OK`: Success
- `404 Not Found`: Manga title not found
- `422 Unprocessable Entity`: Invalid request parameters
- `500 Internal Server Error`: Server error

---

## Request/Response Examples

### Example 1: Basic Request

**Request:**
```bash
POST /api/recommendations
Content-Type: application/json

{
  "manga_title": "Attack on Titan"
}
```

**Response:**
```json
{
  "query": "Attack on Titan",
  "matched_title": "Shingeki no Kyojin",
  "match_score": 95,
  "recommendations": [
    {
      "id": 23390,
      "title": "Shingeki no Kyojin: Before the Fall",
      "genres": ["Action", "Drama", "Fantasy"],
      "similarity_score": 0.92,
      "average_score": 78,
      "popularity": 12000
    }
  ]
}
```

### Example 2: Custom Top N

**Request:**
```bash
POST /api/recommendations
Content-Type: application/json

{
  "manga_title": "Death Note",
  "top_n": 3
}
```

### Example 3: Fuzzy Matching

**Request:**
```bash
POST /api/recommendations
Content-Type: application/json

{
  "manga_title": "won peece"
}
```

**Response:**
```json
{
  "query": "won peece",
  "matched_title": "One Piece",
  "match_score": 75,
  "recommendations": [...]
}
```

## Rate Limiting

Currently no rate limiting is implemented on the API. This may be added in future versions.

## Authentication

Currently no authentication is required. This may be added in future versions for user-specific recommendations.

## CORS

CORS is configured to allow requests from:
- `http://localhost:3000` (frontend development)
- Production frontend URL (when deployed)

## Error Handling

All errors follow this format:
```json
{
  "detail": "Error message here"
}
```

For validation errors, the detail includes field-specific information.

## Versioning

Current version: `v1` (implicit)

Future versions will use URL versioning: `/api/v2/recommendations`

## Testing the API

### Using cURL
```bash
curl -X POST http://localhost:8000/api/recommendations \
  -H "Content-Type: application/json" \
  -d '{"manga_title": "Berserk", "top_n": 5}'
```

### Using Python requests
```python
import requests

response = requests.post(
    "http://localhost:8000/api/recommendations",
    json={"manga_title": "Berserk", "top_n": 5}
)

print(response.json())
```

### Using JavaScript fetch
```javascript
fetch('http://localhost:8000/api/recommendations', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    manga_title: 'Berserk',
    top_n: 5
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

## OpenAPI Schema

The full OpenAPI 3.0 schema is available at:
- JSON: `http://localhost:8000/openapi.json`
- Interactive: `http://localhost:8000/docs`
