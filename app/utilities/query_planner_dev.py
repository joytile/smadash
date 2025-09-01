pip install openai

import re
import pandas as pd
from collections import defaultdict
from datetime import datetime
from typing import Dict, List
from pprint import pprint
from openai import OpenAI
import os
import json

from pprint import pprint

from google.colab import userdata
import os
from openai import OpenAI

# Access the API key from Colab's Secrets Manager
client = OpenAI(
  api_key=userdata.get('OPENAI_API_KEY')
)

with open("db_schema_moc.json", "r") as schema:
    db_schema = schema.read()

# # Load the schema CSV
# df = pd.read_csv("pg_schema.csv")

# # Organize by table
# schema_dict = defaultdict(list)
# for _, row in df.iterrows():
#     schema_dict[row["table_name"]].append((row["column_name"], row["data_type"]))

# # Format as plain text
# formatted_schema = []
# for table, columns in schema_dict.items():
#     formatted_schema.append(f"Table: {table}")
#     for col, dtype in columns:
#         formatted_schema.append(f"- {col} ({dtype})")
#     formatted_schema.append("")

# # Join into final string for LLM
# db_schema = "\n".join(formatted_schema)
# print(db_schema)


dialect = "SQLite3"

SYSTEM_PROMPT = f"""
You are a query planner assistant and builder. Your job is to:
1. Convert a user's natural language request into a structured query plan (JSON)
2. Generate a valid SQL SELECT statement based on that plan

Use the following database schema:
{db_schema}

You must support the following operators:
- "=" for exact match (e.g., field = 'value')
- "between" for range filters (e.g., dates or numeric ranges)
- "like" for partial matches (e.g., names or categories)
- ">" and "<" for comparisons

Use this strict JSON format:
{{
  "query_plan": {{
    "intent": "ranking" | "trend" | "filter" | "comparison",
    "table": "sales_data",
    "filters": [ {{ "field": ..., "operator": ..., "value": ... }} ],
    "metrics": [ {{ "name": ..., "aggregation": ..., "alias": ... }} ],
    "group_by": [...],
    "sort": [ {{ "field": ..., "order": "asc" | "desc" }} ],
    "limit": ...,
    "original_user_query": ...
  }},
  "sql": "SELECT ... FROM ..."
}}

Additional instructions:
- The SQL must be valid for {dialect}. Use {dialect}-specific syntax, data types, and functions where appropriate.
- If using the "between" operator, the value must be a 2-element array: [start, end]
- If using the "like" operator, wrap the value in % signs for partial match (e.g., '%phone%')
- Output must be valid JSON only
- Use only tables and fields from the schema above
- Output the SQL statement as one statement

Only return valid JSON output.
"""


def get_plan_and_sql(user_query: str) -> dict:
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",  # or gpt-3.5-turbo
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_query}
        ],
        temperature=0.2
    )
    content = response.choices[0].message.content.strip()

    try:
        plan = json.loads(content)
        return plan
    except json.JSONDecodeError:
        print("❌ Failed to parse LLM output as JSON.")
        print(content)
        return {}

user_query = "Show me the top 5 events with highest sales in Q2 2024"

user_query2 = "Which venues in LA had the most events?"

plan = get_plan_and_sql(user_query)

pprint(plan)

plan['sql']


