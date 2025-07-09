from dash import html, dcc
import pandas as pd
from sqlalchemy import create_engine
import plotly.graph_objs as go
import plotly_express as px
from dash import dash_table

def get_data(department=None, module=None, status=None, date=None):
    engine = create_engine("mysql+pymysql://root:1619@localhost:3306/drona")

    print("Department Filter:", department)
    print("Module Filter:", module)
    print("Status Filter:", status)
    print("Date Filter:", date)


    
    params = {}
    filter_clauses = []

    if department:
        filter_clauses.append(f"d.name = '{department}'")
        params['department'] = department
    if module:
        filter_clauses.append(f"vs.last_module_id = {module}")
        params['module'] = module
    if status:
        filter_clauses.append(f"vs.status = '{status}'")
        params['status'] = status  
    if date:
        filter_clauses.append(f"DATE(vs.created_at) = '{date}'")
        params['date'] = date

    filter_condition = " AND ".join(filter_clauses)
    where_clause = f"WHERE {filter_condition}" if filter_condition else ""

    print("Query Params:", params)
    print("Final WHERE Clause:", where_clause)

    # Total Trainings, Failures, Success %
    query_data = '''
        SELECT
    (
        SELECT SUM(total_sessions)
        FROM (
            SELECT 
                viewer_id,
                MAX(training_count) AS total_sessions
            FROM (
                SELECT 
                    viewer_id,
                    COUNT(DISTINCT training_session_id) AS training_count
                FROM viewer_session
                GROUP BY viewer_id
            ) AS per_viewer_module
            GROUP BY viewer_id
        ) AS viewer_max_sessions
    ) AS total_sessions,

    (
        SELECT COUNT(*)
        FROM viewer_session
        WHERE status = 'failed'
        AND last_module_id IN (1, 2)
    ) AS total_failures,

    (
        SELECT ROUND(
            (COUNT(*) * 100.0) / 
            (
                SELECT SUM(total_sessions)
                FROM (
                    SELECT 
                        viewer_id,
                        MAX(training_count) AS total_sessions
                    FROM (
                        SELECT 
                            viewer_id,
                            COUNT(DISTINCT training_session_id) AS training_count
                        FROM viewer_session
                        GROUP BY viewer_id
                    ) AS per_viewer_module
                    GROUP BY viewer_id
                ) AS viewer_max_sessions
            ), 2
        )
        FROM viewer_session
        WHERE status = 'success'
    ) AS success_percentage;    
    '''
    df = pd.read_sql(query_data, con=engine)
    total_traings = df['total_sessions'].iloc[0]
    total_failures = df['total_failures'].iloc[0]
    success_percentage = df['success_percentage'].iloc[0]

    # Dropdown Data Fetching (Same as before, untouched)
    query = """SELECT DISTINCT d.name AS department_name FROM viewer v JOIN department d ON v.department_id = d.id WHERE v.department_id IS NOT NULL AND v.department_id != '';"""
    df = pd.read_sql(query, con=engine)
    department_options = [{'label': dept, 'value': dept} for dept in df['department_name']]

    query = "SELECT DISTINCT id, module_name FROM module WHERE is_active = 1"
    df = pd.read_sql(query, con=engine)
    module_options = [{'label': row['module_name'], 'value': row['id']} for _, row in df.iterrows()]

    query = "SELECT DISTINCT status FROM viewer_session WHERE status IS NOT NULL"
    df = pd.read_sql(query, con=engine)
    status_options = [{'label': row['status'].capitalize(), 'value': row['status'].lower()} for _, row in df.iterrows()]

    query = """SELECT DISTINCT DATE(created_at) AS session_date FROM viewer_session ORDER BY session_date DESC"""
    df = pd.read_sql(query, con=engine)
    date_options = [{'label': dt, 'value': dt} for dt in df['session_date']]

    # ✅ Monthly Trainings Query (Now with Filters Applied Correctly)
    query_monthly = f"""
        SELECT
            month,
            SUM(latest_session) AS total_trainings
        FROM (
            SELECT
                MONTHNAME(vs.created_at) AS month,
                MAX(CAST(vs.training_session_id AS UNSIGNED)) AS latest_session,
                vs.viewer_id
            FROM viewer_session vs
            JOIN viewer v ON vs.viewer_id = v.id
            JOIN department d ON v.department_id = d.id
            {where_clause}
            GROUP BY month, vs.viewer_id
        ) AS subquery
        GROUP BY month
        ORDER BY FIELD(month, 'January', 'February', 'March', 'April', 'May', 'June',
                            'July', 'August', 'September', 'October', 'November', 'December');

    """

    df_monthly = pd.read_sql(query_monthly, con=engine, params=params)
    training_by_month_fig = go.Figure(
        data=[
            go.Bar(
                x=df_monthly['month'],
                y=df_monthly['total_trainings'],
                marker_color='skyblue',
                text=df_monthly['total_trainings'],
            )
        ],
        layout=go.Layout(
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            font=dict(color='white')
        )
    )
    training_by_month_fig.update_layout(margin=dict(l=20, r=20, t=50, b=20))

    # ✅ Pie Chart Query (Now Filtered)
    query_status = f"""
        SELECT 
            vs.status, 
            COUNT(*) AS count
        FROM viewer_session vs
        LEFT JOIN viewer v ON v.id = vs.viewer_id
        LEFT JOIN department d ON v.department_id = d.id
        {where_clause}
        GROUP BY vs.status
    """
    df_status = pd.read_sql(query_status, con=engine, params=params)
    pie_chart = px.pie(
        df_status,
        names='status',
        values='count',
        hole=0.4
    )
    pie_chart.update_traces(
        textinfo='percent',
        hoverinfo='skip',
        marker=dict(line=dict(color='white', width=1))
    )
    pie_chart.update_layout(
        showlegend=True,
        margin=dict(l=20, r=20, t=50, b=20),
        # height=400,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white')
    )

    # ✅ Module Failure Rate Table Query (Now Filtered)
    query_failure = f"""
        SELECT
            m.module_name,
            COALESCE(ROUND(100.0 * SUM(CASE WHEN vs.status = 'FAILED' THEN 1 ELSE 0 END) / NULLIF(COUNT(vs.id), 0), 2), 0) AS failure_percentage,
            COALESCE(ROUND(100.0 * SUM(CASE WHEN vs.status = 'SUCCESS' THEN 1 ELSE 0 END) / NULLIF(COUNT(vs.id), 0), 2), 0) AS success_percentage,
            COALESCE(ROUND(100.0 * SUM(CASE WHEN vs.status = 'INCOMPLETE' THEN 1 ELSE 0 END) / NULLIF(COUNT(vs.id), 0), 2), 0) AS incomplete_percentage
        FROM module m
        LEFT JOIN viewer_session vs ON vs.last_module_id = m.id
        LEFT JOIN viewer v ON v.id = vs.viewer_id
        GROUP BY m.module_name
        ORDER BY m.module_name;
    """
    df_failure = pd.read_sql(query_failure, con=engine, params=params)
    failure_table_fig = go.Figure(data=[go.Table(
        header=dict(
            values=["Module Name", "Failure Rate","Success Rate","In-Complete Rate"],
            fill_color='rgba(0,0,0,0)',
            align='center',
            font=dict(color='white', size=14)
        ),
        cells=dict(
            values=[df_failure['module_name'].str.pad(50, side='right'), df_failure['failure_percentage'],df_failure['success_percentage'],df_failure['incomplete_percentage']],
            fill_color='rgba(0,0,0,0)',
            align='center',
            line_color='white',
            font=dict(color='white', size=12)
        )
    )])
    failure_table_fig.update_layout(margin=dict(l=20, r=20, t=20, b=20), height=300, paper_bgcolor='rgba(0,0,0,0)')

    # ✅ Report Table Query (Now Filtered)
    query_report = f"""
       SELECT
            v.name AS viewer_name,
            m.module_name,
            d.name AS department_name, 
            vs.score AS success_rate,
            vs.status
        FROM viewer_session vs
        JOIN viewer v ON v.id = vs.viewer_id
        JOIN department d ON v.department_id = d.id 
        JOIN module m ON m.id = vs.last_module_id
        WHERE vs.id IN (
            SELECT MAX(vs2.id)
            FROM viewer_session vs2
            GROUP BY vs2.viewer_id
        )
        ORDER BY v.name;

    """
    df = pd.read_sql(query_report, con=engine, params=params)
    table_fig = go.Figure(
        data=[
            go.Table(
                header=dict(
                    values=["Trainer Name", "Module", "Department", "Score", "Status"],
                    fill_color="rgba(0, 140, 175, 0.5)",
                    line_color='white',
                    line_width=2,
                    font=dict(color='white', size=14),
                    align='center',
                    height=40
                ),
                cells=dict(
                    values=[
                        df['viewer_name'],
                        df['module_name'],
                        df['department_name'],
                        df['success_rate'],
                        df['status']
                    ],
                    fill_color='rgba(0,0,0,0)',
                    line_color='white',
                    line_width=2,
                    font=dict(color='white', size=13),
                    align='center',
                    height=40,
                )
            )
        ]
    )
    table_fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), paper_bgcolor='rgba(0,0,0,0)')

    return {
        'total_traings': total_traings,
        'total_failures': total_failures,
        'success_percentage': success_percentage,
        'department_options': department_options,
        'module_options': module_options,
        'status_options': status_options,
        'date_options': date_options,
        'training_by_month_fig': training_by_month_fig,
        'pie_chart': pie_chart,
        'failure_table_fig': failure_table_fig,
        'table_fig': table_fig
    }

def reports_layout():
    analytic_data = get_data()

    def display_value(value):
        return value if value is not None else "Loading..."

    return html.Div([
        html.H2("Reports", style={'color': 'white', 'padding': '10px', 'marginTop': '-30px'}),
        html.Div([
            html.Div([
                html.H4("Total Trainings"),
                html.P(display_value(analytic_data['total_traings']))
            ], className='metric-box'),
            html.Div([
                html.H4("Average Score"),
                html.P(display_value(analytic_data['success_percentage']))
            ], className='metric-box'),
            html.Div([
                html.H4("Total Failures"),
                html.P(display_value(analytic_data['total_failures']))
            ], className='metric-box'),
            html.Div([
                html.H4("Certification Rate"),
                html.P("-")
            ], className='metric-box'),
        ], className='metrics-row'),

        html.Div([
            html.Div([
                html.Label("Date Range", className='dropdown-label'),
                dcc.Dropdown(
                    id='date-dropdown',
                    options=analytic_data['date_options'],
                    placeholder="Select Date Range",
                    className='dropdown'
                )
            ], className='dropdown-item'),
            html.Div([
                html.Label("Department", className='dropdown-label'),
                dcc.Dropdown(
                    id='dept-dropdown',
                    options=analytic_data['department_options'],
                    placeholder="Select Department",
                    className='dropdown'
                )
            ], className='dropdown-item'),
            html.Div([
                html.Label("Module", className='dropdown-label'),
                dcc.Dropdown(
                    id='module-dropdown',
                    options=analytic_data['module_options'],
                    placeholder="Select Module",
                    className='dropdown'
                )
            ], className='dropdown-item'),
            html.Div([
                html.Label("Status", className='dropdown-label'),
                dcc.Dropdown(
                    id='status-dropdown',
                    options=analytic_data['status_options'],
                    placeholder="Select status",
                    className='dropdown'
                )
            ], className='dropdown-item')
        ], className='filters-row'),

        html.Div([
            html.Div([
                html.H4('Traings completed by month'),
                dcc.Graph(
                    id='bar-chart',
                    figure=analytic_data['training_by_month_fig'],
                    config={'displayModeBar': False},
                    style={'height': '300px'}
                )
            ], className='analytics-box'),
            html.Div([
                html.H4('Traing status'),
                dcc.Graph(
                    id='pie-chart',
                    figure=analytic_data['pie_chart'],
                    config={'displayModeBar': False},
                    style={'height': '300px'}
                )
            ], className='analytics-box'),
            html.Div([
                html.H4("Module Failure Rate"),
                dcc.Graph(
                    id='failure-table',
                    figure=analytic_data['failure_table_fig'],
                    style={'borderRadius': '10px', 'width': '450px','height': '300px'},
                    config={'displayModeBar': False}
                )
            ], className='analytics-box')
        ], className='three-boxes-row'),

        html.Div([
            html.H3("Training Report Table", style={'color': 'white', 'marginLeft': '15px', 'marginTop': '15px'}),
            dcc.Graph(
                figure=analytic_data['table_fig'],
                style={'width': '100%', 'marginTop': '0px','overflowX': 'auto'},
                config={'displayModeBar': False}
            )
        ], className='table-section'),

    ], className='reports-container')
