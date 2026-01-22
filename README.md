# Steam Catalog & BI Ecosystem

The **Steam Data Ecosystem** is a multi-layered integration platform designed to crawl, process, and analyze gaming data. It demonstrates a complete data pipeline across four distinct "worlds," utilizing various communication protocols and native **XML** storage in **PostgreSQL**.

---

## Features

**Automated Scraping:** Python-based crawler that fetches real-time game details from the official Steam Store API.

**Data Enrichment:** Node.js processor that cleans data and performs currency conversion (EUR to USD) using external financial APIs.

**Quality Assurance:** Strict **XSD Validation** layer that ensures all XML documents meet structural requirements before database persistence.

**Native XML Repository:** Centralized storage using PostgreSQL's XML type, allowing for complex **XPath** queries directly on the database engine.

**BI Intelligence:** A high-performance Business Intelligence service that provides a **GraphQL** interface for advanced filtering and metrics.

---

## Tech Stack

**Backend (BI):** Go (Golang).

**Backend (Data):** Python (Flask, lxml, psycopg2).

**Processing:** Node.js.

**Communication:** gRPC (Internal binary), GraphQL (External), and REST/Webhooks (Orchestration).

**Database & Cloud:** PostgreSQL (XML), Supabase (Storage Buckets).

---

## Testing & Monitoring

**Postman Integration:** Use Postman to interact with the **BI Service** via GraphQL. Send `POST` requests to `http://localhost:4000/query` to filter the XML database in real-time.

**Docker Logs:** Monitor the entire data pipeline and service communication using the terminal. Track the flow from file upload to final database persistence.

---

## Usage

The entire ecosystem is containerized using **Docker Compose**. To run the full pipeline locally:

1. **Setup:** Ensure your `.env` file contains the necessary Supabase and Database credentials.
2. **Launch:** Run `docker-compose up --build` from the root directory.
3. **Explore:** Access the GraphQL Playground at `http://localhost:4000/query` to perform BI queries.

---

## Practical Commands

### Viewing Service Logs
To monitor what is happening inside each "World" in real-time:

* **Monitor the Pipeline:** `docker compose logs -f` (Shows all services).

### BI Queries (GraphQL Example)

```graphql
query {
  getGamesByGenre(genre: "Action") {
    totalResults
    games_xml
  }
}
````
- totalResults: Returns the count of games found via XPath.

- games_xml: Returns the raw XML nodes directly from the PostgreSQL table.

### License & Authors
License: Academic use only (Systems Integration).

Development Team: Tomás Silva.
