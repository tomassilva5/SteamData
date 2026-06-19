# Steam Catalog & BI Ecosystem

![Go](https://img.shields.io/badge/Go-00ADD8?logo=go&logoColor=white)
![Python](https://img.shields.io/badge/Python-3-blue?logo=python)
![Node.js](https://img.shields.io/badge/Node.js-339933?logo=nodedotjs&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?logo=postgresql&logoColor=white)
![GraphQL](https://img.shields.io/badge/GraphQL-E10098?logo=graphql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

## Project Overview

The **Steam Data Ecosystem** is a multi-layered integration platform designed to crawl, process, and analyze gaming data. It demonstrates a complete data pipeline across four distinct "worlds," utilizing various communication protocols and native **XML** storage in **PostgreSQL**.

---

## What's Inside

| Feature | Description |
|---|---|
| **Automated Scraping** | Python-based crawler that fetches real-time game details from the official Steam Store API. |
| **Data Enrichment** | Node.js processor that cleans data and performs currency conversion (EUR to USD) using external financial APIs. |
| **Quality Assurance** | Strict **XSD Validation** layer that ensures all XML documents meet structural requirements before database persistence. |
| **Native XML Repository** | Centralized storage using PostgreSQL's XML type, allowing for complex **XPath** queries directly on the database engine. |
| **BI Intelligence** | A high-performance Business Intelligence service that provides a **GraphQL** interface for advanced filtering and metrics. |

---

## Tech Stack

- **Backend (BI):** Go (Golang)
- **Backend (Data):** Python (Flask, lxml, psycopg2)
- **Processing:** Node.js
- **Communication:** gRPC (Internal binary), GraphQL (External), and REST/Webhooks (Orchestration)
- **Database & Cloud:** PostgreSQL (XML), Supabase (Storage Buckets)

---

## Testing & Monitoring

- **Postman Integration:** Use Postman to interact with the **BI Service** via GraphQL. Send `POST` requests to `http://localhost:4000/query` to filter the XML database in real-time.
- **Docker Logs:** Monitor the entire data pipeline and service communication using the terminal. Track the flow from file upload to final database persistence.

---

## How to Run the Project

The entire ecosystem is containerized using **Docker Compose**. To run the full pipeline locally:

**1. Setup Environment:**
Ensure your `.env` file contains the necessary Supabase and Database credentials.

**2. Launch Application:**
Run the following command from the root directory:

```bash
docker-compose up --build
```

**3. Explore:**
Access the GraphQL Playground at `http://localhost:4000/query` to perform BI queries.

---

## Practical Commands

### Viewing Service Logs

To monitor what is happening inside each "World" in real-time, tracking all services:

```bash
docker compose logs -f
```

### BI Queries (GraphQL Example)

```graphql
query {
  getGamesByGenre(genre: "Action") {
    totalResults
    games_xml
  }
}
```

- `totalResults`: Returns the count of games found via XPath.
- `games_xml`: Returns the raw XML nodes directly from the PostgreSQL table.

---

© Steam Catalog & BI Ecosystem | Developed by Tomás Silva
