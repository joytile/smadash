"""
Query Planner and Generator Script

Features:
- Loads schema (JSON or CSV)
- Builds system prompt
- Accepts natural language query as input
- Returns structured query plan + SQL using OpenAI
"""

import os
import json
import argparse
import pandas as pd
from collections import defaultdict
from pprint import pprint
from dotenv import load_dotenv
from openai import OpenAI

# Access the API key
load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))


def load_schema(path="db_schema_moc.json") -> str:
    """Read the database schema JSON file as a raw string."""
    with open(path, "r") as schema:
        return schema.read()
    


def load_schema_csv(path: str = "pg_schema.csv") -> str:
    """Optional: Load database schema from CSV and format as string."""
    df = pd.read_csv(path)

    # Organize by table
    schema_dict = defaultdict(list)
    for _, row in df.iterrows():
        schema_dict[row["table_name"]].append((row["column_name"], row["data_type"]))

    # Format as plain text
    formatted_schema = []
    for table, columns in schema_dict.items():
        formatted_schema.append(f"Table: {table}")
        for col, dtype in columns:
            formatted_schema.append(f"- {col} ({dtype})")
        formatted_schema.append("")

    # Join into final string for LLM
    return "\n".join(formatted_schema)



def build_system_prompt(db_schema: str, dialect: str = "SQLite3") -> str:
    """Build the system prompt for query planning."""

    return f"""
You are a query planner assistant and builder. Your job is to:
1. Convert a user's natural language request into a structured query plan (JSON)
2. Generate a valid SQL SELECT statement based on that plan

Use the following database schema:
{db_schema}


Additional instructions:
- SQL must be valid for {dialect}.
- Operators: "=", "between" (value = [start,end]), "like" (wrap with %), ">", "<".
- **Display-field policy**
  - The SELECT list MUST include at least one non-ID, human-readable text column for each entity displayed.
  - Preferred display fields (in order): full_name, name, title, label, description, email, (first_name || ' ' || last_name), username.
  - If none exist, choose the longest TEXT/VARCHAR column as a fallback and add a "warning".
- **Join policy**
  - When using a foreign key, JOIN the referenced table to fetch its display field.
  - Use table aliases and readable column aliases.
- **Prohibit**: SELECT *; results that contain only IDs.
- **Validation checklist (the model must self-check before returning)**:
  1) At least one non-ID text column is selected per entity.
  2) All FKs shown have JOINs to pull display fields.
  3) GROUP BY includes all non-aggregated selected columns (per {dialect} rules).
  4) Only schema-listed tables/columns are used.

Extend the JSON format with display choices:
{{
  "query_plan": {{
    "intent": "ranking" | "trend" | "filter" | "comparison",
    "table": "sales_data",
    "filters": [ {{ "field": ..., "operator": ..., "value": ... }} ],
    "metrics": [ {{ "name": ..., "aggregation": ..., "alias": ... }} ],
    "group_by": [...],
    "sort": [ {{ "field": ..., "order": "asc" | "desc" }} ],
    "limit": ...,
    "display_fields": {{
      "customers": ["customer_name", "email"], 
      "orders": ["order_date"]
    }},
    "joins": [
      {{ "from_table": "orders", "from_key": "customer_id", "to_table": "customers", "to_key": "customer_id", "type": "INNER" }}
    ],
    "original_user_query": ...
  }},
  "sql": "SELECT ... FROM ... JOIN ...",
  "warning": "Only IDs available in table X; used column Y as fallback"
}}

Only return valid JSON output.
"""


def get_plan_and_sql(system_prompt: str, user_query: str, model: str = "gpt-4o-mini") -> dict:
    """Call OpenAI to generate query plan + SQL."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY env variable")
    client = OpenAI(api_key=api_key)
    
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        temperature=0.2
    )
    content = response.choices[0].message.content.strip()

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"error": "Invalid JSON returned", "raw_output": content}




def main():
    parser = argparse.ArgumentParser(description="Query Planner CLI")
    parser.add_argument("query", type=str, nargs="?", help="Natural language query to convert into SQL")
    parser.add_argument("--schema", type=str, default="/Users/mac/Documents/Projects/SMADASH/db_schema_moc.json",
                        help="Path to schema file (JSON or CSV)")
    parser.add_argument("--dialect", type=str, default="SQLite3", help="SQL dialect")
    args = parser.parse_args()


    # If no query passed, ask interactively
    user_query = args.query or input("Enter your natural language query: ")


    # Load schema
    if args.schema.endswith(".json"):
        db_schema = load_schema(args.schema)
    elif args.schema.endswith(".csv"):
        db_schema = load_schema_csv(args.schema)
    else:
        raise ValueError("Schema must be a .json or .csv file")
    
    #Build system prompt
    system_prompt = build_system_prompt(db_schema, args.dialect)

    # Run query planner
    result = get_plan_and_sql(system_prompt, user_query)
    print(result)


if __name__ == "__main__":
    main()



