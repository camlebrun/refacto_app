import streamlit as st

# Set page layout and title
st.set_page_config(
    page_title="DBT Model Auditor",
    page_icon="📊",
    layout="wide"
)

# Page title and introduction
st.title("Welcome to the DBT Model Auditor App 📊")

# Introduction Text for DBT Manifest
st.markdown("""
This app provides tools for analyzing your **dbt manifest.json** file and your **DBT logs**.  
The main features of this application are:
""")

# Section 1: DBT Model Analysis
st.markdown("""
### 1. DBT Model Analysis
This feature allows you to analyze your **dbt manifest.json** file.  
You will gain insights into your **dbt models**, including details about materializations, partitions, clusters, dependencies, and more. This helps you to understand how your DBT models are structured and managed.
""")

# Section 2: DBT Logs Analysis and BigQuery Cost Optimization
st.markdown("""
### 2. DBT Logs Analysis and BigQuery Cost Optimization
This feature allows you to analyze your **DBT logs**.  
You will gain insights into your **DBT runs** and receive **cost optimization recommendations** for **BigQuery** queries. This helps you identify potential inefficiencies in your DBT jobs and optimize the cost of running queries on BigQuery.
""")

# Section 3: SQL Query Optimization with SQLflot
st.markdown("""
### 3. SQL Query Optimization with SQLglot
This feature allows you to optimize your **SQL queries** using **SQLflot**.  
You can paste your SQL queries into the application, and it will suggest optimizations to improve performance, especially when using BigQuery.
""")

# Conclusion
st.markdown("""
Feel free to navigate through the menu on the left to explore these features further.
""")