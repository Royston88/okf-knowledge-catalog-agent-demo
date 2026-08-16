from google.cloud import bigquery

def execute_sql(sql_query: str) -> dict:
    """Executes a SQL query on BigQuery and returns the results.

    Args:
        sql_query: The SQL query string to execute.
    """
    try:
        client = bigquery.Client()
        # Ensure we use the correct project
        query_job = client.query(sql_query)
        results = query_job.result()
        rows = [dict(row) for row in results]
        # Convert non-serializable objects (like date) to string
        for row in rows:
            for k, v in row.items():
                if not isinstance(v, (str, int, float, bool, type(None))):
                    row[k] = str(v)
        return {"status": "success", "rows": rows[:50]} # Limit to 50 rows for safety
    except Exception as e:
        return {"status": "error", "message": f"SQL execution failed: {str(e)}"}
