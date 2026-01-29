# Step1: Extract Schema
from sqlalchemy import create_engine, inspect
import json
import re
import os
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
from langchain_groq import ChatGroq
import psycopg2

load_dotenv()

# PostgreSQL Connection URL (Render Database)
db_url = "postgresql://auto:CmRtuCNZsGJMMdz5uhhYaVblhF89rfGQ@dpg-d5l8fvu3jp1c7395g140-a.singapore-postgres.render.com:5432/bitebuddy_adpp"

def extract_schema(db_url):
    engine = create_engine(db_url)
    inspector = inspect(engine)
    schema = {}

    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        schema[table_name] = [col['name'] for col in columns]
    return json.dumps(schema)


# Step2: Text to SQL with User Context
def text_to_sql(schema, prompt, user_id, role):
    SYSTEM_PROMPT = """
Expert PostgreSQL query generator. Use only provided schema tables/columns.

CRITICAL RULES:
- order_status: 'PENDING', 'COMPLETED', 'DELIVERED' (case-sensitive)
- Sales queries: Filter WHERE order_status = 'DELIVERED'
- "Nth order" = position in list → Use LIMIT 1 OFFSET N-1
- Restaurant names: Use ILIKE (e.g., WHERE name ILIKE '%Punjab%')
- INSERT: Never include 'id' (auto-generated)

SECURITY (MANDATORY):
- ROLE_CUSTOMER: Filter customer_id = {user_id}
- ROLE_RESTAURANT_OWNER: Filter restaurant.owner_id = {user_id}
- ROLE_ADMIN: Access all data
- UPDATE/DELETE: ALWAYS add ownership check:
  * Owner: AND restaurant_id IN (SELECT id FROM restaurant WHERE owner_id = {user_id})
  * Customer: AND customer_id = {user_id}

Output SQL only. No explanation.
"""

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("user", "Schema:\n{schema}\n\nUser Context:\n- User ID: {user_id}\n- Role: {role}\n\nQuestion: {user_prompt}\n\nSQL Query:")
    ])

    model = ChatGroq(
        model="llama-3.3-70b-versatile", 
        temperature=0,
        api_key=os.getenv("groq_api")
    )

    chain = prompt_template | model

    raw_response = chain.invoke({
        "schema": schema, 
        "user_prompt": prompt,
        "user_id": user_id,
        "role": role
    })
    
    # Clean the response - remove markdown code blocks
    cleaned_response = raw_response.content.strip()
    cleaned_response = re.sub(r'```sql\s*', '', cleaned_response)
    cleaned_response = re.sub(r'```\s*$', '', cleaned_response)
    cleaned_response = cleaned_response.strip()
    
    return cleaned_response


def get_data_from_database(prompt, user_id=1, role="ROLE_CUSTOMER"):
    #  Validate user_id
    if user_id is None or user_id == "None":
        return {"error": "Authentication failed: user_id not found in token"}
    
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return {"error": f"Invalid user_id: {user_id}"}
    
    schema = extract_schema(db_url)
    print(f"📊 SCHEMA: {schema[:200]}...")
    
    sql_query = text_to_sql(schema, prompt, user_id, role)
    print(f"🔍 GENERATED SQL: {sql_query}")
    print(f"👤 USER CONTEXT: user_id={user_id}, role={role}")
    
    # PostgreSQL Connection
    conn = psycopg2.connect(
        host="dpg-d5l8fvu3jp1c7395g140-a.singapore-postgres.render.com",
        port=5432,
        database="bitebuddy_adpp",
        user="auto",
        password="CmRtuCNZsGJMMdz5uhhYaVblhF89rfGQ"
    )
    cursor = conn.cursor()
    
    try:
        cursor.execute(sql_query)
        if sql_query.strip().upper().startswith('SELECT'):
            results = cursor.fetchall()
            columns = [desc[0] for desc in cursor.description]
            results = [dict(zip(columns, row)) for row in results]
        else:
            conn.commit()
            results = {"message": "Query executed successfully", "affected_rows": cursor.rowcount}
    except Exception as e:
        print(f"❌ SQL Error: {str(e)}")
        results = {"error": str(e)}
    finally:
        conn.close()
    
    return results