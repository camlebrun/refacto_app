import re
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime

def parse_dbt_log(log_content):
    """Parse DBT logs and return a structured dictionary"""
    parsed_data = {
        'dbt_version': None,
        'adapter': {},
        'resource_counts': {},
        'concurrency': {},
        'models': [],
        'summary': {},
        'success': False,
        'stats': {}
    }

    lines = log_content.split('\n')
    current_models = {}

    for line in lines:
        line = line.strip()

        # Parse dbt version
        if 'Running with dbt=' in line:
            match = re.search(r'dbt=([\d.]+)', line)
            if match:
                parsed_data['dbt_version'] = match.group(1)

        # Parse adapter info
        if 'Registered adapter:' in line:
            match = re.search(r'Registered adapter: (\w+)=([\d.]+)', line)
            if match:
                parsed_data['adapter'] = {
                    'name': match.group(1),
                    'version': match.group(2)
                }

        # Parse resource counts
        if 'Found' in line and 'models' in line:
            match = re.search(r'Found (\d+) models, (\d+) seeds, (\d+) sources, (\d+) macros', line)
            if match:
                parsed_data['resource_counts'] = {
                    'models': int(match.group(1)),
                    'seeds': int(match.group(2)),
                    'sources': int(match.group(3)),
                    'macros': int(match.group(4))
                }

        # Parse concurrency
        if 'Concurrency:' in line:
            match = re.search(r'Concurrency: (\d+) threads \(target=\'([^\']+)\'\)', line)
            if match:
                parsed_data['concurrency'] = {
                    'threads': int(match.group(1)),
                    'target': match.group(2)
                }

        # Parse model start
        if 'START sql' in line and '[RUN]' in line:
            match = re.search(r'(\d+:\d+:\d+)\s+(\d+) of (\d+) START (sql \w+ model) ([^\s\.]+\.[^\s\.]+)', line)
            if match:
                timestamp = match.group(1)
                model_number = int(match.group(2))
                total_models = int(match.group(3))
                model_type = match.group(4)
                model_name = match.group(5).strip()

                # Extract layer (bronze, silver, gold) and model type
                layer = model_name.split('.')[0] if '.' in model_name else 'other'

                model_info = {
                    'start_time': timestamp,
                    'model_number': model_number,
                    'total_models': total_models,
                    'model_type': model_type,
                    'model_name': model_name,
                    'layer': layer,
                    'status': 'started'
                }
                current_models[model_name] = model_info

        # Parse model completion
        if 'OK created sql' in line:
            # To capture: 09:02:05  1 of 10 OK created sql incremental model bronze.sales_data .................. [MERGE (10000000.0 rows, 10000.0 MiB processed) in 120.0s]
            match = re.search(r'(\d+:\d+:\d+)\s+(\d+) of (\d+) OK created (sql \w+ model) ([^\s\.]+\.[^\s\.]+)', line)
            if match:
                timestamp = match.group(1)
                model_name = match.group(5).strip()

                # Extract performance information
                perf_match = re.search(r'\[(MERGE|CREATE TABLE|CREATE VIEW) \(([\d.]+) rows, ([\d.]+) MiB processed\) in ([\d.]+)s\]', line)
                if perf_match and model_name in current_models:
                    operation_type = perf_match.group(1)
                    rows = float(perf_match.group(2))
                    size_mb = float(perf_match.group(3))
                    duration = float(perf_match.group(4))

                    # Extract model type (incremental, table, view)
                    model_type_full = current_models[model_name]['model_type']
                    model_type_short = model_type_full.split(' ')[1] if len(model_type_full.split(' ')) > 1 else "unknown"

                    model = current_models[model_name]
                    model.update({
                        'end_time': timestamp,
                        'operation_type': operation_type,
                        'rows_processed': rows,
                        'data_processed_mb': size_mb,
                        'duration_seconds': duration,
                        'efficiency_ratio_kb': (size_mb * 1024 / rows) if rows > 0 else 0,
                        'rows_per_second': rows / duration if duration > 0 else 0,
                        'mb_per_second': size_mb / duration if duration > 0 else 0,
                        'model_type_short': model_type_short,
                        'status': 'completed'
                    })
                    parsed_data['models'].append(model)
                    del current_models[model_name]

        # Parse summary
        if 'Finished running' in line:
            model_types = {}
            match_types = re.search(r'Finished running ((?:\d+ \w+ models, )*\d+ \w+ models)', line)
            if match_types:
                types_str = match_types.group(1)
                for type_count in types_str.split(', '):
                    count, type_name = type_count.split(' ', 1)
                    model_types[type_name.replace(' models', '')] = int(count)
                parsed_data['summary']['model_types'] = model_types

            match_time = re.search(r'in (\d+) hours (\d+) minutes and ([\d.]+) seconds \(([\d.]+)s\)', line)
            if match_time:
                total_seconds = float(match_time.group(4))
                parsed_data['summary']['total_time_seconds'] = total_seconds

        # Parse final stats
        if 'Done.' in line and 'PASS=' in line:
            match = re.search(r'PASS=(\d+) WARN=(\d+) ERROR=(\d+) SKIP=(\d+) TOTAL=(\d+)', line)
            if match:
                parsed_data['stats'] = {
                    'pass': int(match.group(1)),
                    'warn': int(match.group(2)),
                    'error': int(match.group(3)),
                    'skip': int(match.group(4)),
                    'total': int(match.group(5))
                }
                parsed_data['success'] = int(match.group(1)) == int(match.group(5))

    # Enrich with additional metrics
    if parsed_data['models']:
        # Calculate global metrics
        parsed_data['total_rows_processed'] = sum(m.get('rows_processed', 0) for m in parsed_data['models'])
        parsed_data['total_data_processed'] = sum(m.get('data_processed_mb', 0) for m in parsed_data['models'])
        parsed_data['avg_duration'] = sum(m.get('duration_seconds', 0) for m in parsed_data['models']) / len(parsed_data['models'])

        # Calculate percentiles to assign cost levels
        data_processed_values = [m.get('data_processed_mb', 0) for m in parsed_data['models']]
        duration_values = [m.get('duration_seconds', 0) for m in parsed_data['models']]
        efficiency_values = [m.get('efficiency_ratio_kb', 0) for m in parsed_data['models']]

        # Define thresholds for cost categories based on percentiles
        data_processed_thresholds = {
            'Very High': np.percentile(data_processed_values, 90),
            'High': np.percentile(data_processed_values, 75),
            'Medium': np.percentile(data_processed_values, 50),
            'Low': np.percentile(data_processed_values, 25)
        }

        efficiency_thresholds = {
            'Very Poor': np.percentile(efficiency_values, 90),
            'Poor': np.percentile(efficiency_values, 75),
            'Average': np.percentile(efficiency_values, 50),
            'Good': np.percentile(efficiency_values, 25)
        }

        # Classify each model
        for model in parsed_data['models']:
            # Determine cost level
            data_mb = model.get('data_processed_mb', 0)
            if data_mb >= data_processed_thresholds['Very High']:
                model['cost_level'] = 'Very High'
            elif data_mb >= data_processed_thresholds['High']:
                model['cost_level'] = 'High'
            elif data_mb >= data_processed_thresholds['Medium']:
                model['cost_level'] = 'Medium'
            elif data_mb >= data_processed_thresholds['Low']:
                model['cost_level'] = 'Low'
            else:
                model['cost_level'] = 'Very Low'

            # Determine efficiency
            efficiency = model.get('efficiency_ratio_kb', 0)
            if efficiency >= efficiency_thresholds['Very Poor']:
                model['efficiency_level'] = 'Very Poor'
            elif efficiency >= efficiency_thresholds['Poor']:
                model['efficiency_level'] = 'Poor'
            elif efficiency >= efficiency_thresholds['Average']:
                model['efficiency_level'] = 'Average'
            elif efficiency >= efficiency_thresholds['Good']:
                model['efficiency_level'] = 'Good'
            else:
                model['efficiency_level'] = 'Very Good'

            # Add basic optimization recommendations
            model['optimization_recommendations'] = []

            # By default, models with poor efficiency are candidates for partitioning
            if model['efficiency_level'] in ['Very Poor', 'Poor']:
                model['optimization_recommendations'].append('Consider partitioning')
                model['partition_by_recommendation'] = 'date' if 'date' in model['model_name'] else 'created_at or timestamp'

            # For models that process a lot of data but have few rows
            if model['cost_level'] in ['Very High', 'High'] and model['efficiency_level'] in ['Very Poor', 'Poor']:
                model['optimization_recommendations'].append('Review joins and filters')
                model['optimization_recommendations'].append('Consider column pruning')

            # For models that have a lot of rows
            if model.get('rows_processed', 0) > np.percentile([m.get('rows_processed', 0) for m in parsed_data['models']], 75):
                model['optimization_recommendations'].append('Consider clustering')
                # Suggest columns for clustering based on the model name
                name = model['model_name'].lower()
                if 'user' in name or 'customer' in name:
                    model['cluster_by_recommendation'] = 'user_id or customer_id'
                elif 'event' in name:
                    model['cluster_by_recommendation'] = 'event_name, user_id'
                elif 'search' in name:
                    model['cluster_by_recommendation'] = 'search_term'
                elif 'product' in name:
                    model['cluster_by_recommendation'] = 'product_id'
                elif 'order' in name:
                    model['cluster_by_recommendation'] = 'order_id, customer_id'
                else:
                    model['cluster_by_recommendation'] = 'most frequently filtered columns'

        # Add metrics by layer/layer
        layers = {}
        for model in parsed_data['models']:
            layer = model.get('layer', 'other')
            if layer not in layers:
                layers[layer] = {
                    'count': 0,
                    'rows': 0,
                    'data': 0,
                    'duration': 0,
                    'models': []
                }

            layers[layer]['count'] += 1
            layers[layer]['rows'] += model.get('rows_processed', 0)
            layers[layer]['data'] += model.get('data_processed_mb', 0)
            layers[layer]['duration'] += model.get('duration_seconds', 0)
            layers[layer]['models'].append(model)

        parsed_data['layers'] = layers

        # Add metrics by model type
        model_types = {}
        for model in parsed_data['models']:
            model_type = model.get('model_type_short', 'unknown')
            if model_type not in model_types:
                model_types[model_type] = {
                    'count': 0,
                    'rows': 0,
                    'data': 0,
                    'duration': 0,
                    'models': []
                }

            model_types[model_type]['count'] += 1
            model_types[model_type]['rows'] += model.get('rows_processed', 0)
            model_types[model_type]['data'] += model.get('data_processed_mb', 0)
            model_types[model_type]['duration'] += model.get('duration_seconds', 0)
            model_types[model_type]['models'].append(model)

        parsed_data['model_types'] = model_types

        # Calculate optimization priority by model type
        optimization_priority = {
            'incremental': 'Medium',
            'table': 'High',
            'view': 'Low',
        }
        for type_name, type_data in parsed_data['model_types'].items():
            type_data['optimization_priority'] = optimization_priority.get(type_name, 'Medium')

    return parsed_data

def format_data_size(size_mb):
    """
    Format a data size into MiB, GiB, etc.
    """
    if size_mb < 0.1:
        return f"{size_mb * 1024:.1f} KiB"
    elif size_mb < 1024:
        return f"{size_mb:.1f} MiB"
    else:
        return f"{size_mb/1024:.1f} GiB"

def format_efficiency(kb_per_row):
    """
    Format an efficiency ratio KB/row
    """
    if kb_per_row < 0.1:
        return f"{kb_per_row * 1000:.1f} B/row"
    elif kb_per_row < 1000:
        return f"{kb_per_row:.1f} KB/row"
    else:
        return f"{kb_per_row/1024:.1f} MB/row"

def display_metrics(parsed_data):
    """Display the main metrics of the DBT execution"""
    st.subheader("📈 Key Metrics")

    col1, col2, col3, col4, col5 = st.columns(5)

    # Row 1: General information
    col1.metric("DBT Version", parsed_data.get('dbt_version', 'N/A'))

    adapter_info = ""
    if parsed_data.get('adapter'):
        adapter_info = f"{parsed_data['adapter'].get('name', 'N/A')} {parsed_data['adapter'].get('version', '')}"
    col2.metric("Adapter", adapter_info)

    target = parsed_data.get('concurrency', {}).get('target', 'N/A')
    col3.metric("Environment", target)

    total_time_sec = parsed_data.get('summary', {}).get('total_time_seconds', 0)
    col4.metric("Total Duration", f"{total_time_sec/60:.1f} min")

    success_text = "✅ Yes" if parsed_data.get('success', False) else "❌ No"
    col5.metric("Success", success_text)

    # Row 2: Technical statistics
    col1, col2, col3, col4 = st.columns(4)

    total_rows = parsed_data.get('total_rows_processed', 0)
    col1.metric("Rows Processed", f"{total_rows:,.0f}")

    total_data = parsed_data.get('total_data_processed', 0)
    col2.metric("Data Processed", format_data_size(total_data))

    avg_duration = parsed_data.get('avg_duration', 0)
    col3.metric("Average Duration", f"{avg_duration:.1f}s")

    models_count = len(parsed_data.get('models', []))
    total_models = parsed_data.get('resource_counts', {}).get('models', 0)
    col4.metric("Models Executed", f"{models_count}/{total_models}")

    # Last row: Success stats
    if parsed_data.get('stats'):
        stats = parsed_data['stats']
        cols = st.columns(5)
        cols[0].metric("PASS", stats.get('pass', 0))
        cols[1].metric("WARN", stats.get('warn', 0))
        cols[2].metric("ERROR", stats.get('error', 0))
        cols[3].metric("SKIP", stats.get('skip', 0))
        cols[4].metric("TOTAL", stats.get('total', 0))

def display_models_table(parsed_data):
    """Display a detailed table of executed models"""
    st.subheader("📋 Model Details")

    if not parsed_data.get('models'):
        st.warning("No models found in the logs")
        return

    # Create a DataFrame of models
    df = pd.DataFrame(parsed_data['models'])

    # Format columns
    df['layer'] = df['model_name'].apply(lambda x: x.split('.')[0] if '.' in x else 'other')
    df['name_only'] = df['model_name'].apply(lambda x: x.split('.')[-1] if '.' in x else x)
    df['data_formatted'] = df['data_processed_mb'].apply(format_data_size)
    df['efficiency_formatted'] = df['efficiency_ratio_kb'].apply(format_efficiency)
    df['rows_formatted'] = df['rows_processed'].apply(lambda x: f"{x:,.0f}")
    df['duration_formatted'] = df['duration_seconds'].apply(lambda x: f"{x:.2f}s")

    # Configure columns to display
    display_cols = [
        'model_number', 'name_only', 'layer', 'model_type_short', 'operation_type',
        'rows_formatted', 'data_formatted', 'duration_formatted', 'efficiency_formatted', 'cost_level'
    ]

    # Rename columns for display
    display_df = df[display_cols].rename(columns={
        'model_number': 'No.',
        'name_only': 'Name',
        'layer': 'Layer',
        'model_type_short': 'Type',
        'operation_type': 'Operation',
        'rows_formatted': 'Rows',
        'data_formatted': 'Data',
        'duration_formatted': 'Duration',
        'efficiency_formatted': 'Efficiency',
        'cost_level': 'Cost Level'
    })

    # Display the table
    st.dataframe(display_df, use_container_width=True)

def display_visualizations(parsed_data):
    """Display visualizations of the log data"""
    st.subheader("📊 Visualizations")

    if not parsed_data.get('models'):
        st.warning("No data to visualize")
        return

    tab1, tab2, tab3, tab4 = st.tabs(["By Layer", "Execution Time", "Distribution", "Costs"])

    with tab1:
        # Data by layer (bronze/silver/gold)
        st.subheader("Distribution by Layer")

        layers_df = pd.DataFrame([
            {
                'Layer': layer,
                'Models': data['count'],
                'Rows': data['rows'],
                'Data (MiB)': data['data'],
                'Total Duration (s)': data['duration']
            }
            for layer, data in parsed_data.get('layers', {}).items()
        ])

        if not layers_df.empty:
            # Bar chart for distribution by layer
            col1, col2 = st.columns(2)

            with col1:
                fig = px.bar(
                    layers_df,
                    x='Layer',
                    y=['Rows', 'Data (MiB)'],
                    barmode='group',
                    title="Data volume by layer",
                    labels={'value': 'Quantity', 'variable': 'Metric'}
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = px.bar(
                    layers_df,
                    x='Layer',
                    y='Total Duration (s)',
                    title="Execution time by layer",
                    labels={'Total Duration (s)': 'Duration (seconds)'}
                )
                st.plotly_chart(fig, use_container_width=True)

            st.dataframe(layers_df, use_container_width=True)

    with tab2:
        # Execution timeline
        st.subheader("Model Execution Timeline")

        # Create a DataFrame for the timeline
        models_df = pd.DataFrame(parsed_data['models'])

        if not models_df.empty:
            # Convert times to datetime format for the chart
            base_date = "2023-01-01 "  # Fictional date for visualization
            models_df['start_datetime'] = pd.to_datetime(base_date + models_df['start_time'])
            models_df['end_datetime'] = pd.to_datetime(base_date + models_df['end_time'])

            # Create a Gantt chart
            fig = px.timeline(
                models_df,
                x_start='start_datetime',
                x_end='end_datetime',
                y='model_name',
                color='layer',
                hover_data=['duration_seconds', 'rows_processed', 'data_processed_mb', 'cost_level'],
                labels={
                    'start_datetime': 'Start Time',
                    'end_datetime': 'End Time',
                    'model_name': 'Model',
                    'layer': 'Layer'
                },
                title="Model Execution Timeline"
            )

            # Format the x-axis to show only the time
            fig.update_xaxes(tickformat="%H:%M:%S")

            st.plotly_chart(fig, use_container_width=True)

    with tab3:
        # Data distribution
        st.subheader("Data Distribution")

        models_df = pd.DataFrame(parsed_data['models'])

        if not models_df.empty:
            col1, col2 = st.columns(2)

            with col1:
                fig = px.histogram(
                    models_df,
                    x='duration_seconds',
                    nbins=10,
                    title="Distribution of Execution Times",
                    labels={'duration_seconds': 'Duration (seconds)'}
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                fig = px.scatter(
                    models_df,
                    x='rows_processed',
                    y='duration_seconds',
                    color='layer',
                    size='data_processed_mb',
                    hover_data=['model_name', 'cost_level'],
                    title="Duration vs Volume",
                    labels={
                        'rows_processed': 'Rows Processed',
                        'duration_seconds': 'Duration (seconds)',
                        'layer': 'Layer'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)

    with tab4:
        # Cost analysis
        st.subheader("Cost Analysis")

        models_df = pd.DataFrame(parsed_data['models'])

        if not models_df.empty:
            col1, col2 = st.columns(2)

            with col1:
                # Treemap of processed data
                fig = px.treemap(
                    models_df,
                    path=['layer', 'model_name'],
                    values='data_processed_mb',
                    color='cost_level',
                    title="Distribution of Processed Data",
                    color_discrete_map={
                        'Very High': '#FF0000',
                        'High': '#FFA500',
                        'Medium': '#FFFF00',
                        'Low': '#00FF00',
                        'Very Low': '#00FF7F'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                # Bubble chart for efficiency
                fig = px.scatter(
                    models_df,
                    x='data_processed_mb',
                    y='efficiency_ratio_kb',
                    color='cost_level',
                    size='rows_processed',
                    hover_name='model_name',
                    log_x=True,
                    log_y=True,
                    title="Efficiency (KB/row) vs Data Processed",
                    labels={
                        'data_processed_mb': 'Data Processed (MiB)',
                        'efficiency_ratio_kb': 'KB/row (lower is better)',
                        'cost_level': 'Cost Level'
                    },
                    color_discrete_map={
                        'Very High': '#FF0000',
                        'High': '#FFA500',
                        'Medium': '#FFFF00',
                        'Low': '#00FF00',
                        'Very Low': '#00FF7F'
                    }
                )
                st.plotly_chart(fig, use_container_width=True)

def display_cost_analysis(parsed_data):
    """Display cost analysis and optimization recommendations"""
    st.header("💰 FinOps Analysis and Optimization")

    tab1, tab2, tab3, tab4 = st.tabs(["Top Consumers", "Optimizations", "Distribution by Type", "Recommendations"])

    models_df = pd.DataFrame(parsed_data['models'])

    with tab1:
        st.subheader("Top Data-Consuming Models")

        # Sort by data processed (descending)
        top_data_models = models_df.sort_values('data_processed_mb', ascending=False).head(20)

        # Create a formatted table
        top_data_table = pd.DataFrame({
            'Model': top_data_models['model_name'],
            'Data Processed': top_data_models['data_processed_mb'].apply(format_data_size),
            'Duration': top_data_models['duration_seconds'].apply(lambda x: f"{x:.2f}s"),
            'Rows Created': top_data_models['rows_processed'].apply(lambda x: f"{x:,.1f}"),
            'Cost Impact': top_data_models['cost_level']
        })

        st.dataframe(
            top_data_table,
            use_container_width=True
        )

        # Chart of top models
        fig = px.bar(
            top_data_models,
            x='model_name',
            y='data_processed_mb',
            color='cost_level',
            title="Top 10 Models by Data Processed",
            labels={
                'model_name': 'Model',
                'data_processed_mb': 'Data Processed (MiB)',
                'cost_level': 'Cost Impact'
            },
            color_discrete_map={
                'Very High': '#FF0000',
                'High': '#FFA500',
                'Medium': '#FFFF00',
                'Low': '#00FF00',
                'Very Low': '#00FF7F'
            }
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("Inefficient Models")
        st.markdown("""
        The efficiency ratio (KB/row) measures the amount of data processed to produce each row of the result.
        In BigQuery, where costs are primarily based on scanned/processed data, this is a critical metric
        for cost optimization.
        """)

        # Select the least efficient models (highest KB/row)
        top_inefficient = models_df.sort_values('efficiency_ratio_kb', ascending=False).head(20)

        # Create a table for inefficient models
        inefficient_table = pd.DataFrame({
            'Model': top_inefficient['model_name'],
            'Data Processed': top_inefficient['data_processed_mb'].apply(format_data_size),
            'Duration': top_inefficient['duration_seconds'].apply(lambda x: f"{x:.2f}s"),
            'Efficiency Ratio': top_inefficient['efficiency_ratio_kb'].apply(format_efficiency),
            'Recommendation': top_inefficient['optimization_recommendations'].apply(lambda x: ", ".join(x) if isinstance(x, list) else "")
        })

        st.dataframe(inefficient_table, use_container_width=True)

        # Efficiency chart
        fig = px.bar(
            top_inefficient,
            x='model_name',
            y='efficiency_ratio_kb',
            color='efficiency_level',
            title="Top 10 Least Efficient Models (KB/row)",
            labels={
                'model_name': 'Model',
                'efficiency_ratio_kb': 'KB/row (lower is better)',
                'efficiency_level': 'Efficiency Level'
            },
            color_discrete_map={
                'Very Poor': '#FF0000',
                'Poor': '#FFA500',
                'Average': '#FFFF00',
                'Good': '#00FF00',
                'Very Good': '#00FF7F'
            }
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab3:
        st.subheader("Distribution by Model Type")

        # Aggregate data by model type
        model_types_data = []
        for model_type, data in parsed_data.get('model_types', {}).items():
            model_types_data.append({
                'Model Type': model_type,
                'Count': data['count'],
                'Optimization Priority': data.get('optimization_priority', 'Medium')
            })

        model_types_df = pd.DataFrame(model_types_data)

        # Display the distribution of model types
        col1, col2 = st.columns(2)

        with col1:
            # Pie chart for type distribution
            fig = px.pie(
                model_types_df,
                values='Count',
                names='Model Type',
                title="Distribution of Model Types",
                color='Model Type',
                hover_data=['Optimization Priority']
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Table of model types
            st.dataframe(model_types_df, use_container_width=True)

            # Insights on model types
            st.markdown("""
            **Insights on Model Types:**

            - **Table**: Consumes more resources on each run but offers fast reads
            - **View**: Consumes few resources on creation but can be costly on frequent queries
            - **Incremental**: Good balance between performance and costs, but requires a good update strategy
            """)

    with tab4:
        st.subheader("Optimization Recommendations")

        # Partitioning recommendations
        st.write("##### 🔄 Partitioning Candidates")

        # Filter models that are good candidates for partitioning
        partition_candidates = models_df[
            (models_df['data_processed_mb'] > np.percentile(models_df['data_processed_mb'], 75)) &
            (models_df['efficiency_ratio_kb'] > 0)
        ].sort_values('data_processed_mb', ascending=False).head(20)

        partition_table = pd.DataFrame({
            'Model': partition_candidates['model_name'],
            'Current Size': partition_candidates['data_processed_mb'].apply(format_data_size),
            'Processing': partition_candidates['duration_seconds'].apply(lambda x: f"{x:.2f}s"),
            'Partition By': partition_candidates['partition_by_recommendation'].fillna('date')
        })

        st.dataframe(partition_table, use_container_width=True)

        # Clustering recommendations
        st.write("##### 🔍 Clustering Recommendations")

        # Filter models that are good candidates for clustering
        clustering_candidates = models_df[
            (models_df['rows_processed'] > np.percentile(models_df['rows_processed'], 75))
        ].sort_values('rows_processed', ascending=False).head(20)

        clustering_table = pd.DataFrame({
            'Model': clustering_candidates['model_name'],
            'Processing': clustering_candidates['data_processed_mb'].apply(format_data_size),
            'Cluster By': clustering_candidates['cluster_by_recommendation'].fillna('id, date'),
            'Expected Impact': ['High' if r > np.percentile(models_df['rows_processed'], 90) else 'Medium' for r in clustering_candidates['rows_processed']]
        })

        st.dataframe(clustering_table, use_container_width=True)

        # Cost of creating tables
        st.write("##### 💰 Cost of Creating Tables")

        # Filter only tables
        tables_only = models_df[models_df['operation_type'] == 'CREATE TABLE'].sort_values('data_processed_mb', ascending=False).head(20)

        tables_cost_table = pd.DataFrame({
            'Model': tables_only['model_name'],
            'Rows': tables_only['rows_processed'].apply(lambda x: f"{x:,.0f}"),
            'Data Processed': tables_only['data_processed_mb'].apply(format_data_size),
            'Duration': tables_only['duration_seconds'].apply(lambda x: f"{x:.2f}s"),
            'Cost Level': tables_only['cost_level']
        })

        st.dataframe(tables_cost_table, use_container_width=True)

def main():
    """Main function of the application."""
    st.set_page_config(page_title="DBT Log Analyzer", layout="wide")

    st.title("🔍 DBT Log Analyzer with FinOps")
    st.markdown("""
        This application allows you to analyze DBT logs to gain insights into your runs
        and get cost optimization recommendations for BigQuery.
        Upload your log file below to get started.
    """)

    uploaded_file = st.file_uploader("Upload your DBT log file", type=["log", "txt"])

    if uploaded_file is not None:
        log_content = uploaded_file.getvalue().decode("utf-8")

        with st.spinner("Analyzing logs..."):
            parsed_data = parse_dbt_log(log_content)

        if not parsed_data.get('models'):
            st.error("No models could be extracted from the logs. Check the file format.")
            st.code(log_content[:500] + "...")
            return

        # Display metrics and tables
        display_metrics(parsed_data)
        st.markdown("---")

        display_models_table(parsed_data)
        st.markdown("---")

        display_visualizations(parsed_data)
        st.markdown("---")

        display_cost_analysis(parsed_data)

if __name__ == "__main__":
    main()
