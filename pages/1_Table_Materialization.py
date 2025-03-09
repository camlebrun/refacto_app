import streamlit as st
import json
import pandas as pd
import plotly.express as px
from pathlib import Path

# Page configuration
st.set_page_config(page_title="dbt Table Materialization Explorer", page_icon="📊", layout="wide")

# Main title
st.markdown("<h1 style='text-align: center;'>dbt Table Materialization Explorer</h1>", unsafe_allow_html=True)

# Description
st.markdown("""
This app analyzes your dbt manifest file to provide insights into your dbt models.
You can upload your `manifest.json` file to get started.
""")

# Function to process manifest
def process_manifest(manifest):
    model_configs = []
    for node_id, node in manifest.get('nodes', {}).items():
        if node.get('resource_type') == 'model':
            partition_info = node.get('config', {}).get('partition_by', None)
            cluster_info = node.get('config', {}).get('cluster_by', None)

            config = {
                'model_name': node.get('name', ''),
                'schema': node.get('schema', ''),
                'materialized': node.get('config', {}).get('materialized', 'view'),
                'partitioned': bool(partition_info),  # Boolean indicator
                'clustered': bool(cluster_info),  # Boolean indicator
                'partition_details': json.dumps(partition_info) if partition_info else "None",
                'cluster_details': json.dumps(cluster_info) if cluster_info else "None",
                'full_path': node.get('original_file_path', ''),
                'tags': ', '.join(node.get('tags', [])),
                'depends_on_count': len(node.get('depends_on', {}).get('nodes', [])),
                'columns_count': len(node.get('columns', {})),
                'folder': Path(node.get('original_file_path', '')).parent.name if node.get('original_file_path', '') else ''
            }
            model_configs.append(config)
    df = pd.DataFrame(model_configs)
    return df

# Function to generate key metrics
def display_key_metrics(df):
    st.markdown("<div class='sub-header'>Key Metrics</div>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='metric-value'>{len(df)}</div>", unsafe_allow_html=True)
        st.markdown("<div class='metric-label'>Total Models</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='metric-value'>{df['schema'].nunique()}</div>", unsafe_allow_html=True)
        st.markdown("<div class='metric-label'>Number of Schemas</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col3:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='metric-value'>{df[df['materialized'] == 'table'].shape[0]}</div>", unsafe_allow_html=True)
        st.markdown("<div class='metric-label'>Total Tables</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    col4, col5, col6 = st.columns(3)
    with col4:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='metric-value'>{df[df['partitioned']].shape[0]}</div>", unsafe_allow_html=True)
        st.markdown("<div class='metric-label'>Tables with Partitioning</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col5:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='metric-value'>{df[df['clustered']].shape[0]}</div>", unsafe_allow_html=True)
        st.markdown("<div class='metric-label'>Tables with Clustering</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with col6:
        st.markdown("<div class='card'>", unsafe_allow_html=True)
        st.markdown(f"<div class='metric-value'>{df[df['partitioned'] & df['clustered']].shape[0]}</div>", unsafe_allow_html=True)
        st.markdown("<div class='metric-label'>Tables with Partition & Cluster</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# File upload option
uploaded_file = st.file_uploader("Upload your manifest.json file", type=["json"])

df = None
if uploaded_file is not None:
    try:
        manifest = json.load(uploaded_file)
        df = process_manifest(manifest)
        st.success(f"Manifest loaded successfully: {len(df)} models found")
    except json.JSONDecodeError:
        st.error("Error: Invalid JSON file. Please upload a valid manifest.json file.")
    except KeyError as e:
        st.error(f"Error: Missing key in manifest: {str(e)}. Please check your file.")
    except Exception as e:
        st.error(f"An unexpected error occurred: {str(e)}")

# If we have data, display the dashboard
if df is not None and not df.empty:
    display_key_metrics(df)

    # Distribution by Materialization Type
    st.markdown("<div class='sub-header'>Distribution by Materialization Type</div>", unsafe_allow_html=True)
    mat_counts = df['materialized'].value_counts().reset_index()
    mat_counts.columns = ['Type', 'Count']
    fig_pie = px.pie(mat_counts, values='Count', names='Type', color_discrete_sequence=px.colors.sequential.Blues_r, hole=0.4)
    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
    fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0))
    st.plotly_chart(fig_pie, use_container_width=True)

    # Display data in an interactive table
    st.markdown("<div class='sub-header'>Model Data</div>", unsafe_allow_html=True)
    st.dataframe(df)

    # Export options
    st.markdown("<div class='sub-header'>Export Data</div>", unsafe_allow_html=True)
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button(label="Download as CSV", data=csv, file_name='dbt_model_audit.csv', mime='text/csv', key='download-csv')

    try:
        import io
        from io import BytesIO
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Models')
        excel_data = output.getvalue()
        st.download_button(label="Download as Excel", data=excel_data, file_name='dbt_model_audit.xlsx', mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', key='download-excel')
    except ImportError:
        st.warning("The openpyxl library is not installed. Excel export is not available.")
else:
    st.info("Please upload your manifest.json file to start analyzing your dbt models.")