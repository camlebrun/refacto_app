import streamlit as st
import sqlglot
from sqlglot.optimizer import optimize

# Function to automatically extract a suggested schema
def suggest_schema(query):
    try:
        parsed_query = sqlglot.parse_one(query)
        tables = parsed_query.find_all(sqlglot.exp.Table)
        schema = {table.alias_or_name: {} for table in tables}  # Default empty schema
        return schema
    except Exception:
        return {}

# Function to optimize query
def optimize_query(query, schema):
    try:
        # Parse the query
        parsed_query = sqlglot.parse_one(query)
        
        # Optimize the query
        optimized_query = optimize(parsed_query, schema=schema)
        
        # Extract the optimized query
        optimized_sql = optimized_query.sql(pretty=True)

        # Remove double quotes around table and column names
        optimized_sql = optimized_sql.replace('"', '')  # Remove quotes

        return optimized_sql
    except Exception as e:
        return f"Error during optimization: {str(e)}"

# Streamlit interface
st.title("SQL Query Optimizer 🚀")

# Text area for SQL query
query = st.text_area("✍️ Enter your SQL query here:", height=200)

# Automatically detect tables to help the user
suggested_schema = suggest_schema(query)

# Area to modify the schema
st.markdown("### 📌 Table Schema")
schema_input = st.text_area(
    "Modify the schema if necessary (Format: {table: {column: type}})", 
    value=str(suggested_schema),
    height=100
)

# Convert user input to Python dictionary
try:
    user_schema = eval(schema_input)
except Exception:
    user_schema = {}

# Optimization button
if st.button("🚀 Optimize Query"):
    optimized_query = optimize_query(query, user_schema)
    
    # Display the optimized query
    st.markdown("### ✅ Optimized SQL Query")
    st.text_area("Result:", optimized_query, height=200)